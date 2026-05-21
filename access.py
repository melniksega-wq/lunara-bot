from datetime import date


def _today() -> str:
    return date.today().isoformat()


def has_premium(chart: dict | None) -> bool:
    return bool(chart and chart.get("premium_unlocked"))


def question_balance(chart: dict | None) -> int:
    if not chart:
        return 0
    return int(chart.get("question_balance") or 0)


def can_ask_custom(chart: dict | None) -> bool:
    return question_balance(chart) > 0


def can_popular(chart: dict | None) -> bool:
    return has_premium(chart)


def can_compat(chart: dict | None) -> bool:
    return has_premium(chart)


def can_full_chart(chart: dict | None) -> bool:
    return has_premium(chart)


def horoscope_active(chart: dict | None) -> bool:
    if not chart:
        return False
    until = chart.get("horoscope_until") or ""
    if not until:
        return False
    return _today() <= until


def has_horo_today(chart: dict | None) -> bool:
    return bool(
        chart
        and chart.get("horoscope_type") == "today"
        and horoscope_active(chart)
    )


def horo_subscription_active(chart: dict | None) -> bool:
    return bool(
        chart
        and chart.get("horoscope_type") in ("week", "month")
        and horoscope_active(chart)
    )


def horo_status_line(chart: dict | None) -> str:
    if not chart:
        return ""
    parts = []
    if has_horo_today(chart):
        parts.append("✅ Прогноз «Сегодня» активен")
    if horo_subscription_active(chart):
        kind = "неделя" if chart["horoscope_type"] == "week" else "месяц"
        parts.append(f"✅ Подписка ({kind}) до {chart['horoscope_until']}")
    return "\n".join(parts) if parts else ""
