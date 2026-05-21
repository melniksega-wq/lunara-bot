import asyncio
import logging
from datetime import date

from aiogram import Bot

from database import get_active_chart, get_horo_subscribers, record_horo_delivery
from services import PROMPT_HORO_DAILY, ask_ai, profile_text

log = logging.getLogger(__name__)


def _today() -> str:
    return date.today().isoformat()


async def send_daily_horo(bot: Bot, user: dict, day_num: int, total: int) -> None:
    tid = user["telegram_id"]
    chart = get_active_chart(tid)
    if not chart:
        log.warning("horo skip %s: no active chart", tid)
        return
    kind = user.get("horo_sub_kind") or "подписка"
    label = "неделя" if kind == "week" else "месяц"
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
            f"📅 Гороскоп · день {day_num}/{total}\n\n{text}",
        )
        record_horo_delivery(tid)
    except Exception as e:
        log.error("horo delivery %s: %s", tid, e)


async def deliver_due_horoscopes(bot: Bot) -> None:
    today = _today()
    for user in get_horo_subscribers():
        if user.get("horo_last_sent_date") == today:
            continue
        total = int(user["horo_sub_days_total"])
        delivered = int(user["horo_days_delivered"])
        if delivered >= total:
            continue
        await send_daily_horo(bot, user, delivered + 1, total)


async def horo_scheduler_loop(bot: Bot) -> None:
    await asyncio.sleep(30)
    while True:
        try:
            await deliver_due_horoscopes(bot)
        except Exception as e:
            log.error("horo scheduler: %s", e)
        await asyncio.sleep(3600)
