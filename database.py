import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DB = Path(__file__).resolve().parent / "lunara.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _charts_columns(c: sqlite3.Connection) -> set[str]:
    return {r[1] for r in c.execute("PRAGMA table_info(charts)")}


def _users_columns(c: sqlite3.Connection) -> set[str]:
    return {r[1] for r in c.execute("PRAGMA table_info(users)")}


def _add_column(c: sqlite3.Connection, table: str, col: str, ddl: str) -> None:
    cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_legacy_profiles(c: sqlite3.Connection) -> None:
    if "name" not in _users_columns(c):
        return
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
        if c.execute("SELECT 1 FROM charts WHERE user_id=?", (tid,)).fetchone():
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


def _migrate_user_entitlements_to_charts(c: sqlite3.Connection) -> None:
    """Перенос premium / вопросов / гороскопов с users на активную карту."""
    ucols = _users_columns(c)
    if "is_premium" not in ucols:
        return
    rows = c.execute(
        """
        SELECT telegram_id, active_chart_id, is_premium,
               custom_questions_left, horo_today_date,
               horo_sub_kind, horo_sub_days_total, horo_days_delivered,
               horo_last_sent_date
        FROM users
        WHERE active_chart_id IS NOT NULL
        """
    ).fetchall()
    today = _today()
    for row in rows:
        cid = row[1]
        if not cid:
            continue
        premium = 1 if row[2] else 0
        balance = int(row[3] or 0)
        h_type = ""
        h_until = ""
        if row[4] == today:
            h_type, h_until = "today", today
        elif row[5] in ("week", "month"):
            delivered = int(row[7] or 0)
            total = int(row[6] or 0)
            left = max(total - delivered, 0)
            days = left + (1 if row[8] == today else 0)
            if row[5] == "week":
                h_type = "week"
                days = max(days, 1)
                h_until = (date.today() + timedelta(days=days - 1)).isoformat()
            else:
                h_type = "month"
                days = max(days, 1)
                h_until = (date.today() + timedelta(days=days - 1)).isoformat()
        ccols = _charts_columns(c)
        sets = []
        vals = []
        if "premium_unlocked" in ccols and premium:
            sets.append("premium_unlocked=?")
            vals.append(premium)
        if "question_balance" in ccols and balance:
            sets.append("question_balance=?")
            vals.append(balance)
        if h_type and "horoscope_type" in ccols:
            sets.append("horoscope_type=?")
            vals.append(h_type)
            sets.append("horoscope_until=?")
            vals.append(h_until)
        if row[8] and "horo_last_sent_date" in ccols:
            sets.append("horo_last_sent_date=?")
            vals.append(row[8])
        if sets:
            vals.append(cid)
            c.execute(
                f"UPDATE charts SET {', '.join(sets)} WHERE id=?",
                vals,
            )


def init_db() -> None:
    now = _now()
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                active_chart_id INTEGER,
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
                premium_unlocked INTEGER NOT NULL DEFAULT 0,
                question_balance INTEGER NOT NULL DEFAULT 0,
                horoscope_until TEXT NOT NULL DEFAULT '',
                horoscope_type TEXT NOT NULL DEFAULT '',
                horo_last_sent_date TEXT NOT NULL DEFAULT '',
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
            ("created_at", "created_at TEXT NOT NULL DEFAULT ''"),
            ("registered_at", "registered_at TEXT NOT NULL DEFAULT ''"),
            ("name", "name TEXT NOT NULL DEFAULT ''"),
            ("birth_date", "birth_date TEXT NOT NULL DEFAULT ''"),
            ("birth_time", "birth_time TEXT NOT NULL DEFAULT ''"),
            ("birth_place", "birth_place TEXT NOT NULL DEFAULT ''"),
            ("free_reading", "free_reading TEXT"),
            ("full_reading", "full_reading TEXT"),
            ("is_premium", "is_premium INTEGER NOT NULL DEFAULT 0"),
            ("custom_questions_left", "custom_questions_left INTEGER NOT NULL DEFAULT 0"),
            ("horo_today_date", "horo_today_date TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_kind", "horo_sub_kind TEXT NOT NULL DEFAULT ''"),
            ("horo_sub_days_total", "horo_sub_days_total INTEGER NOT NULL DEFAULT 0"),
            ("horo_days_delivered", "horo_days_delivered INTEGER NOT NULL DEFAULT 0"),
            ("horo_last_sent_date", "horo_last_sent_date TEXT NOT NULL DEFAULT ''"),
        ):
            _add_column(c, "users", col, ddl)

        for col, ddl in (
            ("premium_unlocked", "premium_unlocked INTEGER NOT NULL DEFAULT 0"),
            ("question_balance", "question_balance INTEGER NOT NULL DEFAULT 0"),
            ("horoscope_until", "horoscope_until TEXT NOT NULL DEFAULT ''"),
            ("horoscope_type", "horoscope_type TEXT NOT NULL DEFAULT ''"),
            ("horo_last_sent_date", "horo_last_sent_date TEXT NOT NULL DEFAULT ''"),
            ("free_reading", "free_reading TEXT"),
            ("full_reading", "full_reading TEXT"),
        ):
            _add_column(c, "charts", col, ddl)

        _migrate_legacy_profiles(c)
        _migrate_user_entitlements_to_charts(c)

        if "created_at" in _users_columns(c):
            c.execute(
                "UPDATE users SET created_at = ? "
                "WHERE created_at IS NULL OR created_at = ''",
                (now,),
            )
        from analytics import init_analytics_tables

        init_analytics_tables()
        c.commit()


