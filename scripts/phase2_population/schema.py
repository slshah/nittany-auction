from pathlib import Path

from db_utils import get_db_connection


def execute_sql_file(sql_file: Path) -> None:
    """Execute SQL script file against the configured SQLite database."""
    sql_text = sql_file.read_text(encoding="utf-8")
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.executescript(sql_text)
        connection.commit()
    finally:
        connection.close()


def create_schema(sql_file: Path) -> None:
    execute_sql_file(sql_file)
