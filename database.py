import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / "lunara.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _users_columns(c: sqlite3.Connection) -> set[str]:
    return {r[1] for r in c.execute("PRAGMA table_info(users)")}


def _add_column(c: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_legacy_profiles(c: sqlite3.Connection) -> None:
    """Перенос старых профилей из users в charts."""
    rows = c.execute(
        """
        SELECT telegram_id, name, birth_date, birth_time, birth_place,
               free_reading, full_reading, created_at, registered_at
        FROM users
        WHERE birth_place IS NOT NULL AND birth_place != ''
          AND name IS NOT NULL AND name != ''
        """
    ).fetchall()
    for row in rows:
        tid = row[0]
        exists = c.execute(
            "SELECT 1 FROM charts WHERE user_id=?", (tid,)
        ).fetchone()
        if exists:
            continue
        created = row[7] or row[8] or _now()
        cur = c.execute(
            """
            INSERT INTO charts (
                user_id, profile_name, birth_date, birth_time, birth_place,
                free_reading, full_reading, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tid, row[1], row[2], row[3], row[4], row[5], row[6], created),
        )
        chart_id = cur.lastrowid
        c.execute(
            "UPDATE users SET active_chart_id=? WHERE telegram_id=?",
            (chart_id, tid),
        )


def init_db() -> None:
    now = _now()
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                active_chart_id INTEGER,
                is_premium INTEGER NOT NULL DEFAULT 0,
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
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS charts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                profile_name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                birth_time TEXT NOT NULL,
                birth_place TEXT NOT NULL,
                free_reading TEXT,
                full_reading TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_charts_user ON charts(user_id)"
        )

        for col, ddl in (
            ("active_chart_id", "active_chart_id INTEGER"),
            ("is_premium", "is_premium INTEGER NOT NULL DEFAULT 0"),
            ("custom_questions_left", "custom_questions_left INTEGER NOT NULL DEFAULT 0"),
            ("horo_today_date", "horo_today_date TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_kind", "horo_sub_kind TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_days_total", "horo_sub_days_total INTEGER NOT NULL DEFAULT 0"),
            ("horo_days_delivered", "horo_days_delivered INTEGER NOT NULL DEFAULT 0"),
            ("horo_last_sent_date", "horo_last_sent_date TEXT NOT NULL DEFAULT ''"),
            ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
            ("registered_at", "registered_at TEXT NOT NULL DEFAULT ''"),
            # legacy — для миграции
            ("name", "name TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "birth_date TEXT NOT NULL DEFAULT ''"),
            ("birth_time", "birth_time TEXT NOT NULL DEFAULT ''"),
            ("birth_place", "birth_place TEXT NOT NULL DEFAULT ''"),
            ("free_reading", "free_reading TEXT"),
            ("full_reading", "full_reading TEXT"),
        ):
            _add_column(c, "users", col, ddl)

        _migrate_legacy_profiles(c)

        cols = _users_columns(c)
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
        c.commit()


def ensure_user(tid: int) -> None:
    now = _now()
    with sqlite3.connect(DB) as c:
        cols = _users_columns(c)
        row = c.execute(
            "SELECT 1 FROM users WHERE telegram_id=?", (tid,)
        ).fetchone()
        if row:
            return
        stamps: dict = {"telegram_id": tid}
        for leg in ("name", "birth_date", "birth_time", "birth_place"):
            if leg in cols:
                stamps[leg] = ""
        if "created_at" in cols:
            stamps["created_at"] = now
        if "registered_at" in cols:
            stamps["registered_at"] = now
        keys = list(stamps.keys())
        c.execute(
            f"INSERT INTO users ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
            [stamps[k] for k in keys],
        )
        c.commit()


def get_user(tid: int) -> dict | None:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        row = c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()
    return dict(row) if row else None


def list_charts(tid: int) -> list[dict]:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM charts WHERE user_id=? ORDER BY id DESC",
            (tid,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_chart(chart_id: int, tid: int | None = None) -> dict | None:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        if tid is not None:
            row = c.execute(
                "SELECT * FROM charts WHERE id=? AND user_id=?",
                (chart_id, tid),
            ).fetchone()
        else:
            row = c.execute("SELECT * FROM charts WHERE id=?", (chart_id,)).fetchone()
    return dict(row) if row else None


def get_active_chart(tid: int) -> dict | None:
    u = get_user(tid)
    if not u or not u.get("active_chart_id"):
        return None
    return get_chart(int(u["active_chart_id"]), tid)


def set_active_chart(tid: int, chart_id: int) -> bool:
    chart = get_chart(chart_id, tid)
    if not chart:
        return False
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE users SET active_chart_id=? WHERE telegram_id=?",
            (chart_id, tid),
        )
        c.commit()
    return True


def has_any_chart(tid: int) -> bool:
    with sqlite3.connect(DB) as c:
        row = c.execute(
            "SELECT 1 FROM charts WHERE user_id=? LIMIT 1", (tid,)
        ).fetchone()
    return bool(row)


def is_profile_complete(tid: int) -> bool:
    return get_active_chart(tid) is not None


def create_chart(
    tid: int,
    profile_name: str,
    birth_date: str,
    birth_time: str,
    birth_place: str,
) -> dict:
    ensure_user(tid)
    now = _now()
    with sqlite3.connect(DB) as c:
        cur = c.execute(
            """
            INSERT INTO charts (
                user_id, profile_name, birth_date, birth_time, birth_place, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tid, profile_name, birth_date, birth_time, birth_place, now),
        )
        chart_id = cur.lastrowid
        c.execute(
            "UPDATE users SET active_chart_id=? WHERE telegram_id=?",
            (chart_id, tid),
        )
        c.commit()
    chart = get_chart(chart_id, tid)
    assert chart is not None
    return chart


def save_chart_texts(
    chart_id: int,
    *,
    free: str | None = None,
    full: str | None = None,
) -> None:
    with sqlite3.connect(DB) as c:
        if free is not None:
            c.execute(
                "UPDATE charts SET free_reading=? WHERE id=?", (free, chart_id)
            )
        if full is not None:
            c.execute(
                "UPDATE charts SET full_reading=? WHERE id=?", (full, chart_id)
            )
        c.commit()


# ─── Аккаунт: premium, вопросы, гороскопы (на telegram_id) ─────────────


def set_premium(tid: int, on: bool = True) -> None:
    ensure_user(tid)
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE users SET is_premium=? WHERE telegram_id=?",
            (1 if on else 0, tid),
        )
        c.commit()


def add_custom_questions(tid: int, count: int) -> None:
    ensure_user(tid)
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
    ensure_user(tid)
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE users SET horo_today_date=? WHERE telegram_id=?",
            (_today(), tid),
        )
        c.commit()


def grant_horo_subscription(tid: int, kind: str, days: int) -> None:
    ensure_user(tid)
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
