import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings
from scripts.phase2_population.reporting import print_report
from scripts.phase2_population.runner import populate_phase2
from scripts.phase2_population.schema import create_schema


def resolve_project_path(path: Path) -> Path:
    """Resolve relative paths so this script works from any directory."""
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def reset_phase2_database(
    schema_file: Path,
    db_path: Path,
    dataset_dir: Path,
    strict: bool,
) -> None:
    """Recreate the Phase 2 DB and load the full CSV dataset."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    # Ensure shared DB helpers target this DB path.
    os.environ["SQLITE_DB_PATH"] = str(db_path)

    create_schema(schema_file)
    result = populate_phase2(
        dataset_dir=dataset_dir,
        truncate=True,
        strict=strict,
    )
    print_report(result)
    if strict and not result.is_clean:
        raise RuntimeError("populate_phase2 strict validation failed")


def parse_args():
    """Parse CLI options for full reset + full population."""
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the Phase 2 database from schema_phase2.sql and load the full "
            "CSV dataset."
        )
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path("sql/schema_phase2.sql"),
        help="Path to schema SQL file (default: sql/schema_phase2.sql).",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="SQLite DB path. Defaults to SQLITE_DB_PATH from environment.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("NittanyAuctionDataset_v1"),
        help="Dataset directory containing Phase 2 CSV files.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help=(
            "Do not fail when rejected rows or integrity issues are found. "
            "By default strict validation is enabled."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    settings = get_settings()

    raw_db_path = args.db_path if args.db_path else Path(settings.sqlite_db_path)
    db_path = resolve_project_path(raw_db_path)
    schema_file = resolve_project_path(args.schema_file)
    dataset_dir = resolve_project_path(args.dataset_dir)

    reset_phase2_database(
        schema_file=schema_file,
        db_path=db_path,
        dataset_dir=dataset_dir,
        strict=not args.no_strict,
    )

    if args.no_strict:
        print(f"Phase 2 database reset + full population completed at: {db_path}")
    else:
        print(
            f"Phase 2 database reset + full strict population completed at: {db_path}"
        )
