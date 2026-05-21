import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "lunara.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                birth_time TEXT NOT NULL,
                birth_place TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                is_premium INTEGER NOT NULL DEFAULT 0,
                free_reading TEXT,
                full_reading TEXT
            )
            """
        )
        for column, ddl in (
            ("is_premium", "INTEGER NOT NULL DEFAULT 0"),
            ("free_reading", "TEXT"),
            ("full_reading", "TEXT"),
        ):
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {ddl}")
            except sqlite3.OperationalError:
                pass
        conn.commit()


def save_user(
    telegram_id: int,
    name: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
) -> None:
    registered_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
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


def get_user(telegram_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    return dict(row) if row else None


def is_premium(telegram_id: int) -> bool:
    user = get_user(telegram_id)
    return bool(user and user.get("is_premium"))


def set_premium(telegram_id: int, premium: bool = True) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET is_premium = ? WHERE telegram_id = ?",
            (1 if premium else 0, telegram_id),
        )
        conn.commit()


def save_readings(
    telegram_id: int,
    *,
    free_reading: str | None = None,
    full_reading: str | None = None,
) -> None:
    with _connect() as conn:
        if free_reading is not None:
            conn.execute(
                "UPDATE users SET free_reading = ? WHERE telegram_id = ?",
                (free_reading, telegram_id),
            )
        if full_reading is not None:
            conn.execute(
                "UPDATE users SET full_reading = ? WHERE telegram_id = ?",
                (full_reading, telegram_id),
            )
        conn.commit()
