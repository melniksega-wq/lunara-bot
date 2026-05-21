import asyncio
import logging
import re

logger = logging.getLogger(__name__)

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove
from openai import AsyncOpenAI

from chart_generator import generate_natal_chart_png
from config import OPENAI_API_KEY, OPENAI_MODEL
from database import save_user
from keyboards import (
    BTN_CREATE_CARD,
    BTN_UNKNOWN_TIME,
    MAIN_REPLY_KB,
    MENU_INLINE_KB,
    QUICK_QUESTIONS,
    QUICK_QUESTIONS_KB,
    UNKNOWN_TIME_KB,
)
from states import BirthForm, CompatibilityForm

router = Router()
_openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

WELCOME_INTRO = (
    "✨ Добро пожаловать в Lunara\n\n"
    "Я создам твою персональную натальную карту и расскажу:\n"
    "• кто ты на самом деле\n"
    "• что у тебя с любовью\n"
    "• где твои сильные стороны\n"
    "• почему в жизни повторяются одни и те же ситуации\n\n"
    "Нажми кнопку ниже, чтобы начать 💫"
)

_ASTRO_STYLE = (
    "Ты премиальный астрологический AI-сервис Lunara.\n\n"
    "Пиши эмоционально, красиво и современно.\n"
    "Не используй сложные астрологические термины.\n"
    "Пиши так, чтобы человек чувствовал: «это точно про меня».\n\n"
    "Текст должен быть атмосферным, персональным, вовлекающим и не слишком длинным.\n"
    "Без медицинских и юридических советов, без катастрофического языка.\n"
    "Если время рождения неизвестно — скажи об этом мягко, опирайся на дату и место."
)

_SYSTEM_PROMPT = (
    _ASTRO_STYLE
    + "\n\nПо данным рождения сделай натальную карту на русском языке.\n"
    "Строго соблюдай структуру с эмодзи в заголовках:\n"
    "1. ✨ Кто человек\n"
    "2. ⚡ Его сильная сторона\n"
    "3. 🔮 Главная проблема\n"
    "4. 💕 Любовь и отношения\n"
    "5. 💰 Деньги и реализация\n"
    "6. 🌑 Что ему мешает\n"
    "7. 🌟 Его скрытый потенциал\n\n"
    "В каждом разделе — 1–2 коротких абзаца."
)

_COMPAT_SYSTEM = (
    _ASTRO_STYLE
    + "\n\nСделай разбор совместимости двух людей по их данным. "
    "Пиши эмоционально и понятно, без сложных астрологических терминов.\n"
    "Строго соблюдай структуру с эмодзи в заголовках:\n"
    "1. 💕 Эмоциональная совместимость\n"
    "2. 🔥 Сильное притяжение\n"
    "3. ⚡ Основные конфликты\n"
    "4. 🌱 Перспектива отношений\n"
    "5. 🌑 Что может разрушить отношения\n\n"
    "В каждом разделе — 1–2 коротких абзаца."
)

_MENU_PROMPTS = {
    "money": (
        "Сделай раздел про деньги и карьеру: сильные стороны в работе, подходящие направления, "
        "что мешает зарабатывать, практичные советы на ближайшие месяцы."
    ),
    "love": (
        "Сделай раздел про любовь и отношения: как проявляется в паре, что важно в партнёре, "
        "типичные сценарии, мягкие рекомендации."
    ),
    "forecast": (
        "Сделай краткий прогноз на ближайшие 3–6 месяцев: ключевые темы, возможности, "
        "на что обратить внимание. Без точных дат «предсказаний»."
    ),
}

_DATE_RE = re.compile(
    r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$"
)
_TIME_RE = re.compile(
    r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)


def _parse_date(text: str) -> tuple[int, int, int] | None:
    m = _DATE_RE.match(text.strip())
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    try:
        from datetime import date

        date(y, mo, d)
    except ValueError:
        return None
    return y, mo, d


