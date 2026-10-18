import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from db_utils import get_db_connection

from .common import (
    collect_db_row_counts,
    collect_fk_issues,
    load_role_memberships,
    truncate_existing_data,
)
from .loaders import (
    load_address,
    load_auction_listings,
    load_bidders,
    load_bids,
    load_categories,
    load_credit_cards,
    load_helpdesk,
    load_local_vendors,
    load_ratings,
    load_requests,
    load_sellers,
    load_transactions,
    load_users,
    load_zipcode_info,
)
from .models import PopulationResult, TableLoadStats

Loader = Callable[[sqlite3.Cursor, Path], TableLoadStats]

LOAD_SEQUENCE: List[Tuple[str, Loader]] = [
    ("zipcode_info", load_zipcode_info),
    ("address", load_address),
    ("bidders", load_bidders),
    ("sellers", load_sellers),
    ("helpdesk", load_helpdesk),
    ("credit_cards", load_credit_cards),
    ("local_vendors", load_local_vendors),
    ("categories", load_categories),
    ("auction_listings", load_auction_listings),
    ("bids", load_bids),
    ("transactions", load_transactions),
    ("ratings", load_ratings),
    ("requests", load_requests),
]


def populate_phase2(
    dataset_dir: Path,
    truncate: bool = True,
    strict: bool = True,
) -> PopulationResult:
    """
    Load the full Phase 2 dataset and run post-load integrity checks.

    In strict mode, any rejected row or integrity issue triggers a rollback so we
    never leave the DB in a half-populated state.
    """
    memberships = load_role_memberships(dataset_dir)

    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        if truncate:
            truncate_existing_data(cursor)

        table_stats: Dict[str, TableLoadStats] = {}

        users_stats, auth_stats = load_users(cursor, dataset_dir, memberships)
        table_stats["users"] = users_stats
        table_stats["auth_users"] = auth_stats

        for table_name, loader in LOAD_SEQUENCE:
            table_stats[table_name] = loader(cursor, dataset_dir)

        db_row_counts = collect_db_row_counts(cursor, table_stats)
        row_count_mismatches = {}
        for table_name, stats in table_stats.items():
            actual = db_row_counts[table_name]
            expected = stats.loaded_rows
            if actual != expected:
                row_count_mismatches[table_name] = (
                    f"expected {expected} rows from load stats, found {actual}"
                )

        fk_issues = collect_fk_issues(cursor)

        result = PopulationResult(
            table_stats=table_stats,
            db_row_counts=db_row_counts,
            row_count_mismatches=row_count_mismatches,
            fk_issues=fk_issues,
        )

        if strict and not result.is_clean:
            # Keep population all or nothing when strict mode is requested.
            connection.rollback()
            return result

        connection.commit()
        return result
    finally:
        connection.close()
