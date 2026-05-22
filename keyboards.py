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
BTN_MY_CHARTS = "📋 Все карты"
BTN_NEW_CHART = "➕ Создать новую карту"
BTN_CHART = "✨ Текущая карта"
BTN_PREMIUM = "💎 Premium"
BTN_SUPPORT = "💬 Поддержка"
BTN_COMPAT = "❤️ Совместимость"
BTN_QUESTIONS = "🔮 Вопросы"
BTN_ASK = "✍️ Задать вопрос"
BTN_HORO = "📅 Гороскопы"
BTN_ADMIN = "⚙️ Admin"

SUPPORT_URL = "https://t.me/sup_lunara"

KB_SUPPORT = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✉️ Написать в поддержку",
                url=SUPPORT_URL,
            )
        ],
    ]
)


def _btn(text: str) -> KeyboardButton:
    return KeyboardButton(text=text)


def menu_kb(is_premium: bool, *, show_admin: bool = False) -> ReplyKeyboardMarkup:
    row_charts = [_btn(BTN_MY_CHARTS), _btn(BTN_NEW_CHART)]
    admin_row = [[_btn(BTN_ADMIN)]] if show_admin else []
    if is_premium:
        rows = [
            row_charts,
            [_btn(BTN_CHART), _btn(BTN_COMPAT)],
            [_btn(BTN_QUESTIONS), _btn(BTN_ASK)],
            [_btn(BTN_HORO), _btn(BTN_SUPPORT)],
        ]
        return ReplyKeyboardMarkup(
            keyboard=rows + admin_row,
            resize_keyboard=True,
        )
    rows = [
        row_charts,
        [_btn(BTN_CHART), _btn(BTN_PREMIUM)],
        [_btn(BTN_ASK), _btn(BTN_HORO)],
        [_btn(BTN_SUPPORT)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows + admin_row,
        resize_keyboard=True,
    )


def charts_list_kb(charts: list[dict], active_id: int | None) -> InlineKeyboardMarkup:
    rows = []
    for ch in charts:
        marks = ""
        if ch["id"] == active_id:
            marks += " ✅"
        if ch.get("premium_unlocked"):
            marks += " 💎"
        label = f"{ch['profile_name']} · {ch['birth_date']}{marks}"
        if len(label) > 64:
            label = label[:61] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"chart:{ch['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
