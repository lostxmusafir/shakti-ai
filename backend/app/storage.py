import io
import json
import os
from pathlib import Path
import zipfile

from PIL import Image

MAX_FILE = 10 * 1024 * 1024
MAX_IMAGE = 5 * 1024 * 1024
EXTENSIONS = {'.csv', '.xlsx', '.png', '.jpg', '.jpeg'}


def validate_upload(name: str, content: bytes):
    extension = Path(name).suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError('Supported files: CSV, XLSX, PNG and JPEG. Macros and legacy XLS are not supported.')
    if not content:
        raise ValueError('The file is empty.')
    limit = MAX_IMAGE if extension in {'.png', '.jpg', '.jpeg'} else MAX_FILE
    if len(content) > limit:
        raise ValueError(f'File exceeds the {limit // 1024 // 1024} MB limit.')
    if extension == '.xlsx':
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > 10000 or sum(x.file_size for x in infos) > 100 * 1024 * 1024:
                    raise ValueError('Workbook decompressed size is too large.')
                names = set(archive.namelist())
                if '[Content_Types].xml' not in names or 'xl/workbook.xml' not in names:
                    raise ValueError('This is not a valid XLSX workbook.')
                if any('vbaproject' in n.lower() or n.startswith('xl/externalLinks/') for n in names):
                    raise ValueError('Macros and external workbook links are unsupported. Upload a values-only XLSX.')
        except zipfile.BadZipFile as exc:
            raise ValueError('The XLSX file is invalid or damaged.') from exc
    elif extension in {'.png', '.jpg', '.jpeg'}:
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {'PNG', 'JPEG'} or image.width * image.height > 20_000_000:
                    raise ValueError('Use PNG/JPEG with no more than 20 million pixels.')
                image.verify()
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError('The image is invalid or too large.') from exc
    elif extension == '.csv':
        if content.startswith((b'\xff\xfe', b'\xfe\xff')):
            try:
                decoded = content.decode('utf-16')
                if '\x00' in decoded:
                    raise ValueError('CSV contains binary/null bytes.')
            except UnicodeDecodeError as exc:
                raise ValueError('Invalid UTF-16 CSV file.') from exc
        elif b'\x00' in content:
            raise ValueError('CSV must be UTF-8 text, not a binary file.')


def dataset_dir(settings, dataset_id):
    # IDs are generated server-side, never filenames supplied by a user.
    if len(dataset_id) != 32 or any(c not in '0123456789abcdef' for c in dataset_id):
        raise ValueError('Invalid dataset identifier.')
    base = (settings.data_dir / 'files').resolve()
    target = (base / dataset_id).resolve()
    if target.parent != base:
        raise ValueError('Invalid storage path.')
    return target


def version_path(settings, dataset_id, version):
    return dataset_dir(settings, dataset_id) / f'v{int(version)}.json'


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def read_tables(settings, dataset_id, version):
    return json.loads(version_path(settings, dataset_id, version).read_text(encoding='utf-8'))
