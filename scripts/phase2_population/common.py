import csv
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Set

from auth_utils import normalize_email

from .constants import ROLE_FILE_MAP, ROLE_PRIORITY, SEQUENCE_RESET_TABLES, TABLE_DELETE_ORDER
from .models import TableLoadStats


def read_csv_rows(dataset_dir: Path, filename: str) -> Iterable[dict]:
    """Stream rows from a dataset CSV as dictionaries."""
    with (dataset_dir / filename).open(newline="", encoding="utf-8-sig") as file_obj:
        # utf-8-sig lets us handle files that include a BOM in the first header.
        reader = csv.DictReader(file_obj)
        for row in reader:
            yield row


def clean_text(value) -> str:
    return (value or "").strip()


def parse_int(value, field_name: str) -> int:
    text = clean_text(value)
    if not text:
        raise ValueError(f"missing {field_name}")
    return int(text)


def parse_float(value, field_name: str) -> float:
    text = clean_text(value)
    if not text:
        raise ValueError(f"missing {field_name}")
    normalized = text.replace("$", "").replace(",", "").strip()
    return float(normalized)


def parse_mapped_status(value, mapping: Dict[str, int], field_name: str) -> int:
    text = clean_text(value)
    if not text:
        raise ValueError(f"missing {field_name}")
    normalized_key = text.lower()
    if normalized_key not in mapping:
        raise ValueError(f"unsupported {field_name}: {text}")
    return mapping[normalized_key]


def load_email_set(dataset_dir: Path, filename: str, field_name: str) -> Set[str]:
    emails: Set[str] = set()
    for row in read_csv_rows(dataset_dir, filename):
        email = normalize_email(row.get(field_name))
        if email:
            emails.add(email)
    return emails


def load_role_memberships(dataset_dir: Path) -> Dict[str, Set[str]]:
    """Load role membership email sets used for auth role assignment."""
    return {
        "seller": load_email_set(dataset_dir, ROLE_FILE_MAP["seller"], "email"),
        "bidder": load_email_set(dataset_dir, ROLE_FILE_MAP["bidder"], "email"),
        "helpdesk": load_email_set(dataset_dir, ROLE_FILE_MAP["helpdesk"], "email"),
    }


def choose_role(email: str, memberships: Dict[str, Set[str]]) -> str:
    for role in ROLE_PRIORITY:
        if email in memberships[role]:
            return role
    return "unsupported"


def truncate_existing_data(cursor: sqlite3.Cursor) -> None:
    """Clear all populated Phase 2 tables in FK safe reverse dependency order."""
    for table_name in TABLE_DELETE_ORDER:
        cursor.execute(f"DELETE FROM {table_name}")

    quoted_names = ", ".join(f"'{table}'" for table in SEQUENCE_RESET_TABLES)
    cursor.execute(
        f"""
        DELETE FROM sqlite_sequence
        WHERE name IN ({quoted_names})
        """
    )


def collect_db_row_counts(
    cursor: sqlite3.Cursor,
    table_stats: Dict[str, TableLoadStats],
) -> Dict[str, int]:
    counts = {}
    for table_name in table_stats:
        counts[table_name] = cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
    return counts


def collect_fk_issues(cursor: sqlite3.Cursor) -> List[str]:
    issues = []
    for row in cursor.execute("PRAGMA foreign_key_check").fetchall():
        issues.append(
            f"table={row[0]}, rowid={row[1]}, parent={row[2]}, fk_index={row[3]}"
        )
    return issues
