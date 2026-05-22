import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from analytics import (
    all_user_ids,
    get_admin_stats,
    list_users_admin,
    recent_events,
    recent_purchases,
)
from config import admin_ids
from keyboards import BTN_ADMIN
from states import AdminBroadcast

log = logging.getLogger(__name__)

router = Router()

ADM_STATS = "📊 Статистика"
ADM_USERS = "👥 Пользователи"
ADM_SALES = "💰 Продажи"
ADM_CHARTS = "🌙 Карты"
ADM_ACTIVITY = "🔥 Активность"
ADM_BROADCAST = "📨 Рассылка"

KB_ADMIN = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=ADM_STATS, callback_data="admin:stats")],
        [
            InlineKeyboardButton(text=ADM_USERS, callback_data="admin:users"),
            InlineKeyboardButton(text=ADM_SALES, callback_data="admin:sales"),
        ],
        [
            InlineKeyboardButton(text=ADM_CHARTS, callback_data="admin:charts"),
            InlineKeyboardButton(text=ADM_ACTIVITY, callback_data="admin:activity"),
        ],
        [InlineKeyboardButton(text=ADM_BROADCAST, callback_data="admin:broadcast")],
    ]
)


def is_admin(user_id: int) -> bool:
    return user_id in admin_ids()


def _uid(msg: Message) -> int:
    return msg.from_user.id if msg.from_user else 0


def _stats_text() -> str:
    s = get_admin_stats()
    return (
        "📊 <b>Статистика Lunara</b>\n\n"
        f"👥 Пользователей: <b>{s['users_total']}</b>\n"
        f"🆕 Новых сегодня: <b>{s['users_today']}</b>\n\n"
        f"🌙 Карт всего: <b>{s['charts_total']}</b>\n"
        f"💎 Premium-карт: <b>{s['premium_charts']}</b>\n\n"
        f"🛒 Покупок: <b>{s['purchases_count']}</b>\n"
        f"💰 Выручка: <b>{s['revenue']:,} ₽</b>\n\n"
        f"📈 Конверсия в Premium: <b>{s['conversion']}%</b>\n"
        f"<i>(пользователи с ≥1 premium-картой / с картой)</i>"
    ).replace(",", " ")


async def open_admin_panel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer(
        "⚙️ <b>Admin panel</b>\n\nВыбери раздел:",
        reply_markup=KB_ADMIN,
        parse_mode="HTML",
    )


@router.message(Command("myid"))
async def cmd_myid(msg: Message) -> None:
    await msg.answer(
        f"Ваш Telegram ID: <code>{_uid(msg)}</code>",
        parse_mode="HTML",
    )


@router.message(Command("admin"))
@router.message(StateFilter(None), F.text == BTN_ADMIN)
async def cmd_admin(msg: Message, state: FSMContext) -> None:
    uid = _uid(msg)
    if not is_admin(uid):
        return
    try:
        await open_admin_panel(msg, state)
    except Exception as e:
        log.exception("admin panel open failed for %s", uid)
        await msg.answer(f"Ошибка admin panel: {e}")


@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, state: FSMContext) -> None:
    if not is_admin(_uid(msg)):
        return
    await state.set_state(AdminBroadcast.waiting)
    await msg.answer(
        "📨 <b>Рассылка</b>\n\n"
        "Отправь одно сообщение (текст, фото с подписью).\n"
        "/cancel — отмена",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("admin:"))
async def cb_admin(cb: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    if not cb.message:
        await cb.answer("Сообщение недоступно", show_alert=True)
        return

    action = cb.data.split(":")[1]
    await cb.answer()

    try:
        if action == "stats":
            await cb.message.answer(_stats_text(), parse_mode="HTML")
            return

        if action == "users":
            rows = list_users_admin(20)
            if not rows:
                await cb.message.answer("👥 Пользователей пока нет.")
                return
            lines = ["👥 <b>Последние пользователи</b>\n"]
            for u in rows:
                lines.append(
                    f"• <code>{u['telegram_id']}</code> · карт: {u['charts_count']} "
                    f"· 💎: {u['premium_count']}"
                )
            await cb.message.answer("\n".join(lines), parse_mode="HTML")
            return

        if action == "sales":
            sales = recent_purchases(15)
            if not sales:
                await cb.message.answer("💰 Покупок пока нет.")
                return
            lines = ["💰 <b>Последние покупки</b>\n"]
            for p in sales:
                cid = p.get("chart_id") or "—"
                lines.append(
                    f"• {p['product_type']} · {p['amount_rub']} ₽ · "
                    f"user <code>{p['user_id']}</code> · chart {cid}"
                )
            await cb.message.answer("\n".join(lines), parse_mode="HTML")
            return

        if action == "charts":
            s = get_admin_stats()
            with_charts = list_users_admin(50)
            lines = [
                f"🌙 <b>Карты</b>\n\nВсего карт: <b>{s['charts_total']}</b>\n"
                f"Premium: <b>{s['premium_charts']}</b>\n\n<b>По пользователям:</b>\n"
            ]
            for u in with_charts[:15]:
                if u["charts_count"]:
                    lines.append(
                        f"• <code>{u['telegram_id']}</code>: {u['charts_count']} карт"
                    )
            await cb.message.answer("\n".join(lines), parse_mode="HTML")
            return

        if action == "activity":
            events = recent_events(20)
            if not events:
                await cb.message.answer("🔥 Событий пока нет.")
                return
            lines = ["🔥 <b>Последняя активность</b>\n"]
            for e in events:
                meta = f" · {e['meta']}" if e.get("meta") else ""
                ch = f" · chart {e['chart_id']}" if e.get("chart_id") else ""
                lines.append(
                    f"• <code>{e['user_id']}</code> · {e['event_type']}{ch}{meta}"
                )
            await cb.message.answer("\n".join(lines[:25]), parse_mode="HTML")
            return

        if action == "broadcast":
            await state.set_state(AdminBroadcast.waiting)
            await cb.message.answer(
                "📨 Отправь текст рассылки одним сообщением.\n/cancel — отмена"
            )
    except Exception as e:
        log.exception("admin callback %s failed", action)
        await cb.message.answer(f"Ошибка раздела «{action}»: {e}")


@router.message(AdminBroadcast.waiting)
async def on_broadcast(msg: Message, state: FSMContext) -> None:
    if not is_admin(_uid(msg)):
        return
    if msg.text and msg.text.startswith("/cancel"):
        await state.clear()
        await msg.answer("Рассылка отменена.")
        return

    user_ids = all_user_ids()
    if not user_ids:
        await state.clear()
        await msg.answer("Нет пользователей для рассылки.")
        return

    await msg.answer(f"📨 Рассылка на {len(user_ids)} пользователей…")
    ok, fail = 0, 0
    for uid in user_ids:
        try:
            await msg.copy_to(uid)
            ok += 1
        except Exception as e:
            fail += 1
            log.debug("broadcast fail %s: %s", uid, e)
        await asyncio.sleep(0.05)

    await state.clear()
    await msg.answer(
        f"✅ Рассылка завершена\n\n"
        f"Доставлено: <b>{ok}</b>\n"
        f"Ошибок: <b>{fail}</b>",
        parse_mode="HTML",
    )