def _parse_time(text: str) -> tuple[int, int] | None:
    m = _TIME_RE.match(text.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def _profile_prompt(data: dict) -> str:
    return (
        f"Имя: {data['name']}\n"
        f"Дата рождения: {data['birth_date']}\n"
        f"Время рождения: {data['birth_time']}\n"
        f"Место рождения: {data['birth_place']}\n"
    )


_GENERATION_STEPS = (
    "✨ Анализирую положение планет...",
    "🌙 Изучаю твою личность...",
    "❤️ Анализирую сферу отношений...",
    "💰 Смотрю денежный потенциал...",
)
_GENERATION_STEP_DELAY = 1.5


async def _send_generation_progress(message: Message) -> None:
    for i, text in enumerate(_GENERATION_STEPS):
        await message.answer(text)
        if i < len(_GENERATION_STEPS) - 1:
            await asyncio.sleep(_GENERATION_STEP_DELAY)


async def _call_openai(system: str, user: str) -> str:
    completion = await _openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    return completion.choices[0].message.content or ""


async def _send_long_text(message: Message, text: str) -> None:
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await message.answer(text[i : i + chunk_size])


async def _send_quick_questions(message: Message) -> None:
    await message.answer(
        "✨ Что ты хочешь узнать?",
        reply_markup=QUICK_QUESTIONS_KB,
    )


async def _send_after_menu(message: Message) -> None:
    await _send_quick_questions(message)
    await message.answer(
        "Или выбери другой раздел 👇",
        reply_markup=MENU_INLINE_KB,
    )


def _compat_user_prompt(profile: dict, partner_name: str, partner_birth_date: str) -> str:
    parts = [
        "Сделай разбор совместимости для пары.",
        "",
        "Первый человек (пользователь):",
        _profile_prompt(profile),
    ]
    chart = profile.get("natal_chart")
    if chart:
        parts.extend(["", "Натальная карта пользователя:", chart])
    parts.extend(
        [
            "",
            "Партнёр:",
            f"Имя: {partner_name}",
            f"Дата рождения: {partner_birth_date}",
        ]
    )
    return "\n".join(parts)


def _question_user_prompt(profile: dict, question: str) -> str:
    parts = [
        f"Вопрос: {question}",
        "",
        "Данные рождения:",
        _profile_prompt(profile),
    ]
    chart = profile.get("natal_chart")
    if chart:
        parts.extend(["", "Натальная карта пользователя:", chart])
    return "\n".join(parts)


_QUESTION_SYSTEM = (
    _ASTRO_STYLE
    + "\n\nОтветь на вопрос пользователя, опираясь на данные рождения и его натальную карту. "
    "2–3 абзаца, с эмодзи в заголовке."
)


async def _get_profile(state: FSMContext) -> dict | None:
    data = await state.get_data()
    if not data.get("name") or not data.get("birth_date"):
        return None
    return data


async def _begin_form(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BirthForm.name)
    await message.answer(
        "Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_INTRO, reply_markup=MAIN_REPLY_KB)


@router.message(Command("form"))
async def cmd_form(message: Message, state: FSMContext) -> None:
    await _begin_form(message, state)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Анкета сброшена. Нажми «✨ Создать мою карту», чтобы начать снова 💫",
        reply_markup=MAIN_REPLY_KB,
    )


@router.message(F.text == BTN_CREATE_CARD)
async def btn_create_card(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current:
        await message.answer(
            "Сначала закончи текущий шаг или напиши /cancel, чтобы начать заново."
        )
        return
    await _begin_form(message, state)


@router.message(BirthForm.name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    if message.text.strip() == BTN_CREATE_CARD:
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Введите, пожалуйста, полноценное имя.")
        return
    await state.update_data(name=name)
    await state.set_state(BirthForm.birth_date)
    await message.answer(
        "📅 Дата рождения в формате ДД.ММ.ГГГГ (например, 15.03.1990)."
    )


@router.message(BirthForm.birth_date, F.text)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    parsed = _parse_date(message.text)
    if not parsed:
        await message.answer(
            "Не удалось разобрать дату. Используйте ДД.ММ.ГГГГ, например 08.11.2001."
        )
        return
    y, mo, d = parsed
    await state.update_data(birth_date=f"{d:02d}.{mo:02d}.{y}")
    await state.set_state(BirthForm.birth_time)
    await message.answer(
        "🕐 Время рождения в формате ЧЧ:ММ (24 часа), например 14:30.\n"
        "Если не знаешь — нажми кнопку ниже.",
        reply_markup=UNKNOWN_TIME_KB,
    )


@router.message(BirthForm.birth_time, F.text)
async def process_birth_time(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text == BTN_UNKNOWN_TIME:
        await state.update_data(birth_time="неизвестно")
    else:
        parsed = _parse_time(text)
        if not parsed:
            await message.answer(
                "Укажи время как ЧЧ:ММ, например 09:05 или 21:40, или нажми «Не знаю»."
            )
            return
        h, mi = parsed
        await state.update_data(birth_time=f"{h:02d}:{mi:02d}")
    await state.set_state(BirthForm.birth_place)
    await message.answer(
        "📍 Город и страна рождения (например, Москва, Россия).",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(BirthForm.birth_place, F.text)
async def process_birth_place(message: Message, state: FSMContext) -> None:
    place = message.text.strip()
    if len(place) < 2:
        await message.answer("Уточните место рождения (город и при необходимости страна).")
        return
    await state.update_data(birth_place=place)
    data = await state.get_data()

    if message.from_user:
        save_user(
            telegram_id=message.from_user.id,
            name=data["name"],
            birth_date=data["birth_date"],
            birth_time=data["birth_time"],
            birth_place=place,
        )

    await state.set_state(None)

    try:
        png_path = await asyncio.to_thread(
            generate_natal_chart_png,
            telegram_id=message.from_user.id if message.from_user else 0,
            name=data["name"],
            birth_date=data["birth_date"],
            birth_time=data["birth_time"],
            birth_place=place,
        )
        await message.answer_photo(
            FSInputFile(png_path),
            caption="✨ Твоя натальная карта Lunara",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Не удалось сгенерировать карту: %s", e)
        await message.answer(
            "Не получилось построить изображение карты — продолжаю текстовый разбор ✨"
        )

    await _send_generation_progress(message)

    prompt = _profile_prompt(data)

    try:
        text = await _call_openai(
            _SYSTEM_PROMPT,
            "Сделай натальный разбор Lunara по данным:\n\n" + prompt,
        )
    except Exception as e:  # noqa: BLE001
        await message.answer(
            "Не удалось получить ответ от OpenAI. Проверьте ключ API, баланс и название модели.\n"
            f"Техническая информация: {type(e).__name__}: {e}",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    await state.update_data(natal_chart=text)
    await _send_long_text(message, text)
    await message.answer("Готово ✨", reply_markup=MAIN_REPLY_KB)
    await _send_after_menu(message)


@router.callback_query(F.data.startswith("quick:"))
async def on_quick_question(callback: CallbackQuery, state: FSMContext) -> None:
    profile = await _get_profile(state)
    if not profile or not profile.get("natal_chart"):
        await callback.answer("Сначала создай натальную карту ✨", show_alert=True)
        return

    key = callback.data.split(":", 1)[1]
    question = QUICK_QUESTIONS.get(key)
    if not question:
        await callback.answer()
        return

    await callback.answer()
    await callback.message.answer(f"🔮 {question}\n\nСмотрю в твою карту…")

    try:
        text = await _call_openai(
            _QUESTION_SYSTEM,
            _question_user_prompt(profile, question),
        )
    except Exception as e:  # noqa: BLE001
        await callback.message.answer(
            f"Не удалось получить ответ. {type(e).__name__}: {e}",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    await _send_long_text(callback.message, text)
    await callback.message.answer("Готово ✨", reply_markup=MAIN_REPLY_KB)
    await _send_after_menu(callback.message)


@router.callback_query(F.data.startswith("menu:"))
async def on_menu_click(callback: CallbackQuery, state: FSMContext) -> None:
    profile = await _get_profile(state)
    if not profile:
        await callback.answer("Сначала создай карту ✨", show_alert=True)
        return

    topic = callback.data.split(":", 1)[1]

    if topic == "question":
        await callback.answer()
        await state.set_state(BirthForm.custom_question)
        await callback.message.answer(
            "🔮 Напиши свой вопрос одним сообщением — отвечу с опорой на твою карту."
        )
        return

    if topic == "compat":
        await callback.answer()
        await state.set_state(CompatibilityForm.partner_name)
        await callback.message.answer(
            "❤️ Совместимость\n\n"
            "Как зовут партнёра? (имя или имя и фамилия)"
        )
        return

    await callback.answer()
    await callback.message.answer("Смотрю в карту… ✨")

    user_prompt = _MENU_PROMPTS.get(topic, "Дай полезный астрологический совет.")
    try:
        text = await _call_openai(
            _QUESTION_SYSTEM,
            _question_user_prompt(profile, user_prompt),
        )
    except Exception as e:  # noqa: BLE001
        await callback.message.answer(
            f"Не удалось получить ответ. {type(e).__name__}: {e}",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    await _send_long_text(callback.message, text)
    await _send_after_menu(callback.message)


@router.message(CompatibilityForm.partner_name, F.text)
async def process_partner_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Напиши имя партнёра чуть подробнее 🙏")
        return
    await state.update_data(partner_name=name)
    await state.set_state(CompatibilityForm.partner_birth_date)
    await message.answer(
        f"📅 Дата рождения {name} в формате ДД.ММ.ГГГГ (например, 22.07.1992)."
    )


@router.message(CompatibilityForm.partner_birth_date, F.text)
async def process_partner_birth_date(message: Message, state: FSMContext) -> None:
    profile = await _get_profile(state)
    if not profile:
        await state.set_state(None)
        await message.answer(
            "Сначала создай свою карту кнопкой «✨ Создать мою карту».",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    parsed = _parse_date(message.text)
    if not parsed:
        await message.answer(
            "Не удалось разобрать дату. Используй ДД.ММ.ГГГГ, например 08.11.2001."
        )
        return

    y, mo, d = parsed
    partner_date = f"{d:02d}.{mo:02d}.{y}"
    data = await state.get_data()
    partner_name = data.get("partner_name", "Партнёр")

    await state.set_state(None)
    await message.answer("❤️ Смотрю вашу совместимость…")

    try:
        text = await _call_openai(
            _COMPAT_SYSTEM,
            _compat_user_prompt(profile, partner_name, partner_date),
        )
    except Exception as e:  # noqa: BLE001
        await message.answer(
            f"Не удалось получить ответ. {type(e).__name__}: {e}",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    await _send_long_text(message, text)
    await message.answer("Готово ✨", reply_markup=MAIN_REPLY_KB)
    await _send_after_menu(message)


@router.message(BirthForm.custom_question, F.text)
async def process_custom_question(message: Message, state: FSMContext) -> None:
    profile = await _get_profile(state)
    if not profile:
        await state.set_state(None)
        await message.answer(
            "Сначала создай карту кнопкой «✨ Создать мою карту».",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    question = message.text.strip()
    if len(question) < 3:
        await message.answer("Напиши вопрос чуть подробнее 🙏")
        return

    await state.set_state(None)
    await message.answer("🔮 Ищу ответ в твоей карте…")

    try:
        text = await _call_openai(
            _QUESTION_SYSTEM,
            _question_user_prompt(profile, question),
        )
    except Exception as e:  # noqa: BLE001
        await message.answer(
            f"Не удалось получить ответ. {type(e).__name__}: {e}",
            reply_markup=MAIN_REPLY_KB,
        )
        return

    await _send_long_text(message, text)
    await message.answer("Готово ✨", reply_markup=MAIN_REPLY_KB)
    await _send_after_menu(message)
