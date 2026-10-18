from pathlib import Path

from db_utils import get_db_connection
from scripts.phase2_population import ROOT_CATEGORY_NAME, populate_phase2
from scripts.phase2_population.schema import create_schema


def test_populate_phase2_strict_loads_dataset(monkeypatch, tmp_path):
    db_path = tmp_path / "phase2_populated.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))

    create_schema(Path("sql/schema_phase2.sql"))
    result = populate_phase2(
        dataset_dir=Path("NittanyAuctionDataset_v1"),
        truncate=True,
        strict=True,
    )

    assert result.is_clean
    assert result.total_rejected_rows == 0
    assert result.row_count_mismatches == {}
    assert result.fk_issues == []

    connection = get_db_connection()
    try:
        cursor = connection.cursor()

        root_category = cursor.execute(
            """
            SELECT category_name, parent_category
            FROM categories
            WHERE category_name = ?
            """,
            (ROOT_CATEGORY_NAME,),
        ).fetchone()
        assert root_category is not None
        assert root_category["parent_category"] is None

        listings_status_count = cursor.execute(
            """
            SELECT COUNT(*)
            FROM auction_listings
            WHERE status IN (0, 1, 2)
            """
        ).fetchone()[0]
        assert listings_status_count == result.db_row_counts["auction_listings"]

        assert result.db_row_counts["bidders"] > 0
        assert result.db_row_counts["sellers"] > 0
        assert result.db_row_counts["transactions"] > 0

        queue_user = cursor.execute(
            "SELECT 1 FROM users WHERE email = 'helpdeskteam@lsu.edu'"
        ).fetchone()
        assert queue_user is not None
    finally:
        connection.close()
