import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    sqlite_db_path: str
    flask_secret_key: str
    flask_debug: bool


def to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    return Settings(
        sqlite_db_path=os.getenv("SQLITE_DB_PATH", "nittanyauction.db"),
        flask_secret_key=os.getenv("FLASK_SECRET_KEY", "dev-only-change-me"),
        flask_debug=to_bool(os.getenv("FLASK_DEBUG"), default=False),
    )
