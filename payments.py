"""
Оплата через ЮKassa (нативная интеграция Telegram Payments).

Документация: sendInvoice + provider_token + provider_data (чек 54-ФЗ).
После оплаты Telegram присылает SuccessfulPayment (без webhook ЮKassa).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from analytics import record_purchase
from config import (
    YOOKASSA_PROVIDER_TOKEN,
    YOOKASSA_VAT_CODE,
    payments_enabled,
)
from database import (
    add_chart_questions,
    get_chart,
    grant_chart_horo,
    set_chart_premium,
)
from horo_scheduler import send_daily_horo
from paywalls import PRICES

log = logging.getLogger(__name__)
router = Router()


@dataclass(frozen=True)
class InvoiceProduct:
    key: str
    title: str
    description: str
    label: str
    price_rub: int
    record_type: str

    @property
    def amount_kop(self) -> int:
        return int(self.price_rub) * 100

    @property
    def amount_rub_str(self) -> str:
        """Сумма в рублях для чека ЮKassa (должна совпадать с amount в prices)."""
        kop = self.amount_kop
        return f"{kop // 100}.{(kop % 100):02d}"


PRODUCTS: dict[str, InvoiceProduct] = {
    "premium": InvoiceProduct(
        key="premium",
        title="Lunara Premium",
        description="Полный анализ натальной карты, цифровой контент в боте",
        label="Premium - натальная карта",
        price_rub=PRICES["premium"],
        record_type="premium",
    ),
    "ask_3": InvoiceProduct(
        key="ask_3",
        title="3 персональных вопроса",
        description="Цифровая услуга в Telegram-боте Lunara",
        label="3 вопроса к карте",
        price_rub=PRICES["ask_3"],
        record_type="ask_3",
    ),
    "ask_10": InvoiceProduct(
        key="ask_10",
        title="10 персональных вопросов",
        description="Цифровая услуга в Telegram-боте Lunara",
        label="10 вопросов к карте",
        price_rub=PRICES["ask_10"],
        record_type="ask_10",
    ),
    "horo_today": InvoiceProduct(
        key="horo_today",
        title="Прогноз на сегодня",
        description="Персональный прогноз, цифровой контент",
        label="Прогноз на сегодня",
        price_rub=PRICES["horo_today"],
        record_type="horo_today",
    ),
    "horo_week": InvoiceProduct(
        key="horo_week",
        title="Прогнозы на 7 дней",
        description="Ежедневная доставка в боте",
        label="Прогнозы - 7 дней",
        price_rub=PRICES["horo_week"],
        record_type="horo_week",
    ),
    "horo_month": InvoiceProduct(
        key="horo_month",
        title="Прогнозы на 30 дней",
        description="Ежедневная доставка в боте",
        label="Прогнозы - 30 дней",
        price_rub=PRICES["horo_month"],
        record_type="horo_month",
    ),
}


def product_key_from_callback(data: str) -> str | None:
    parts = data.split(":")
    if len(parts) < 2 or parts[0] != "pay":
        return None
    if parts[1] == "premium":
        return "premium"
    if parts[1] == "ask" and len(parts) == 3:
        return f"ask_{parts[2]}"
    if parts[1] == "horo" and len(parts) == 3:
        return f"horo_{parts[2]}"
    return None


def build_payload(user_id: int, chart_id: int, product_key: str) -> str:
    """До 128 байт для invoice_payload."""
    return f"{user_id}:{chart_id}:{product_key}"


def parse_payload(payload: str) -> tuple[int, int, str] | None:
    try:
        uid_s, cid_s, key = payload.split(":", 2)
        return int(uid_s), int(cid_s), key
    except (ValueError, AttributeError):
        return None


def build_provider_data(product: InvoiceProduct) -> str:
    """Чек 54-ФЗ для ЮKassa (сумма в рублях = prices / 100)."""
    value = product.amount_rub_str
    receipt = {
        "receipt": {
            "items": [
                {
                    "description": product.title[:128],
                    "quantity": "1.00",
                    "amount": {"value": value, "currency": "RUB"},
                    "vat_code": int(YOOKASSA_VAT_CODE),
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ]
        }
    }
    return json.dumps(receipt, ensure_ascii=False)


async def send_payment_invoice(
    cb: CallbackQuery,
    chart: dict,
    product_key: str,
) -> None:
    product = PRODUCTS.get(product_key)
    if not product:
        await cb.answer("Товар не найден", show_alert=True)
        return
    if not cb.message:
        await cb.answer("Ошибка чата", show_alert=True)
        return

    payload = build_payload(cb.from_user.id, chart["id"], product_key)
    amount_kop = product.amount_kop
    if amount_kop < 100:
        await cb.answer("Сумма слишком мала для оплаты", show_alert=True)
        return

    invoice_kwargs = dict(
        chat_id=cb.message.chat.id,
        title=product.title[:32],
        description=product.description[:255],
        payload=payload,
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label=product.label[:64], amount=amount_kop)],
        need_email=True,
        send_email_to_provider=True,
        start_parameter="lunara",
    )
    try:
        await cb.bot.send_invoice(
            **invoice_kwargs,
            provider_data=build_provider_data(product),
        )
        await cb.answer()
    except Exception as e:
        err = str(e)
        log.exception(
            "send_invoice %s amount_kop=%s rub=%s",
            product_key,
            amount_kop,
            product.amount_rub_str,
        )
        if "CURRENCY_TOTAL_AMOUNT_INVALID" in err:
            try:
                await cb.bot.send_invoice(**invoice_kwargs)
                await cb.answer()
                return
            except Exception as e2:
                err = str(e2)
                log.exception("send_invoice without receipt failed")
        await cb.answer("Не удалось выставить счёт", show_alert=True)
        await cb.message.answer(
            "Не удалось открыть оплату.\n\n"
            f"Товар: {product.title}\n"
            f"Сумма: {product.amount_rub_str} ₽ ({amount_kop} коп.)\n\n"
            f"Ошибка: {err}"
        )


def validate_pre_checkout(query: PreCheckoutQuery) -> tuple[bool, str | None]:
    parsed = parse_payload(query.invoice_payload or "")
    if not parsed:
        return False, "Некорректный заказ"
    user_id, chart_id, product_key = parsed
    if query.from_user.id != user_id:
        return False, "Заказ привязан к другому пользователю"
    if product_key not in PRODUCTS:
        return False, "Товар недоступен"
    product = PRODUCTS[product_key]
    if query.total_amount != product.amount_kop:
        return False, "Сумма заказа изменилась"
    chart = get_chart(chart_id, user_id)
    if not chart:
        return False, "Карта не найдена"
    return True, None


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
        await message.answer(
            f"✍️ +3 вопроса для «{cname}»\nОсталось: {left}"
        )
        await prompt_custom_question(message, state, user_id)
        return

    if product_key == "ask_10":
        add_chart_questions(chart_id, 10)
        chart = get_chart(chart_id, user_id)
        left = question_balance(chart) if chart else 0
        await message.answer(
            f"✍️ +10 вопросов для «{cname}»\nОсталось: {left}"
        )
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


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    ok, err = validate_pre_checkout(query)
    await query.answer(ok=ok, error_message=err)


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, state: FSMContext) -> None:
    sp = message.successful_payment
    parsed = parse_payload(sp.invoice_payload)
    if not parsed:
        await message.answer("Оплата получена, но заказ не распознан. Напиши в поддержку.")
        return
    user_id, chart_id, product_key = parsed
    if message.from_user and message.from_user.id != user_id:
        await message.answer("Ошибка привязки платежа. Напиши в поддержку.")
        return
    await fulfill_order(
        message,
        state,
        user_id,
        chart_id,
        product_key,
        provider_payment_id=sp.provider_payment_charge_id or "",
    )
