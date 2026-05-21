from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

# Onboarding
BTN_NO_TIME = "Не знаю"
KB_TIME = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_NO_TIME)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# Меню
BTN_CHART = "🌙 Моя карта"
BTN_PREMIUM = "💎 Premium"
BTN_SUPPORT = "💬 Поддержка"
BTN_COMPAT = "❤️ Совместимость"
BTN_QUESTIONS = "🔮 Вопросы"
BTN_ASK = "✍️ Задать вопрос"
BTN_HORO = "📅 Гороскопы"

MENU_FREE = [BTN_CHART, BTN_PREMIUM, BTN_SUPPORT]
MENU_PREMIUM = [BTN_CHART, BTN_COMPAT, BTN_QUESTIONS, BTN_ASK, BTN_HORO, BTN_SUPPORT]


def menu_kb(premium: bool) -> ReplyKeyboardMarkup:
    if premium:
        return ReplyKeyboardMarkup(
            keyboard=[
                [BTN_CHART, BTN_COMPAT],
                [BTN_QUESTIONS, BTN_ASK],
                [BTN_HORO, BTN_SUPPORT],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        keyboard=[[BTN_CHART, BTN_PREMIUM], [BTN_SUPPORT]],
        resize_keyboard=True,
    )


PAYWALL_TEXT = (
    "🔒 Полная версия натальной карты скрыта\n\n"
    "В полной версии:\n"
    "• отношения\n"
    "• предназначение\n"
    "• деньги\n"
    "• жизненные сценарии\n"
    "• скрытые таланты"
)

KB_PAYWALL = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть полную карту — 249 ₽", callback_data="pay")]
    ]
)

POPULAR = {
    "love": "Почему мне не везет в любви?",
    "talent": "В чем мой талант?",
    "burnout": "Почему я выгораю?",
    "money": "Где мои деньги?",
    "people": "Почему мне сложно с людьми?",
}

KB_POPULAR = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=f"q:{k}")]
        for k, t in POPULAR.items()
    ]
)

KB_HORO = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="h:today"),
            InlineKeyboardButton(text="Неделя", callback_data="h:week"),
        ],
        [InlineKeyboardButton(text="Месяц", callback_data="h:month")],
    ]
)
