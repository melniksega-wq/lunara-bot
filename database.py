import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / "lunara.db"


def _add_column(c: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                birth_time TEXT NOT NULL,
                birth_place TEXT NOT NULL,
                is_premium INTEGER NOT NULL DEFAULT 0,
                free_reading TEXT,
                full_reading TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        _add_column(c, "users", "is_premium", "is_premium INTEGER NOT NULL DEFAULT 0")
        _add_column(c, "users", "free_reading", "free_reading TEXT")
        _add_column(c, "users", "full_reading", "full_reading TEXT")
        c.commit()


def upsert_user(tid: int, name: str, bdate: str, btime: str, bplace: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            INSERT INTO users (telegram_id, name, birth_date, birth_time, birth_place, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name=excluded.name, birth_date=excluded.birth_date,
                birth_time=excluded.birth_time, birth_place=excluded.birth_place
            """,
            (tid, name, bdate, btime, bplace, now),
        )
        c.commit()


def get_user(tid: int) -> dict | None:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()
    return dict(row) if row else None


def premium(tid: int) -> bool:
    u = get_user(tid)
    return bool(u and u["is_premium"])


def set_premium(tid: int, on: bool = True) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE users SET is_premium=? WHERE telegram_id=?", (1 if on else 0, tid))
        c.commit()


def save_texts(tid: int, free: str | None = None, full: str | None = None) -> None:
    with sqlite3.connect(DB) as c:
        if free is not None:
            c.execute("UPDATE users SET free_reading=? WHERE telegram_id=?", (free, tid))
        if full is not None:
            c.execute("UPDATE users SET full_reading=? WHERE telegram_id=?", (full, tid))
        c.commit()
