from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --- Onboarding ---
BTN_UNKNOWN_TIME = "Не знаю"

UNKNOWN_TIME_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_UNKNOWN_TIME)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

# --- Reply menu (free) ---
BTN_MY_CHART = "🌙 Моя карта"
BTN_PREMIUM = "💎 Premium"
BTN_SUPPORT = "💬 Поддержка"

# --- Reply menu (premium only) ---
BTN_COMPAT = "❤️ Совместимость"
BTN_QUESTIONS = "🔮 Вопросы"
BTN_ASK = "✍️ Задать вопрос"
BTN_HOROSCOPE = "📅 Гороскопы"


def main_menu_kb(premium: bool) -> ReplyKeyboardMarkup:
    if premium:
        rows = [
            [BTN_MY_CHART, BTN_COMPAT],
            [BTN_QUESTIONS, BTN_ASK],
            [BTN_HOROSCOPE, BTN_SUPPORT],
        ]
    else:
        rows = [
            [BTN_MY_CHART, BTN_PREMIUM],
            [BTN_SUPPORT],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# --- Paywall ---
BTN_UNLOCK_PREMIUM = "💎 Открыть полную карту — 249 ₽"

PAYWALL_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=BTN_UNLOCK_PREMIUM, callback_data="pay:unlock")],
    ]
)

# --- Популярные вопросы (premium) ---
POPULAR_QUESTIONS: dict[str, str] = {
    "love_luck": "Почему мне не везет в любви?",
    "talent": "В чем мой талант?",
    "burnout": "Почему я выгораю?",
    "money": "Где мои деньги?",
    "people": "Почему мне сложно с людьми?",
}

POPULAR_QUESTIONS_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"pop:{key}")]
        for key, text in POPULAR_QUESTIONS.items()
    ]
)

# --- Гороскопы (premium) ---
HOROSCOPE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data="horo:today"),
            InlineKeyboardButton(text="Неделя", callback_data="horo:week"),
        ],
        [InlineKeyboardButton(text="Месяц", callback_data="horo:month")],
    ]
)
