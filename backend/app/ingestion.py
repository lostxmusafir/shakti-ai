"""Local, bounded file parsing with explicit provenance and review requirements."""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .analysis import MAX_COLUMNS, MAX_ROWS, decimal_value, is_null, iso_date
from .config import tesseract_command

TABLE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_MAX_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000


def _cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        if len(value) > 10_000:
            raise ValueError("A cell exceeds the 10,000-character limit.")
        return value if value.strip() else None
    if isinstance(value, (int, float, bool)):
        return str(value) if not isinstance(value, bool) else value
    return str(value)


def _kind(values: list, warnings: list, name: str) -> str:
    present = [v for v in values if not is_null(v)]
    if not present:
        return "text"
    # Preserve code/identifier columns: casting 001 to 1 changes identity.
    if any(isinstance(v, str) and re.fullmatch(r"[+-]?0\d+", v.strip()) for v in present):
        warnings.append(f"{name}: leading-zero identifiers preserved as text.")
        return "text"
    number_count = 0
    for value in present:
        try:
            decimal_value(value)
            number_count += 1
        except ValueError:
            pass
    if number_count == len(present):
        return "number"
    if number_count:
        warnings.append(f"{name}: mixed numeric/text values retained as text; numeric operations require clean values.")
    try:
        for value in present:
            iso_date(value)
        return "date"
    except ValueError:
        pass
    if any(isinstance(v, str) and re.fullmatch(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", v.strip()) for v in present):
        warnings.append(f"{name}: ambiguous date format retained as text. Confirm YYYY-MM-DD dates before date comparisons.")
    return "text"


def make_table(name: str, raw: list[list], source_numbers: list[int], *, warnings: list[str] | None = None,
               formula_indexes: set[int] | None = None, requires_review: bool = False) -> dict:
    warnings = list(warnings or [])
    formula_indexes = formula_indexes or set()
    if not raw:
        raise ValueError("The file/table is empty.")
    while raw and all(is_null(v) for v in raw[0]):
        raw = raw[1:]
        source_numbers = source_numbers[1:]
        warnings.append("Leading blank rows were skipped before the header.")
    if not raw:
        raise ValueError("The file/table has no header.")
    header = raw[0]
    # Trailing empty Excel columns are not part of the table.
    while header and is_null(header[-1]) and all(len(r) < len(header) or is_null(r[len(header) - 1]) for r in raw[1:]):
        header = header[:-1]
    if not header or any(is_null(v) for v in header):
        raise ValueError("Every data column needs a nonempty header; choose a rectangular table with one header row.")
    headers = [str(v).strip() for v in header]
    if any(len(h) > 250 for h in headers):
        raise ValueError("Column names must be at most 250 characters.")
    if len(headers) != len(set(headers)):
        raise ValueError("Duplicate column headers are ambiguous. Rename them before uploading.")
    if len(headers) > MAX_COLUMNS:
        raise ValueError("A table can contain at most 50 columns.")
    rows, origins = [], []
    empty_count = short_count = 0
    for row, source in zip(raw[1:], source_numbers[1:]):
        if all(is_null(v) for v in row):
            empty_count += 1
            continue
        if len(row) > len(headers) and any(not is_null(v) for v in row[len(headers):]):
            raise ValueError(f"Source row {source} has more fields than the header.")
        if len(row) < len(headers):
            short_count += 1
        normalized = [_cell(v) for v in row[:len(headers)]]
        normalized += [None] * (len(headers) - len(normalized))
        rows.append(normalized)
        origins.append(source)
        if len(rows) > MAX_ROWS:
            raise ValueError("A table can contain at most 50,000 data rows.")
    if empty_count:
        warnings.append(f"{empty_count} completely blank row(s) skipped; source row numbers preserved.")
    if short_count:
        warnings.append(f"{short_count} short row(s) padded with null; no values inferred.")
    if not rows:
        raise ValueError("The table has a header but no data rows.")
    columns = []
    for i, header_name in enumerate(headers):
        formula = i in formula_indexes
        columns.append({"name": header_name, "type": "text" if formula else _kind([r[i] for r in rows], warnings, header_name), "formula": formula})
    if formula_indexes:
        warnings.append("Formula-dependent columns are blocked for analysis. Upload verified values-only data; formulas are never recalculated.")
    if any(any(isinstance(v, str) and re.search(r"\b(?:sub\s*total|grand\s*total)\b", v, re.I) for v in row) for row in rows):
        warnings.append("Possible subtotal/total rows detected. They are retained; filter them explicitly to prevent double counting.")
    return {"name": name, "columns": columns, "rows": rows, "source_rows": origins,
            "warnings": list(dict.fromkeys(warnings)), "requires_review": requires_review, "confirmed": False}


def _parse_csv(path: Path) -> list[dict]:
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-16" if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV encoding must be UTF-8 or BOM-marked UTF-16. Save the file as CSV UTF-8.") from exc
    if "\x00" in text:
        raise ValueError("CSV contains binary/null bytes.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text, newline=""), dialect=dialect, strict=True)
    rows, origins = [], []
    try:
        for row in reader:
            rows.append(row)
            origins.append(reader.line_num)
            if len(rows) > MAX_ROWS + 1001:
                raise ValueError("CSV exceeds the supported row limit.")
            if len(row) > MAX_COLUMNS:
                raise ValueError("A table can contain at most 50 columns.")
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}.") from exc
    return [make_table("CSV", rows, origins)]


def _parse_xlsx(path: Path) -> list[dict]:
    from openpyxl import load_workbook
    try:
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if len(infos) > 10_000 or sum(i.file_size for i in infos) > 100 * 1024 * 1024:
                raise ValueError("Workbook expands beyond the 100 MB safety limit.")
            if any("vbaproject" in i.filename.casefold() for i in infos):
                raise ValueError("Macro-enabled workbooks are not supported.")
            if any(i.flag_bits & 1 for i in infos):
                raise ValueError("Encrypted workbooks are not supported.")
        book = load_workbook(path, read_only=False, data_only=False, keep_links=False)
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise ValueError("Invalid or unsupported XLSX workbook.") from exc
    try:
        if len(book.worksheets) > 20:
            raise ValueError("A workbook can contain at most 20 sheets.")
        result = []
        for sheet in book.worksheets:
            if sheet.max_row > MAX_ROWS + 1 or sheet.max_column > MAX_COLUMNS:
                raise ValueError(f"Sheet {sheet.title!r} exceeds 50,000 rows or 50 columns. Remove unused formatted rows/columns.")
            if sheet.merged_cells.ranges:
                raise ValueError(f"Sheet {sheet.title!r} contains merged cells. Supply a rectangular table with a single header row.")
            raw, formulas = [], set()
            for row in sheet.iter_rows():
                raw.append([cell.value for cell in row])
                for cell in row:
                    if cell.data_type == "f":
                        formulas.add(cell.column - 1)
            if not raw or all(all(is_null(v) for v in row) for row in raw):
                continue
            warnings = []
            if sheet.sheet_state != "visible":
                warnings.append("This sheet is hidden in the workbook; it is available for explicit selection.")
            if any(dim.hidden for dim in sheet.row_dimensions.values()) or any(dim.hidden for dim in sheet.column_dimensions.values()):
                warnings.append("Hidden rows/columns are included. Apply explicit filters if they should be excluded.")
            result.append(make_table(sheet.title, raw, list(range(1, len(raw) + 1)), warnings=warnings, formula_indexes=formulas))
        if not result:
            raise ValueError("Workbook has no nonempty tables.")
        return result
    finally:
        book.close()


def _ocr_image(path: Path) -> tuple[list[list[str | None]], list[str]]:
    """Extract an axis-aligned simple grid, or cluster TSV text into row bands.

    Extraction is always a proposal, never a verified table. Review is mandatory.
    The text path makes no inference about missing cells; misalignment is surfaced
    for correction rather than silently shifted into arithmetic.
    """
    tesseract = tesseract_command()
    if not tesseract or not Path(tesseract).is_file():
        raise ValueError("Image OCR is unavailable: install Tesseract locally and set TESSERACT_CMD to tesseract.exe, then restart the worker. CSV/XLSX remain available.")
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ValueError("Image OCR needs opencv-python-headless. Install the backend requirements and restart the worker.") from exc
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(path) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("Image exceeds 25 megapixels. Crop it to the table.")
            source.verify()
        data = np.fromfile(str(path), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image could not be decoded.")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid PNG/JPEG image.") from exc
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if min(gray.shape) < 80:
        raise ValueError("Image is too small. Upload a clear table screenshot.")
    # Remove grid lines; TSV word coordinates retain the original alignment.
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, gray.shape[1] // 25), 1)))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, gray.shape[0] // 25))))
    cleaned = cv2.bitwise_not(cv2.subtract(binary, cv2.bitwise_or(horizontal, vertical)))
    with tempfile.TemporaryDirectory(prefix="zydrakon-ocr-") as tmp:
        prepared = Path(tmp) / "table.png"
        cv2.imencode(".png", cleaned)[1].tofile(str(prepared))
        try:
            process = subprocess.run([tesseract, str(prepared), "stdout", "--psm", "6", "-l", "eng", "tsv"],
                                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired as exc:
            raise ValueError("OCR exceeded 45 seconds. Crop the image or use CSV/XLSX.") from exc
        if process.returncode != 0:
            raise ValueError("Local OCR failed. Check the Tesseract installation and English language data.")
    words = []
    low_confidence = 0
    for item in csv.DictReader(io.StringIO(process.stdout), delimiter="\t"):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        try:
            left, top, width, height = [int(item[k]) for k in ("left", "top", "width", "height")]
            confidence = float(item["conf"])
        except (KeyError, TypeError, ValueError):
            continue
        words.append({"text": text, "x": left, "y": top + height / 2, "w": width, "h": height})
        low_confidence += confidence < 80
    if not words:
        raise ValueError("No readable table text found. Upload a clearer screenshot.")
    median_height = float(np.median([word["h"] for word in words]))
    bands: list[list] = []
    for word in sorted(words, key=lambda word: (word["y"], word["x"])):
        if not bands or abs(word["y"] - np.mean([w["y"] for w in bands[-1]])) > median_height * 0.7:
            bands.append([word])
        else:
            bands[-1].append(word)
    # Detect vertical rules as preferred cell boundaries.
    strength = np.count_nonzero(vertical, axis=0)
    ruled_x = np.where(strength > gray.shape[0] * 0.35)[0].tolist()
    groups = []
    for x in ruled_x:
        if not groups or x - groups[-1][-1] > 3:
            groups.append([x])
        else:
            groups[-1].append(x)
    boundaries = [float(np.mean(group)) for group in groups]
    table = []
    warnings = ["OCR proposal: verify every cell and row alignment against the source image before confirming."]
    if 3 <= len(boundaries) <= MAX_COLUMNS + 1:
        for band in bands:
            cells = []
            for left, right in zip(boundaries, boundaries[1:]):
                cell_words = sorted([w for w in band if left <= w["x"] + w["w"] / 2 < right], key=lambda w: w["x"])
                cells.append(" ".join(w["text"] for w in cell_words) or None)
            if any(cells):
                table.append(cells)
    else:
        # Borderless simple screenshots: columns are anchored by header groups.
        header = sorted(bands[0], key=lambda word: word["x"])
        header_groups = []
        for word in header:
            if not header_groups or word["x"] - (header_groups[-1][-1]["x"] + header_groups[-1][-1]["w"]) > median_height * 1.5:
                header_groups.append([word])
            else:
                header_groups[-1].append(word)
        if len(header_groups) < 2:
            raise ValueError("Could not identify table columns. Use a clear screenshot with column spacing or visible grid lines.")
        starts = [g[0]["x"] for g in header_groups]
        table.append([" ".join(w["text"] for w in g) for g in header_groups])
        for band in bands[1:]:
            cells = [[] for _ in starts]
            for word in sorted(band, key=lambda word: word["x"]):
                idx = min(range(len(starts)), key=lambda i: abs(word["x"] - starts[i]))
                cells[idx].append(word["text"])
            table.append([" ".join(cell) or None for cell in cells])
        warnings.append("Borderless-table columns were inferred from header positions; confirm column alignment carefully.")
    if low_confidence:
        warnings.append(f"{low_confidence} OCR word(s) had low recognition confidence. Confidence is not a correctness guarantee.")
    if len(table) < 2:
        raise ValueError("OCR did not recover a header and data row. Use a clearer table screenshot.")
    return table, warnings


def parse_file(path: str | Path, original_name: str) -> list[dict]:
    path = Path(path)
    extension = Path(original_name).suffix.casefold()
    if extension not in (".csv", ".xlsx", ".png", ".jpg", ".jpeg"):
        raise ValueError("Supported files: CSV, XLSX, PNG, JPG, JPEG. Macros and legacy XLS files are not supported.")
    limit = IMAGE_MAX_BYTES if extension in (".png", ".jpg", ".jpeg") else TABLE_MAX_BYTES
    size = path.stat().st_size
    if size <= 0:
        raise ValueError("The uploaded file is empty.")
    if size > limit:
        raise ValueError(f"File exceeds the {limit // (1024 * 1024)} MB limit.")
    if extension == ".csv":
        return _parse_csv(path)
    if extension == ".xlsx":
        return _parse_xlsx(path)
    raw, warnings = _ocr_image(path)
    warnings.append("Image source rows identify extracted table rows, not Excel cell coordinates.")
    return [make_table("Image table", raw, list(range(1, len(raw) + 1)), warnings=warnings, requires_review=True)]
