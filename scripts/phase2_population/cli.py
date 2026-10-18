import argparse
import os
import sqlite3
from pathlib import Path

from .reporting import print_report
from .runner import populate_phase2

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_args():
    """Parse CLI args for Phase 2 population runs."""
    parser = argparse.ArgumentParser(
        description=(
            "Populate the full Phase 2 NittanyAuction schema from CSVs and "
            "print ETL/integrity reports."
        )
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("NittanyAuctionDataset_v1"),
        help="Dataset directory containing all Phase 2 CSV files.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="SQLite DB path. Defaults to SQLITE_DB_PATH from environment.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail with exit code 1 if any row is rejected or integrity checks fail. "
            "If omitted, script reports issues but still exits 0."
        ),
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    """Resolve relative paths from repo root so scripts work from any wd."""
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def main() -> int:
    """Run population from CLI and return a shell friendly exit code."""
    args = parse_args()
    if args.db_path:
        os.environ["SQLITE_DB_PATH"] = str(resolve_project_path(args.db_path))

    dataset_dir = resolve_project_path(args.dataset_dir)
    try:
        result = populate_phase2(
            dataset_dir=dataset_dir,
            truncate=True,
            strict=args.strict,
        )
    except sqlite3.OperationalError as exc:
        print(f"Population failed: {exc}")
        print("Run `python scripts/reset_phase2.py` first.")
        return 1

    print_report(result)

    if args.strict and not result.is_clean:
        print("\nPopulation failed in strict mode.")
        return 1

    print("\nPopulation completed.")
    return 0
