from dataclasses import dataclass
from pathlib import Path
import os
import shutil


@dataclass
class Settings:
    data_dir: Path
    api_key: str = ''
    base_url: str = ''
    model: str = 'ministral-8b-latest'
    cloud_enabled: bool = True
    job_timeout: int = 120
    daily_cloud_limit: int = 200
    session_hours: int = 12

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=False)
        default = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'ZydrakonAI'

        mistral_key = os.environ.get('MISTRAL_API_KEY', '')
        openai_key = os.environ.get('OPENAI_API_KEY', '')
        api_key = mistral_key or openai_key

        base_url = os.environ.get('MISTRAL_BASE_URL') or os.environ.get('OPENAI_BASE_URL', '')
        if not base_url and mistral_key:
            base_url = 'https://api.mistral.ai/v1'

        model = os.environ.get('MISTRAL_MODEL') or os.environ.get('OPENAI_MODEL')
        if not model:
            model = 'ministral-8b-latest' if mistral_key else 'gpt-6-luna'

        return cls(
            data_dir=Path(os.environ.get('ZYDRAKON_DATA_DIR', str(default))).resolve(),
            api_key=api_key,
            base_url=base_url,
            model=model,
            cloud_enabled=os.environ.get('ZYDRAKON_CLOUD_ENABLED', 'true').lower() == 'true',
            job_timeout=max(10, min(600, int(os.environ.get('ZYDRAKON_JOB_TIMEOUT', '120')))),
            daily_cloud_limit=max(1, int(os.environ.get('ZYDRAKON_DAILY_CLOUD_LIMIT', '200'))),
        )

    @property
    def db_url(self):
        return 'sqlite:///' + str(self.data_dir / 'zydrakon.db')

    @property
    def configured(self):
        return self.cloud_enabled and bool(self.api_key)


def tesseract_command():
    explicit = os.environ.get('TESSERACT_CMD')
    candidates = [explicit, shutil.which('tesseract'), r'C:\Program Files\Tesseract-OCR\tesseract.exe']
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)
