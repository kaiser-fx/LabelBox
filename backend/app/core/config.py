from pathlib import Path
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "LabelBox"
    app_version: str = "0.1.0"
    database_url: str = ""
    jwt_secret_key: str = "labelbox-super-secret-key-change-in-production-2026"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours for inspection shifts

    model_config = {
        "env_file": [str(ENV_FILE), ".env"],
        "extra": "ignore",
    }



settings = Settings()
