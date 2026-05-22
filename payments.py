"""
Оплата через REST API ЮKassa (redirect + webhook).

Не использует Telegram Payments API (sendInvoice).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram import Bot, Dispatcher

from analytics import record_purchase
from config import payments_enabled
import uuid

from database import (
    add_chart_questions,
    create_pending_payment,
    get_chart,
    get_pending_by_id,
    get_pending_by_yookassa_id,
    grant_chart_horo,
    mark_pending_fulfilled,
    set_chart_premium,
    update_pending_status,
    update_pending_yookassa_id,
)
from horo_scheduler import send_daily_horo
from paywalls import PRICES
from yookassa_client import create_payment, get_payment

log = logging.getLogger(__name__)
router = Router()


@dataclass(frozen=True)
class InvoiceProduct:
    key: str
    title: str
    description: str
    price_rub: int
    record_type: str

    @property
    def amount_rub_str(self) -> str:
        kop = int(self.price_rub) * 100
        return f"{kop // 100}.{(kop % 100):02d}"


PRODUCTS: dict[str, InvoiceProduct] = {
    "premium": InvoiceProduct(
        key="premium",
        title="Lunara Premium",
        description="Полный анализ натальной карты, цифровой контент в боте",
        price_rub=PRICES["premium"],
        record_type="premium",
    ),
    "ask_3": InvoiceProduct(
        key="ask_3",
        title="3 персональных вопроса",
        description="Цифровая услуга в Telegram-боте Lunara",
        price_rub=PRICES["ask_3"],
        record_type="ask_3",
    ),
    "ask_10": InvoiceProduct(
        key="ask_10",
        title="10 персональных вопросов",
        description="Цифровая услуга в Telegram-боте Lunara",
        price_rub=PRICES["ask_10"],
        record_type="ask_10",
    ),
    "horo_today": InvoiceProduct(
        key="horo_today",
        title="Прогноз на сегодня",
        description="Персональный прогноз, цифровой контент",
        price_rub=PRICES["horo_today"],
        record_type="horo_today",
    ),
    "horo_week": InvoiceProduct(
        key="horo_week",
        title="Прогнозы на 7 дней",
        description="Ежедневная доставка в боте",
        price_rub=PRICES["horo_week"],
        record_type="horo_week",
    ),
    "horo_month": InvoiceProduct(
        key="horo_month",
        title="Прогнозы на 30 дней",
        description="Ежедневная доставка в боте",
        price_rub=PRICES["horo_month"],
        record_type="horo_month",
    ),
}


def product_key_from_callback(data: str) -> str | None:
    parts = data.split(":")
    if len(parts) < 2:
        return None
    if parts[0] == "pay":
        if parts[1] == "premium":
            return "premium"
        if parts[1] == "ask" and len(parts) == 3:
            return f"ask_{parts[2]}"
        if parts[1] == "horo" and len(parts) == 3:
            return f"horo_{parts[2]}"
    if parts[0] == "paycheck" and len(parts) == 2 and parts[1].isdigit():
        return None
    return None


def paycheck_order_id(data: str) -> int | None:
    parts = data.split(":")
    if parts[0] == "paycheck" and len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return None


def _fsm_context(dp: Dispatcher, bot: Bot, user_id: int) -> FSMContext:
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=dp.storage, key=key)


async def fulfill_order(
    message: Message,
    state: FSMContext,
    user_id: int,
    chart_id: int,
    product_key: str,
    *,
    provider_payment_id: str = "",
) -> None:
    from access import question_balance
    from handlers import (
        deliver_full_chart,
        deliver_today_horo,
        prompt_custom_question,
        show_menu,
    )

    chart = get_chart(chart_id, user_id)
    if not chart:
        await message.answer("Карта не найдена. Напиши в поддержку.")
        return

    product = PRODUCTS.get(product_key)
    if not product:
        await message.answer("Неизвестный товар. Напиши в поддержку.")
        return

    cname = chart["profile_name"]
    record_purchase(
        user_id,
        product.record_type,
        product.price_rub,
        chart_id=chart_id,
    )

    if product_key == "premium":
        set_chart_premium(chart_id, True)
        await message.answer(f"💎 Premium для «{cname}» активирован. Спасибо за оплату!")
        await deliver_full_chart(message, user_id)
        await show_menu(message, user_id)
        return

    if product_key == "ask_3":
        add_chart_questions(chart_id, 3)
        chart = get_chart(chart_id, user_id)
        left = question_balance(chart) if chart else 0
        await message.answer(f"✍️ +3 вопроса для «{cname}»\nОсталось: {left}")
        await prompt_custom_question(message, state, user_id)
        return

    if product_key == "ask_10":
        add_chart_questions(chart_id, 10)
        chart = get_chart(chart_id, user_id)
        left = question_balance(chart) if chart else 0
        await message.answer(f"✍️ +10 вопросов для «{cname}»\nОсталось: {left}")
        await prompt_custom_question(message, state, user_id)
        return

    if product_key == "horo_today":
        grant_chart_horo(chart_id, "today", 1)
        await message.answer(f"📅 Прогноз «Сегодня» для «{cname}»")
        await deliver_today_horo(message, user_id)
        await show_menu(message, user_id)
        return

    if product_key == "horo_week":
        grant_chart_horo(chart_id, "week", 7)
        chart = get_chart(chart_id, user_id)
        await message.answer(f"📅 «Неделя» для «{cname}» — 7 дней")
        if chart:
            await send_daily_horo(message.bot, chart)
        await show_menu(message, user_id)
        return

    if product_key == "horo_month":
        grant_chart_horo(chart_id, "month", 30)
        chart = get_chart(chart_id, user_id)
        await message.answer(f"📅 «Месяц» для «{cname}» — 30 дней")
        if chart:
            await send_daily_horo(message.bot, chart)
        await show_menu(message, user_id)
        return

    log.warning("unhandled product %s payment %s", product_key, provider_payment_id)


async def process_payment_object(
    bot: Bot,
    dp: Dispatcher,
    payment_obj: dict,
) -> None:
    yk_id = payment_obj.get("id", "")
    status = payment_obj.get("status", "")
    if not yk_id:
        return

    pending = get_pending_by_yookassa_id(yk_id)
    if not pending:
        meta = payment_obj.get("metadata") or {}
        try:
            order_id = int(meta.get("order_id", 0))
        except (TypeError, ValueError):
            order_id = 0
        if order_id:
            pending = get_pending_by_id(order_id)
    if not pending:
        log.warning("pending payment not found for %s", yk_id)
        return

    update_pending_status(pending["id"], status)
    if status not in ("succeeded", "waiting_for_capture"):
        return
    if pending.get("fulfilled"):
        return
    if not mark_pending_fulfilled(pending["id"]):
        return

    user_id = int(pending["user_id"])
    chart_id = int(pending["chart_id"])
    product_key = pending["product_key"]

    msg = await bot.send_message(user_id, "✅ Оплата получена, открываю доступ…")
    state = _fsm_context(dp, bot, user_id)
    await fulfill_order(
        msg,
        state,
        user_id,
        chart_id,
        product_key,
        provider_payment_id=yk_id,
    )


async def try_complete_order(
    bot: Bot,
    dp: Dispatcher,
    chat_id: int,
    order_id: int,
) -> None:
    pending = get_pending_by_id(order_id)
    if not pending:
        await bot.send_message(chat_id, "Заказ не найден.")
        return
    if pending.get("fulfilled"):
        await bot.send_message(chat_id, "Этот заказ уже выполнен ✨")
        return

    try:
        payment = await get_payment(pending["yookassa_id"])
    except Exception as e:
        log.exception("get_payment %s", order_id)
        await bot.send_message(chat_id, f"Не удалось проверить оплату: {e}")
        return

    status = payment.get("status", "")
    if status == "succeeded":
        await process_payment_object(bot, dp, payment)
        return
    if status == "pending":
        await bot.send_message(
            chat_id,
            "Оплата ещё не завершена. Заверши платёж на странице ЮKassa "
            "или подожди минуту и нажми «Проверить оплату» снова.",
        )
        return
    if status == "canceled":
        await bot.send_message(chat_id, "Платёж отменён. Можно создать новый счёт.")
        return
    await bot.send_message(chat_id, f"Статус платежа: {status}")


async def send_yookassa_payment_link(
    cb: CallbackQuery,
    chart: dict,
    product_key: str,
) -> None:
    product = PRODUCTS.get(product_key)
    if not product or not cb.message:
        await cb.answer("Товар не найден", show_alert=True)
        return

    user_id = cb.from_user.id
    chart_id = int(chart["id"])

    try:
        order_id = create_pending_payment(
            yookassa_id=f"tmp_{uuid.uuid4().hex}",
            user_id=user_id,
            chart_id=chart_id,
            product_key=product_key,
            amount_rub=product.price_rub,
        )
        payment = await create_payment(
            amount_rub_str=product.amount_rub_str,
            description=product.description,
            product_title=product.title,
            order_id=order_id,
            user_id=user_id,
            chart_id=chart_id,
            product_key=product_key,
        )
    except Exception as e:
        log.exception("create yookassa payment")
        await cb.answer("Ошибка создания платежа", show_alert=True)
        await cb.message.answer(
            f"Не удалось создать платёж.\n\n"
            f"Проверь YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в Railway.\n\n"
            f"Ошибка: {e}"
        )
        return

    yk_id = payment.get("id", "")
    confirm = payment.get("confirmation") or {}
    pay_url = confirm.get("confirmation_url", "")
    if not yk_id or not pay_url:
        await cb.message.answer("ЮKassa не вернула ссылку на оплату.")
        return

    update_pending_yookassa_id(order_id, yk_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=pay_url)],
            [
                InlineKeyboardButton(
                    text="✅ Проверить оплату",
                    callback_data=f"paycheck:{order_id}",
                )
            ],
        ]
    )
    await cb.message.answer(
        f"💳 *{product.title}*\n\n"
        f"Сумма: *{product.amount_rub_str} ₽*\n\n"
        "Оплата на защищённой странице ЮKassa "
        "(карта, SberPay, ЮMoney и др.).\n\n"
        "После оплаты доступ откроется автоматически. "
        "Если не открылся — нажми «Проверить оплату».",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await cb.answer()


@router.callback_query(F.data.startswith("paycheck:"))
async def on_paycheck(cb: CallbackQuery) -> None:
    order_id = paycheck_order_id(cb.data)
    if not order_id or not cb.message:
        await cb.answer()
        return
    await cb.answer("Проверяю…")
    dp = getattr(cb.bot, "_lunara_dp", None)
    if not dp:
        await cb.message.answer("Внутренняя ошибка: перезапусти бота.")
        return
    await try_complete_order(cb.bot, dp, cb.message.chat.id, order_id)


async def handle_paid_deeplink(
    msg: Message,
    state: FSMContext,
    order_id: int,
) -> None:
    dp = getattr(msg.bot, "_lunara_dp", None)
    if not dp:
        await msg.answer("Перезапусти бота и попробуй снова.")
        return
    await try_complete_order(msg.bot, dp, msg.chat.id, order_id)
