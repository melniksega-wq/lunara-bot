"""
Paywall-экраны Lunara (ЮKassa / Telegram Payments).

callback_data → product_id (заглушка до подключения оплаты):
  pay:premium      → premium_249
  pay:ask:3        → ask_3_99
  pay:ask:10       → ask_10_249
  pay:horo:today   → horo_today_29
  pay:horo:week    → horo_week_99
  pay:horo:month   → horo_month_199
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Цены в рублях (для invoice — умножить на 100 для копеек)
PRICES = {
    "premium": 249,
    "ask_3": 99,
    "ask_10": 249,
    "horo_today": 29,
    "horo_week": 99,
    "horo_month": 199,
}

PRODUCTS = {
    "premium_249": {
        "title": "Lunara Premium",
        "description": "Полный анализ натальной карты, цифровой контент в боте",
        "price_rub": PRICES["premium"],
        "callback": "pay:premium",
    },
    "ask_3_99": {
        "title": "3 персональных вопроса",
        "description": "Цифровая услуга в Telegram-боте Lunara",
        "price_rub": PRICES["ask_3"],
        "callback": "pay:ask:3",
    },
    "ask_10_249": {
        "title": "10 персональных вопросов",
        "description": "Цифровая услуга в Telegram-боте Lunara",
        "price_rub": PRICES["ask_10"],
        "callback": "pay:ask:10",
    },
    "horo_today_29": {
        "title": "Прогноз на сегодня",
        "description": "Персональный прогноз, цифровой контент",
        "price_rub": PRICES["horo_today"],
        "callback": "pay:horo:today",
    },
    "horo_week_99": {
        "title": "Прогнозы на 7 дней",
        "description": "Ежедневная доставка в боте",
        "price_rub": PRICES["horo_week"],
        "callback": "pay:horo:week",
    },
    "horo_month_199": {
        "title": "Прогнозы на 30 дней",
        "description": "Ежедневная доставка в боте",
        "price_rub": PRICES["horo_month"],
        "callback": "pay:horo:month",
    },
}

_FOOTER = "\n\nℹ️ После оплаты доступ активируется автоматически."


def paywall_premium_text() -> str:
    return (
        "💎 *Premium · Lunara*\n\n"
        "Цифровой контент для *активной* натальной карты.\n"
        "Каждая новая карта требует отдельного Premium.\n\n"
        "Расширенный анализ выбранной карты:\n\n"
        "*В Premium входит:*\n"
        "• полный анализ натальной карты\n"
        "• любовь и отношения\n"
        "• финансовый потенциал\n"
        "• совместимость\n"
        "• готовые вопросы\n"
        "• дополнительные разделы карты\n\n"
        "💰 Стоимость: *249 ₽*\n"
        "📦 Формат: цифровая услуга\n"
        "⏳ Доступ: бессрочный, внутри бота"
        f"{_FOOTER}"
    )


def paywall_premium_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 249 ₽",
                    callback_data="pay:premium",
                )
            ],
        ]
    )


def paywall_ask_text() -> str:
    return (
        "✍️ *Персональные вопросы*\n\n"
        "Отдельная цифровая услуга в Telegram-боте Lunara.\n\n"
        "Вы задаёте вопросы — ответы формируются *автоматически* "
        "на основе данных вашей натальной карты.\n\n"
        "*Пакеты:*\n"
        "• 3 вопроса — 99 ₽\n"
        "• 10 вопросов — 249 ₽\n\n"
        "Отдельно для активной карты. Не входит в Premium."
        f"{_FOOTER}"
    )


def paywall_ask_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 99 ₽",
                    callback_data="pay:ask:3",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 249 ₽",
                    callback_data="pay:ask:10",
                )
            ],
        ]
    )


def paywall_horo_text(extra: str = "") -> str:
    base = (
        "📅 *Персональные прогнозы*\n\n"
        "Отдельная цифровая услуга в Telegram-боте Lunara.\n\n"
        "Прогнозы формируются *автоматически* по данным натальной карты. "
        "Бот отправляет материалы в течение оплаченного периода.\n\n"
        "*Периоды:*\n"
        "• Сегодня — 29 ₽\n"
        "• Неделя — 99 ₽ · 7 дней подряд\n"
        "• Месяц — 199 ₽ · 30 дней подряд\n\n"
        "Отдельно для активной карты. Не входит в Premium."
        f"{_FOOTER}"
    )
    if extra:
        return f"{extra}\n\n{base}"
    return base


def paywall_horo_kb(*, show_today_btn: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if show_today_btn:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Получить прогноз на сегодня",
                    callback_data="horo:deliver:today",
                )
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 29 ₽",
                    callback_data="pay:horo:today",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 99 ₽",
                    callback_data="pay:horo:week",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Оплатить 199 ₽",
                    callback_data="pay:horo:month",
                )
            ],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_paywall_premium(msg) -> None:
    await msg.answer(
        paywall_premium_text(),
        reply_markup=paywall_premium_kb(),
        parse_mode="Markdown",
    )


async def send_paywall_ask(msg) -> None:
    await msg.answer(
        paywall_ask_text(),
        reply_markup=paywall_ask_kb(),
        parse_mode="Markdown",
    )


async def send_paywall_horo(msg, *, extra: str = "", show_today_btn: bool = False) -> None:
    await msg.answer(
        paywall_horo_text(extra),
        reply_markup=paywall_horo_kb(show_today_btn=show_today_btn),
        parse_mode="Markdown",
    )
