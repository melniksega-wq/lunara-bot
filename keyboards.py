from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_CREATE_CARD = "✨ Создать мою карту"
BTN_UNKNOWN_TIME = "Не знаю"

MAIN_REPLY_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CREATE_CARD)]],
    resize_keyboard=True,
)

UNKNOWN_TIME_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_UNKNOWN_TIME)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

MENU_INLINE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Совместимость", callback_data="menu:compat")],
        [InlineKeyboardButton(text="🔮 Задать вопрос", callback_data="menu:question")],
        [InlineKeyboardButton(text="💰 Деньги и карьера", callback_data="menu:money")],
        [InlineKeyboardButton(text="🌙 Любовь и отношения", callback_data="menu:love")],
        [InlineKeyboardButton(text="📅 Прогноз", callback_data="menu:forecast")],
    ]
)

# callback_data: quick:<ключ>
QUICK_QUESTIONS: dict[str, str] = {
    "love_luck": "Почему мне не везет в любви?",
    "talent": "В чем мой талант?",
    "burnout": "Почему я выгораю?",
    "money": "Где мои деньги?",
    "people": "Почему мне сложно с людьми?",
}

QUICK_QUESTIONS_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"quick:{key}")]
        for key, text in QUICK_QUESTIONS.items()
    ]
)
