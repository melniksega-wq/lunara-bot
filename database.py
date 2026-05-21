import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "lunara.db"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                birth_time TEXT NOT NULL,
                birth_place TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_user(
    telegram_id: int,
    name: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
) -> None:
    registered_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO users (
                telegram_id, name, birth_date, birth_time, birth_place, registered_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name = excluded.name,
                birth_date = excluded.birth_date,
                birth_time = excluded.birth_time,
                birth_place = excluded.birth_place
            """,
            (telegram_id, name, birth_date, birth_time, birth_place, registered_at),
        )
        conn.commit()
