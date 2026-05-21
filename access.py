from datetime import date, datetime, timezone

from database import get_user


def _today() -> str:
    return date.today().isoformat()


def has_premium(u: dict | None) -> bool:
    return bool(u and u.get("is_premium"))


def custom_questions_left(u: dict | None) -> int:
    if not u:
        return 0
    return int(u.get("custom_questions_left") or 0)


def can_ask_custom(u: dict | None) -> bool:
    return custom_questions_left(u) > 0


def can_popular(u: dict | None) -> bool:
    return has_premium(u)


def can_compat(u: dict | None) -> bool:
    return has_premium(u)


def can_full_chart(u: dict | None) -> bool:
    return has_premium(u)


def has_horo_today(u: dict | None) -> bool:
    return bool(u and u.get("horo_today_date") == _today())


def horo_subscription_active(u: dict | None) -> bool:
    if not u or not u.get("horo_sub_kind"):
        return False
    total = int(u.get("horo_sub_days_total") or 0)
    delivered = int(u.get("horo_days_delivered") or 0)
    return delivered < total


def horo_status_line(u: dict | None) -> str:
    if not u:
        return ""
    parts = []
    if has_horo_today(u):
        parts.append("✅ Сегодня куплен")
    if horo_subscription_active(u):
        left = int(u["horo_sub_days_total"]) - int(u["horo_days_delivered"])
        kind = "неделя" if u["horo_sub_kind"] == "week" else "месяц"
        parts.append(f"✅ Подписка ({kind}): осталось {left} дн.")
    return "\n".join(parts) if parts else ""
