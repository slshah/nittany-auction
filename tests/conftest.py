import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_utils import get_db_connection
from password_utils import hash_password_sha256
from scripts.phase2_population.schema import create_schema


@pytest.fixture()
def client(monkeypatch, tmp_path):
    db_path = tmp_path / "test_nittanyauction.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(db_path))
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("FLASK_DEBUG", "0")

    create_schema(Path("sql/schema_phase2.sql"))

    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.executemany(
            """
            INSERT INTO auth_users (email, hashed_password, role)
            VALUES (?, ?, ?)
            """,
            [
                ("seller@test.edu", hash_password_sha256("seller-pass"), "seller"),
                ("bidder@test.edu", hash_password_sha256("bidder-pass"), "Bidder"),
                ("helpdesk@test.edu", hash_password_sha256("helpdesk-pass"), "helpdesk"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    import app as app_module

    app_module = importlib.reload(app_module)
    app_module.app.config.update(TESTING=True)

    with app_module.app.test_client() as test_client:
        yield test_client
