import sqlite3
from datetime import date
from pathlib import Path

DB = Path(__file__).resolve().parent / "lunara.db"


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def init_analytics_tables(conn: sqlite3.Connection | None = None) -> None:
    def _ddl(c: sqlite3.Connection) -> None:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chart_id INTEGER,
                event_type TEXT NOT NULL,
                meta TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chart_id INTEGER,
                product_type TEXT NOT NULL,
                amount_rub INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id)"
        )

    if conn is not None:
        _ddl(conn)
        return
    with sqlite3.connect(DB, timeout=30) as c:
        _ddl(c)
        c.commit()


def log_event(
    user_id: int,
    event_type: str,
    *,
    chart_id: int | None = None,
    meta: str = "",
) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            INSERT INTO events (user_id, chart_id, event_type, meta, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chart_id, event_type, meta, _now()),
        )
        c.commit()


def record_purchase(
    user_id: int,
    product_type: str,
    amount_rub: int,
    *,
    chart_id: int | None = None,
) -> None:
    with sqlite3.connect(DB) as c:
        c.execute(
            """
            INSERT INTO purchases (user_id, chart_id, product_type, amount_rub, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chart_id, product_type, amount_rub, _now()),
        )
        c.commit()
    log_event(user_id, f"purchase_{product_type}", chart_id=chart_id, meta=str(amount_rub))


def _users_columns(c: sqlite3.Connection) -> set[str]:
    return {r[1] for r in c.execute("PRAGMA table_info(users)")}


def _count_users_today(c: sqlite3.Connection, today: str) -> int:
    ucols = _users_columns(c)
    parts: list[str] = []
    params: list[str] = []
    for col in ("created_at", "registered_at"):
        if col in ucols:
            parts.append(f"substr({col}, 1, 10) = ?")
            params.append(today)
    if not parts:
        return 0
    return c.execute(
        f"SELECT COUNT(*) FROM users WHERE {' OR '.join(parts)}",
        params,
    ).fetchone()[0]


def get_admin_stats() -> dict:
    today = _today()
    with sqlite3.connect(DB) as c:
        users_total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        users_today = _count_users_today(c, today)
        if users_today == 0:
            users_today = c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM events "
                "WHERE event_type = 'registration' AND substr(created_at, 1, 10) = ?",
                (today,),
            ).fetchone()[0]

        charts_total = c.execute("SELECT COUNT(*) FROM charts").fetchone()[0]
        premium_charts = c.execute(
            "SELECT COUNT(*) FROM charts WHERE premium_unlocked = 1"
        ).fetchone()[0]
        purchases_count = c.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        revenue = c.execute(
            "SELECT COALESCE(SUM(amount_rub), 0) FROM purchases"
        ).fetchone()[0]

        users_with_chart = c.execute(
            "SELECT COUNT(DISTINCT user_id) FROM charts"
        ).fetchone()[0]
        users_premium = c.execute(
            """
            SELECT COUNT(DISTINCT user_id) FROM charts WHERE premium_unlocked = 1
            """
        ).fetchone()[0]

    conversion = 0.0
    if users_with_chart > 0:
        conversion = round(100.0 * users_premium / users_with_chart, 1)

    return {
        "users_total": users_total,
        "users_today": users_today,
        "charts_total": charts_total,
        "premium_charts": premium_charts,
        "purchases_count": purchases_count,
        "revenue": int(revenue),
        "conversion": conversion,
        "users_with_chart": users_with_chart,
        "users_premium": users_premium,
    }


def recent_events(limit: int = 15) -> list[dict]:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """
            SELECT e.*, u.telegram_id
            FROM events e
            LEFT JOIN users u ON u.telegram_id = e.user_id
            ORDER BY e.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_purchases(limit: int = 15) -> list[dict]:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM purchases ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def list_users_admin(limit: int = 20) -> list[dict]:
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            """
            SELECT u.telegram_id, u.active_chart_id,
                   (SELECT COUNT(*) FROM charts WHERE user_id = u.telegram_id) AS charts_count,
                   (SELECT COUNT(*) FROM charts WHERE user_id = u.telegram_id
                    AND premium_unlocked = 1) AS premium_count
            FROM users u
            ORDER BY u.telegram_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def all_user_ids() -> list[int]:
    with sqlite3.connect(DB) as c:
        rows = c.execute("SELECT telegram_id FROM users").fetchall()
    return [r[0] for r in rows]
