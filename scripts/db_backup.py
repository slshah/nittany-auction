import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings


def resolve_project_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def backup_database(db_path: Path, output_dir: Path) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = db_path.suffix if db_path.suffix else ".db"
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = output_dir / f"{db_path.stem}-{timestamp}{suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a timestamped backup copy of the NittanyAuction SQLite database."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="SQLite DB path. Defaults to SQLITE_DB_PATH from environment.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backups"),
        help="Directory where backup files are written (default: backups/).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    settings = get_settings()

    raw_db_path = args.db_path if args.db_path else Path(settings.sqlite_db_path)
    db_path = resolve_project_path(raw_db_path)
    output_dir = resolve_project_path(args.output_dir)

    backup_path = backup_database(db_path=db_path, output_dir=output_dir)
    print(f"Backup created: {backup_path}")

