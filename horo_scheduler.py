import asyncio
import logging
from datetime import date

from aiogram import Bot

from database import (
    get_chart,
    get_horo_subscriber_charts,
    horo_current_day,
    horo_period_total,
    record_chart_horo_sent,
)
from services import PROMPT_HORO_DAILY, ask_ai, profile_text

log = logging.getLogger(__name__)


def _today() -> str:
    return date.today().isoformat()


async def send_daily_horo(bot: Bot, chart: dict) -> None:
    tid = chart["user_id"]
    chart_id = chart["id"]
    kind = chart.get("horoscope_type") or "подписка"
    label = "неделя" if kind == "week" else "месяц"
    day_num = horo_current_day(chart)
    total = horo_period_total(chart)
    try:
        text = await ask_ai(
            PROMPT_HORO_DAILY,
            (
                f"Подписка: {label}, день {day_num} из {total}.\n"
                f"Дата: {_today()}\n\n{profile_text(chart)}"
            ),
        )
        await bot.send_message(
            tid,
            f"📅 {chart['profile_name']} · день {day_num}/{total}\n\n{text}",
        )
        record_chart_horo_sent(chart_id)
    except Exception as e:
        log.error("horo delivery chart=%s: %s", chart_id, e)


async def deliver_due_horoscopes(bot: Bot) -> None:
    for chart in get_horo_subscriber_charts():
        fresh = get_chart(chart["id"]) or chart
        await send_daily_horo(bot, fresh)


async def horo_scheduler_loop(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            await deliver_due_horoscopes(bot)
        except Exception as e:
            log.error("horo scheduler: %s", e)
        await asyncio.sleep(3600)
