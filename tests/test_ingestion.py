import csv
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.analysis import analyze
from app.ingestion import make_table, parse_file


def csv_file(tmp_path, text, name="data.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


def test_csv_precision_nulls_and_source_rows(tmp_path):
    path = csv_file(tmp_path, "Code,Amount,Date\n001,0.10,2026-01-01\n002,,2026-01-02\n003,0.20,2026-01-03\n")
    t = parse_file(path, path.name)[0]
    assert t["rows"][0] == ["001", "0.10", "2026-01-01"]
    assert t["columns"][0]["type"] == "text"
    assert t["columns"][1]["type"] == "number"
    assert t["columns"][2]["type"] == "date"
    assert t["rows"][1][1] is None
    assert t["source_rows"] == [2, 3, 4]
    assert analyze(t, {"action": "sum", "column": "Amount"})["value"] == "0.3"
    assert not t["confirmed"]


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
def test_delimiters(tmp_path, delimiter):
    p = csv_file(tmp_path, f"Item{delimiter}Amount\nA{delimiter}10\nB{delimiter}20\n")
    assert parse_file(p, p.name)[0]["rows"] == [["A", "10"], ["B", "20"]]


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_bom_encodings(tmp_path, encoding):
    p = csv_file(tmp_path, "Item,Amount\nA,10\n", encoding=encoding)
    assert parse_file(p, p.name)[0]["columns"][0]["name"] == "Item"


@pytest.mark.parametrize("text,match", [("A,A\n1,2\n", "Duplicate"), ("A,\n1,2\n", "nonempty header"), ("A,B\n1,2,3\n", "more fields"), ("A,B\n", "no data"), ("\x00bad", "binary"), ("", "empty")])
def test_malformed_csv(tmp_path, text, match):
    p = csv_file(tmp_path, text)
    with pytest.raises(ValueError, match=match):
        parse_file(p, p.name)


def test_short_rows_blank_rows_and_mixed_types(tmp_path):
    p = csv_file(tmp_path, "Item,Amount\nA,10\n\nB\nC,unknown\n")
    t = parse_file(p, p.name)[0]
    assert t["rows"] == [["A", "10"], ["B", None], ["C", "unknown"]]
    assert t["source_rows"] == [2, 4, 5]
    assert t["columns"][1]["type"] == "text"
    assert any("blank row" in w for w in t["warnings"])
    assert any("short row" in w for w in t["warnings"])
    with pytest.raises(ValueError, match="Non-numeric"):
        analyze(t, {"action": "sum", "column": "Amount"})


def test_xlsx_multiple_sheets_formula_hidden_data(tmp_path):
    book = Workbook()
    first = book.active
    first.title = "Sales"
    first.append(["Item", "Amount", "Calculated"])
    first.append(["A", 10, "=B2*2"])
    first.append(["B", 20, "=B3*2"])
    first.row_dimensions[3].hidden = True
    second = book.create_sheet("Other")
    second.append(["Name", "Value"])
    second.append(["Test", 4])
    second.sheet_state = "hidden"
    p = tmp_path / "book.xlsx"
    book.save(p)
    original = p.read_bytes()
    tables = parse_file(p, p.name)
    assert [t["name"] for t in tables] == ["Sales", "Other"]
    assert tables[0]["columns"][2]["formula"] is True
    assert tables[0]["rows"][0][2] == "=B2*2"
    assert analyze(tables[0], {"action": "sum", "column": "Amount"})["value"] == "30"
    assert any("Hidden rows" in w for w in tables[0]["warnings"])
    assert any("hidden" in w for w in tables[1]["warnings"])
    assert p.read_bytes() == original


def test_merged_workbook_rejected(tmp_path):
    book = Workbook()
    book.active.append(["A", "B"])
    book.active.append([1, 2])
    book.active.merge_cells("A2:B2")
    p = tmp_path / "merged.xlsx"
    book.save(p)
    with pytest.raises(ValueError, match="merged"):
        parse_file(p, p.name)


def test_unknown_formats_and_forged_xlsx(tmp_path):
    p = csv_file(tmp_path, "not an Excel file", "fake.xlsx")
    with pytest.raises(ValueError, match="XLSX"):
        parse_file(p, p.name)
    with pytest.raises(ValueError, match="Supported files"):
        parse_file(p, "file.xlsm")


def test_cell_column_and_size_limits(tmp_path):
    with pytest.raises(ValueError, match="50 columns"):
        make_table("wide", [[f"c{i}" for i in range(51)], ["1"] * 51], [1, 2])
    with pytest.raises(ValueError, match="10,000-character"):
        make_table("long", [["header"], ["x" * 10001]], [1, 2])
    p = tmp_path / "large.csv"
    with p.open("wb") as out:
        out.truncate(10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="10 MB"):
        parse_file(p, p.name)


def test_ambiguous_dates_and_subtotals_warn(tmp_path):
    p = csv_file(tmp_path, "Item,Date,Amount\nA,01/02/2026,10\nGrand Total,02/02/2026,10\n")
    t = parse_file(p, p.name)[0]
    assert t["columns"][1]["type"] == "text"
    assert any("ambiguous date" in w for w in t["warnings"])
    assert any("subtotal" in w for w in t["warnings"])
    assert len(t["rows"]) == 2


@pytest.mark.parametrize("image_index", range(10))
def test_ten_image_review_contracts(tmp_path, monkeypatch, image_index):
    """Generated-image boundary fixtures; this does NOT claim OCR recognition accuracy."""
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (600, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), "Item                  Amount", fill="black")
    draw.text((20, 70), f"Sample{image_index}              {image_index + 1}.25", fill="black")
    p = tmp_path / f"table-{image_index}.png"
    image.save(p)
    extracted = [["Item", "Amount"], [f"Sample{image_index}", f"{image_index + 1}.25"]]
    monkeypatch.setattr("app.ingestion._ocr_image", lambda path: (extracted, ["OCR proposal: verify every cell."]))
    t = parse_file(p, p.name)[0]
    assert t["requires_review"] is True
    assert t["confirmed"] is False
    assert t["rows"][0][1] == f"{image_index + 1}.25"
    assert any("OCR proposal" in w for w in t["warnings"])


def test_ocr_unavailable_is_actionable(tmp_path, monkeypatch):
    from PIL import Image
    p = tmp_path / "table.png"
    Image.new("RGB", (100, 100), "white").save(p)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr("app.ingestion.tesseract_command", lambda: None)
    with pytest.raises(ValueError, match="install Tesseract"):
        parse_file(p, p.name)


def test_validate_upload_bom_and_binary():
    from app.storage import validate_upload
    # Valid UTF-16 with BOM must be accepted
    utf16_content = "Item,Amount\nA,10\n".encode("utf-16")
    validate_upload("test.csv", utf16_content)

    # Binary file with null byte without BOM must be rejected
    with pytest.raises(ValueError, match="binary file"):
        validate_upload("test.csv", b"Item\x00Amount\n1,2\n")
