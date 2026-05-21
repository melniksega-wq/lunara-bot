from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

# Onboarding
BTN_CANCEL = "❌ Отмена"
BTN_NO_TIME = "Не знаю"

KB_ONBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
)

KB_TIME = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_NO_TIME)],
        [KeyboardButton(text=BTN_CANCEL)],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)

KB_ASK = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
    resize_keyboard=True,
)

# Меню
BTN_CHART = "🌙 Моя карта"
BTN_PREMIUM = "💎 Premium"
BTN_SUPPORT = "💬 Поддержка"
BTN_COMPAT = "❤️ Совместимость"
BTN_QUESTIONS = "🔮 Вопросы"
BTN_ASK = "✍️ Задать вопрос"
BTN_HORO = "📅 Гороскопы"


def _btn(text: str) -> KeyboardButton:
    return KeyboardButton(text=text)


def menu_kb(is_premium: bool) -> ReplyKeyboardMarkup:
    if is_premium:
        return ReplyKeyboardMarkup(
            keyboard=[
                [_btn(BTN_CHART), _btn(BTN_COMPAT)],
                [_btn(BTN_QUESTIONS), _btn(BTN_ASK)],
                [_btn(BTN_HORO), _btn(BTN_SUPPORT)],
            ],
            resize_keyboard=True,
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [_btn(BTN_CHART), _btn(BTN_PREMIUM)],
            [_btn(BTN_ASK), _btn(BTN_HORO)],
            [_btn(BTN_SUPPORT)],
        ],
        resize_keyboard=True,
    )


PAYWALL_PREMIUM_TEXT = (
    "🔒 Полная версия карты скрыта\n\n"
    "Premium за 249 ₽ открывает:\n"
    "• полную карту\n"
    "• совместимость\n"
    "• готовые вопросы"
)

PAYWALL_ASK_TEXT = (
    "✍️ Свой вопрос — отдельная покупка\n\n"
    "Не входит в Premium.\n"
    "Выбери пакет:"
)

PAYWALL_HORO_TEXT = (
    "📅 Гороскопы — отдельная покупка\n\n"
    "Не входит в Premium.\n"
    "Выбери период:"
)

KB_PAYWALL_PREMIUM = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💎 Premium — 249 ₽",
                callback_data="pay:premium",
            )
        ]
    ]
)

KB_PAYWALL_ASK = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="3 вопроса — 99 ₽",
                callback_data="pay:ask:3",
            )
        ],
        [
            InlineKeyboardButton(
                text="10 вопросов — 249 ₽",
                callback_data="pay:ask:10",
            )
        ],
    ]
)

KB_PAYWALL_HORO = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Сегодня — 29 ₽",
                callback_data="pay:horo:today",
            )
        ],
        [
            InlineKeyboardButton(
                text="Неделя — 99 ₽",
                callback_data="pay:horo:week",
            )
        ],
        [
            InlineKeyboardButton(
                text="Месяц — 199 ₽",
                callback_data="pay:horo:month",
            )
        ],
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

KB_HORO_MENU = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Сегодня — 29 ₽",
                callback_data="horo:today",
            )
        ],
        [
            InlineKeyboardButton(
                text="Неделя — 99 ₽",
                callback_data="horo:week",
            )
        ],
        [
            InlineKeyboardButton(
                text="Месяц — 199 ₽",
                callback_data="horo:month",
            )
        ],
    ]
)
