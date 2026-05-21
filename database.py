import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / "lunara.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _table_columns(c: sqlite3.Connection) -> set[str]:
    return {r[1] for r in c.execute("PRAGMA table_info(users)")}


def _add_column(c: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    if col not in _table_columns(c):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    now = _now()
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                birth_date TEXT NOT NULL DEFAULT '',
                birth_time TEXT NOT NULL DEFAULT '',
                birth_place TEXT NOT NULL DEFAULT '',
                is_premium INTEGER NOT NULL DEFAULT 0,
                free_reading TEXT,
                full_reading TEXT,
                custom_questions_left INTEGER NOT NULL DEFAULT 0,
                horo_today_date TEXT NOT NULL DEFAULT '',
                horo_sub_kind TEXT NOT NULL DEFAULT '',
                horo_sub_days_total INTEGER NOT NULL DEFAULT 0,
                horo_days_delivered INTEGER NOT NULL DEFAULT 0,
                horo_last_sent_date TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                registered_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        migrations = (
            ("name", "name TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "birth_date TEXT NOT NULL DEFAULT ''"),
            ("birth_time", "birth_time TEXT NOT NULL DEFAULT ''"),
            ("birth_place", "birth_place TEXT NOT NULL DEFAULT ''"),
            ("is_premium", "is_premium INTEGER NOT NULL DEFAULT 0"),
            ("free_reading", "free_reading TEXT"),
            ("full_reading", "full_reading TEXT"),
            ("custom_questions_left", "custom_questions_left INTEGER NOT NULL DEFAULT 0"),
            ("horo_today_date", "horo_today_date TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_kind", "horo_sub_kind TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_days_total", "horo_sub_days_total INTEGER NOT NULL DEFAULT 0"),
            ("horo_days_delivered", "horo_days_delivered INTEGER NOT NULL DEFAULT 0"),
            ("horo_last_sent_date", "horo_last_sent_date TEXT NOT NULL DEFAULT ''"),
            ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
            ("registered_at", "registered_at TEXT NOT NULL DEFAULT ''"),
        )
        for col, ddl in migrations:
            _add_column(c, "users", col, ddl)

        cols = _table_columns(c)
        if "created_at" in cols:
            c.execute(
                "UPDATE users SET created_at = ? "
                "WHERE created_at IS NULL OR created_at = ''",
                (now,),
            )
        if "registered_at" in cols:
            c.execute(
                "UPDATE users SET registered_at = ? "
                "WHERE registered_at IS NULL OR registered_at = ''",
                (now,),
            )
        if "created_at" in cols and "registered_at" in cols:
            c.execute(
                """
                UPDATE users SET created_at = registered_at
                WHERE (created_at IS NULL OR created_at = '')
                  AND registered_at IS NOT NULL AND registered_at != ''
                """
            )
            c.execute(
                """
                UPDATE users SET registered_at = created_at
                WHERE (registered_at IS NULL OR registered_at = '')
                  AND created_at IS NOT NULL AND created_at != ''
                """
            )
        c.commit()


def _stamp_fields(cols: set[str], now: str) -> dict[str, str]:
    stamps: dict[str, str] = {}
    if "created_at" in cols:
        stamps["created_at"] = now
    if "registered_at" in cols:
        stamps["registered_at"] = now
    return stamps


def is_profile_complete(u: dict | None) -> bool:
    if not u:
        return False
    return bool(
        u.get("name")
        and u.get("birth_date")
        and u.get("birth_time")
        and u.get("birth_place")
    )


def save_progress(
    tid: int,
    *,
    name: str | None = None,
    birth_date: str | None = None,
    birth_time: str | None = None,
    birth_place: str | None = None,
) -> None:
    fields = {
        k: v
        for k, v in {
            "name": name,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "birth_place": birth_place,
        }.items()
        if v is not None
    }
    if not fields:
        return

    now = _now()
    with sqlite3.connect(DB) as c:
        cols = _table_columns(c)
        exists = c.execute(
            "SELECT 1 FROM users WHERE telegram_id=?", (tid,)
        ).fetchone()
        if exists:
            sets = ", ".join(f"{k}=?" for k in fields)
            c.execute(
                f"UPDATE users SET {sets} WHERE telegram_id=?",
                (*fields.values(), tid),
            )
        else:
            row = {
                "telegram_id": tid,
                "name": fields.get("name", ""),
                "birth_date": fields.get("birth_date", ""),
                "birth_time": fields.get("birth_time", ""),
                "birth_place": fields.get("birth_place", ""),
                **_stamp_fields(cols, now),
            }
            keys = [k for k in row if k in cols]
            c.execute(
                f"INSERT INTO users ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
                [row[k] for k in keys],
            )
        c.commit()


def upsert_user(tid: int, name: str, bdate: str, btime: str, bplace: str) -> None:
    now = _now()
    with sqlite3.connect(DB) as c:
        cols = _table_columns(c)
        stamps = _stamp_fields(cols, now)
        base = {
            "telegram_id": tid,
            "name": name,
            "birth_date": bdate,
            "birth_time": btime,
            "birth_place": bplace,
            **stamps,
        }
        keys = [k for k in base if k in cols]
        updates = ", ".join(
            f"{k}=excluded.{k}" for k in keys if k != "telegram_id" and k not in stamps
        )
        c.execute(
            f"""
            INSERT INTO users ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})
            ON CONFLICT(telegram_id) DO UPDATE SET {updates}
            """,
            [base[k] for k in keys],
        )
        c.commit()


def get_user(tid: int) -> dict | None:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()
    return dict(row) if row else None


def set_premium(tid: int, on: bool = True) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE users SET is_premium=? WHERE telegram_id=?",
            (1 if on else 0, tid),
        )
        c.commit()


def add_custom_questions(tid: int, count: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            UPDATE users SET custom_questions_left = custom_questions_left + ?
            WHERE telegram_id=?
            """,
            (count, tid),
        )
        c.commit()


def use_custom_question(tid: int) -> bool:
    with sqlite3.connect(DB) as c:
        row = c.execute(
            "SELECT custom_questions_left FROM users WHERE telegram_id=?", (tid,)
        ).fetchone()
        if not row or row[0] < 1:
            return False
        c.execute(
            """
            UPDATE users SET custom_questions_left = custom_questions_left - 1
            WHERE telegram_id=?
            """,
            (tid,),
        )
        c.commit()
    return True


def grant_horo_today(tid: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE users SET horo_today_date=? WHERE telegram_id=?",
            (_today(), tid),
        )
        c.commit()


def grant_horo_subscription(tid: int, kind: str, days: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            UPDATE users SET
                horo_sub_kind=?,
                horo_sub_days_total=?,
                horo_days_delivered=0,
                horo_last_sent_date=''
            WHERE telegram_id=?
            """,
            (kind, days, tid),
        )
        c.commit()


def record_horo_delivery(tid: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            UPDATE users SET
                horo_days_delivered = horo_days_delivered + 1,
                horo_last_sent_date=?
            WHERE telegram_id=?
            """,
            (_today(), tid),
        )
        c.commit()


def get_horo_subscribers() -> list[dict]:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """
            SELECT * FROM users
            WHERE horo_sub_kind != ''
              AND horo_days_delivered < horo_sub_days_total
            """
        ).fetchall()
    return [dict(r) for r in rows]


def save_texts(tid: int, free: str | None = None, full: str | None = None) -> None:
    with sqlite3.connect(DB) as c:
        if free is not None:
            c.execute(
                "UPDATE users SET free_reading=? WHERE telegram_id=?", (free, tid)
            )
        if full is not None:
            c.execute(
                "UPDATE users SET full_reading=? WHERE telegram_id=?", (full, tid)
            )
        c.commit()