def ensure_user(tid: int) -> bool:
    now = _now()
    with sqlite3.connect(DB) as c:
        cols = _users_columns(c)
        if c.execute("SELECT 1 FROM users WHERE telegram_id=?", (tid,)).fetchone():
            return False
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
    from analytics import log_event

    log_event(tid, "registration")
    return True


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
                user_id, profile_name, birth_date, birth_time, birth_place,
                premium_unlocked, question_balance, horoscope_until, horoscope_type,
                created_at
            ) VALUES (?, ?, ?, ?, ?, 0, 0, '', '', ?)
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
    from analytics import log_event

    log_event(tid, "chart_created", chart_id=chart_id)
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


# ─── Доступ на уровне карты ────────────────────────────────────────────


def set_chart_premium(chart_id: int, on: bool = True) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE charts SET premium_unlocked=? WHERE id=?",
            (1 if on else 0, chart_id),
        )
        c.commit()


def add_chart_questions(chart_id: int, count: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            UPDATE charts SET question_balance = question_balance + ?
            WHERE id=?
            """,
            (count, chart_id),
        )
        c.commit()


def use_chart_question(chart_id: int) -> bool:
    with sqlite3.connect(DB) as c:
        row = c.execute(
            "SELECT question_balance FROM charts WHERE id=?", (chart_id,)
        ).fetchone()
        if not row or row[0] < 1:
            return False
        c.execute(
            "UPDATE charts SET question_balance = question_balance - 1 WHERE id=?",
            (chart_id,),
        )
        c.commit()
    return True


def grant_chart_horo(chart_id: int, kind: str, days: int) -> None:
    today = date.today()
    until = (today + timedelta(days=days - 1)).isoformat()
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            UPDATE charts SET
                horoscope_type=?,
                horoscope_until=?,
                horo_last_sent_date=''
            WHERE id=?
            """,
            (kind, until, chart_id),
        )
        c.commit()


def record_chart_horo_sent(chart_id: int) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            "UPDATE charts SET horo_last_sent_date=? WHERE id=?",
            (_today(), chart_id),
        )
        c.commit()


def get_horo_subscriber_charts() -> list[dict]:
    today = _today()
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """
            SELECT * FROM charts
            WHERE horoscope_type IN ('week', 'month')
              AND horoscope_until >= ?
              AND horo_last_sent_date != ?
            """,
            (today, today),
        ).fetchall()
    return [dict(r) for r in rows]


def horo_period_total(chart: dict) -> int:
    if chart.get("horoscope_type") == "week":
        return 7
    if chart.get("horoscope_type") == "month":
        return 30
    return 1


def horo_current_day(chart: dict) -> int:
    until_s = chart.get("horoscope_until") or _today()
    total = horo_period_total(chart)
    try:
        until = date.fromisoformat(until_s)
        start = until - timedelta(days=total - 1)
        return (date.today() - start).days + 1
    except ValueError:
        return 1
