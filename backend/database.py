import sqlite3
from pathlib import Path

STATE_DIR = Path("/state")
DATABASE_PATH = STATE_DIR / "users.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',

                imap_username TEXT NOT NULL UNIQUE,
                imap_password_hash TEXT NOT NULL,
                is_guest INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS oauth_identities (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_subject TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL,

                PRIMARY KEY(provider, provider_subject),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )

        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "is_guest" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 0"
            )
