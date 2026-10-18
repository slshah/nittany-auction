import sqlite3

from config import get_settings


def get_db_connection():
    settings = get_settings()
    connection = sqlite3.connect(settings.sqlite_db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
