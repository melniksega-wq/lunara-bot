import asyncio
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove
from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from database import get_user, is_premium, save_readings, save_user, set_premium
from keyboards import (
    BTN_ASK,
    BTN_COMPAT,
    BTN_HOROSCOPE,
    BTN_MY_CHART,
    BTN_PREMIUM,
    BTN_QUESTIONS,
    BTN_SUPPORT,
    BTN_UNKNOWN_TIME,
    HOROSCOPE_KB,
    PAYWALL_KB,
    POPULAR_QUESTIONS,
    POPULAR_QUESTIONS_KB,
    UNKNOWN_TIME_KB,
    main_menu_kb,
)
from states import BirthForm, CompatibilityForm

logger = logging.getLogger(__name__)
router = Router()
_openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

ONBOARDING_WELCOME = (
    "✨ Добро пожаловать в Lunara\n\n"
    "Я создам твою персональную натальную карту:\n"
    "• кто ты на самом деле\n"
    "• что с любовью и деньгами\n"
    "• твоя главная черта\n\n"
    "Для начала — несколько данных о рождении 💫\n\n"
    "Как тебя зовут?"
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

SUPPORT_TEXT = (
    "💬 Поддержка Lunara\n\n"
    "По вопросам оплаты, доступа и работы бота — напиши сюда, "
    "мы ответим в ближайшее время."
)

_ASTRO_STYLE = (
    "Ты премиальный астрологический AI-сервис Lunara.\n"
    "Пиши эмоционально, красиво, современно, без сложных терминов.\n"
    "Читатель должен чувствовать: «это точно про меня».\n"
    "Коротко, атмосферно, без медицины и катастроф."
)

_FREE_PROMPT = (
    _ASTRO_STYLE
    + "\n\nБесплатный мини-разбор. Строго 4 блока с эмодзи:\n"
    "1. ✨ Кто человек (2–3 предложения)\n"
    "2. 💕 Любовь (2–3 предложения)\n"
    "3. 💰 Деньги (2–3 предложения)\n"
    "4. ⚡ Главная черта личности (2–3 предложения)"
)

_FULL_PROMPT = (
    _ASTRO_STYLE
    + "\n\nПолная натальная карта. Строго 5 блоков с эмодзи:\n"
    "1. 💕 Отношения\n"
    "2. 🌟 Предназначение\n"
    "3. 💰 Деньги\n"
    "4. 🔮 Жизненные сценарии\n"
    "5. ✨ Скрытые таланты\n"
    "В каждом — 2 коротких абзаца."
)

_COMPAT_PROMPT = (
    _ASTRO_STYLE
    + "\n\nРазбор совместимости. 5 блоков: 💕 эмоции, 🔥 притяжение, "
    "⚡ конфликты, 🌱 перспектива, 🌑 что разрушит."
)

_QUESTION_PROMPT = (
    _ASTRO_STYLE + "\n\nОтвет на вопрос по карте. 2–3 абзаца, эмодзи в заголовке."
)

_HOROSCOPE_PROMPTS = {
    "today": "Гороскоп на сегодня",
    "week": "Гороскоп на неделю",
    "month": "Гороскоп на месяц",
}

_DATE_RE = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$")
_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$")

_PROGRESS = (
    "✨ Анализирую положение планет...",
    "🌙 Изучаю твою личность...",
    "❤️ Смотрю сферу отношений...",
    "💰 Считаю денежный потенциал...",
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
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return h, mi
    return None


def _profile_prompt(data: dict) -> str:
    return (
        f"Имя: {data['name']}\n"
        f"Дата: {data['birth_date']}\n"
        f"Время: {data['birth_time']}\n"
        f"Место: {data['birth_place']}\n"
    )


async def _call_openai(system: str, user: str) -> str:
    r = await _openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    return r.choices[0].message.content or ""


async def _send_long(message: Message, text: str) -> None:
    for i in range(0, len(text), 4000):
        await message.answer(text[i : i + 4000])


async def _progress(message: Message) -> None:
    for i, t in enumerate(_PROGRESS):
        await message.answer(t)
        if i < len(_PROGRESS) - 1:
            await asyncio.sleep(1.4)


async def _get_profile(state: FSMContext) -> dict | None:
    d = await state.get_data()
    return d if d.get("name") and d.get("birth_date") else None


async def _sync_db_to_state(state: FSMContext, telegram_id: int) -> dict | None:
    row = get_user(telegram_id)
    if not row:
        return None
    await state.update_data(
        name=row["name"],
        birth_date=row["birth_date"],
        birth_time=row["birth_time"],
        birth_place=row["birth_place"],
        free_reading=row.get("free_reading") or "",
        full_reading=row.get("full_reading") or "",
    )
    return row


async def _show_menu(message: Message, telegram_id: int) -> None:
    premium = is_premium(telegram_id)
    if premium:
        text = "💎 Premium активен\n\nВыбери раздел в меню 👇"
    else:
        text = "Готово ✨\n\nВыбери раздел в меню 👇"
    await message.answer(text, reply_markup=main_menu_kb(premium))


async def _show_paywall(message: Message) -> None:
    await message.answer(PAYWALL_TEXT, reply_markup=PAYWALL_KB)


async def _require_premium_message(message: Message, telegram_id: int) -> bool:
    if is_premium(telegram_id):
        return True
    await message.answer(
        "🔒 Этот раздел доступен в Premium.\n\n" + PAYWALL_TEXT.split("\n\n", 1)[-1],
        reply_markup=PAYWALL_KB,
    )
    return False


# --- /start, onboarding ---


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    row = await _sync_db_to_state(state, tid)
    if row and row.get("name"):
        await state.set_state(None)
        name = row["name"]
        await message.answer(
            f"С возвращением, {name} ✨\nТвоя карта Lunara сохранена.",
            reply_markup=main_menu_kb(is_premium(tid)),
        )
        return
    await state.clear()
    await state.set_state(BirthForm.name)
    await message.answer(ONBOARDING_WELCOME, reply_markup=ReplyKeyboardRemove())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    await state.set_state(None)
    row = get_user(tid)
    if row:
        await _sync_db_to_state(state, tid)
        await message.answer("Отменено.", reply_markup=main_menu_kb(is_premium(tid)))
    else:
        await state.clear()
        await message.answer("Отменено. Нажми /start, чтобы начать.")


@router.message(BirthForm.name, F.text)
async def on_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Напиши имя чуть длиннее 🙏")
        return
    await state.update_data(name=name)
    await state.set_state(BirthForm.birth_date)
    await message.answer("📅 Дата рождения — ДД.ММ.ГГГГ (например, 15.03.1990)")


@router.message(BirthForm.birth_date, F.text)
async def on_date(message: Message, state: FSMContext) -> None:
    p = _parse_date(message.text)
    if not p:
        await message.answer("Формат: ДД.ММ.ГГГГ, например 08.11.2001")
        return
    y, mo, d = p
    await state.update_data(birth_date=f"{d:02d}.{mo:02d}.{y}")
    await state.set_state(BirthForm.birth_time)
    await message.answer(
        "🕐 Время рождения — ЧЧ:ММ (24ч)\nИли нажми «Не знаю»",
        reply_markup=UNKNOWN_TIME_KB,
    )


@router.message(BirthForm.birth_time, F.text)
async def on_time(message: Message, state: FSMContext) -> None:
    t = message.text.strip()
    if t == BTN_UNKNOWN_TIME:
        await state.update_data(birth_time="неизвестно")
    else:
        p = _parse_time(t)
        if not p:
            await message.answer("Формат ЧЧ:ММ или кнопка «Не знаю»")
            return
        h, mi = p
        await state.update_data(birth_time=f"{h:02d}:{mi:02d}")
    await state.set_state(BirthForm.birth_place)
    await message.answer(
        "📍 Место рождения (город, страна)",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(BirthForm.birth_place, F.text)
async def on_place(message: Message, state: FSMContext) -> None:
    place = message.text.strip()
    if len(place) < 2:
        await message.answer("Уточни город и страну")
        return
    tid = message.from_user.id if message.from_user else 0
    await state.update_data(birth_place=place)
    data = await state.get_data()

    save_user(
        tid,
        data["name"],
        data["birth_date"],
        data["birth_time"],
        place,
    )

    await state.set_state(None)
    await _progress(message)

    try:
        from chart_generator import generate_natal_chart_png

        png = await asyncio.to_thread(
            generate_natal_chart_png,
            telegram_id=tid,
            name=data["name"],
            birth_date=data["birth_date"],
            birth_time=data["birth_time"],
            birth_place=place,
        )
        await message.answer_photo(
            FSInputFile(png),
            caption="✨ Твоя натальная карта Lunara",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Chart: %s", e)
        await message.answer("Карту не удалось построить — даю текстовый разбор ✨")

    try:
        free = await _call_openai(
            _FREE_PROMPT,
            "Мини-разбор:\n\n" + _profile_prompt(data),
        )
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Ошибка OpenAI: {type(e).__name__}: {e}")
        return

    await state.update_data(free_reading=free)
    save_readings(tid, free_reading=free)
    await message.answer("🎁 Твой бесплатный разбор\n")
    await _send_long(message, free)
    await _show_paywall(message)
    await _show_menu(message, tid)


# --- Paywall ---


@router.callback_query(F.data == "pay:unlock")
async def on_pay_unlock(callback: CallbackQuery, state: FSMContext) -> None:
    tid = callback.from_user.id
    await callback.answer("Открываем полную карту… ✨")
    profile = await _get_profile(state) or await _sync_db_to_state(state, tid)
    if not profile:
        await callback.message.answer("Сначала пройди onboarding: /start")
        return

    set_premium(tid, True)
    await callback.message.answer(
        "💎 Premium активирован!\n"
        "(тестовый режим — оплата 249 ₽ будет подключена позже)"
    )

    data = await state.get_data()
    if data.get("full_reading"):
        full = data["full_reading"]
    else:
        await callback.message.answer("🌙 Создаю полную карту…")
        try:
            full = await _call_openai(
                _FULL_PROMPT,
                "Полная карта:\n\n" + _profile_prompt(data),
            )
        except Exception as e:  # noqa: BLE001
            await callback.message.answer(f"Ошибка: {e}")
            return
        await state.update_data(full_reading=full)
        save_readings(tid, full_reading=full)

    await callback.message.answer("💎 Полная натальная карта\n")
    await _send_long(callback.message, full)
    await _show_menu(callback.message, tid)


# --- Reply menu ---


@router.message(F.text == BTN_MY_CHART)
async def menu_my_chart(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    profile = await _get_profile(state) or await _sync_db_to_state(state, tid)
    if not profile:
        await message.answer("Карты ещё нет — нажми /start")
        return
    free = profile.get("free_reading") or ""
    if free:
        await message.answer("🌙 Твоя карта (бесплатный разбор)\n")
        await _send_long(message, free)
    if is_premium(tid) and profile.get("full_reading"):
        await message.answer("💎 Полная версия\n")
        await _send_long(message, profile["full_reading"])
    elif not is_premium(tid):
        await _show_paywall(message)


@router.message(F.text == BTN_PREMIUM)
async def menu_premium(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if is_premium(tid):
        await message.answer("💎 У тебя уже открыт Premium ✨")
        return
    await _show_paywall(message)


@router.message(F.text == BTN_SUPPORT)
async def menu_support(message: Message) -> None:
    await message.answer(SUPPORT_TEXT)


@router.message(F.text == BTN_COMPAT)
async def menu_compat(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if not await _require_premium_message(message, tid):
        return
    if not await _get_profile(state):
        await _sync_db_to_state(state, tid)
    await state.set_state(CompatibilityForm.partner_name)
    await message.answer("❤️ Совместимость\n\nКак зовут партнёра?")


@router.message(F.text == BTN_QUESTIONS)
async def menu_questions(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if not await _require_premium_message(message, tid):
        return
    await message.answer("🔮 Популярные вопросы — выбери:", reply_markup=POPULAR_QUESTIONS_KB)


@router.message(F.text == BTN_ASK)
async def menu_ask(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if not await _require_premium_message(message, tid):
        return
    await state.set_state(BirthForm.custom_question)
    await message.answer("✍️ Напиши свой вопрос одним сообщением")


@router.message(F.text == BTN_HOROSCOPE)
async def menu_horoscope(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if not await _require_premium_message(message, tid):
        return
    await message.answer("📅 Гороскопы — выбери период:", reply_markup=HOROSCOPE_KB)


# --- Premium: популярные вопросы, гороскоп, свой вопрос, совместимость ---


@router.callback_query(F.data.startswith("pop:"))
async def on_popular(callback: CallbackQuery, state: FSMContext) -> None:
    tid = callback.from_user.id
    if not is_premium(tid):
        await callback.answer("Только Premium", show_alert=True)
        return
    key = callback.data.split(":", 1)[1]
    q = POPULAR_QUESTIONS.get(key)
    if not q:
        await callback.answer()
        return
    profile = await _get_profile(state) or await _sync_db_to_state(state, tid)
    await callback.answer()
    await callback.message.answer(f"🔮 {q}")
    try:
        text = await _call_openai(
            _QUESTION_PROMPT,
            f"{q}\n\n{_profile_prompt(profile)}",
        )
        await _send_long(callback.message, text)
    except Exception as e:  # noqa: BLE001
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(F.data.startswith("horo:"))
async def on_horo(callback: CallbackQuery, state: FSMContext) -> None:
    tid = callback.from_user.id
    if not is_premium(tid):
        await callback.answer("Только Premium", show_alert=True)
        return
    period = callback.data.split(":", 1)[1]
    label = _HOROSCOPE_PROMPTS.get(period, "Прогноз")
    profile = await _get_profile(state) or await _sync_db_to_state(state, tid)
    await callback.answer()
    await callback.message.answer(f"📅 {label}…")
    try:
        text = await _call_openai(
            _QUESTION_PROMPT,
            f"{label} для человека:\n\n{_profile_prompt(profile)}",
        )
        await _send_long(callback.message, text)
    except Exception as e:  # noqa: BLE001
        await callback.message.answer(f"Ошибка: {e}")


@router.message(BirthForm.custom_question, F.text)
async def on_custom_q(message: Message, state: FSMContext) -> None:
    tid = message.from_user.id if message.from_user else 0
    if not is_premium(tid):
        await _require_premium_message(message, tid)
        return
    q = message.text.strip()
    if len(q) < 3:
        await message.answer("Вопрос покороче 🙂")
        return
    profile = await _get_profile(state) or await _sync_db_to_state(state, tid)
    await state.set_state(None)
    await message.answer("✍️ Ищу ответ…")
    try:
        text = await _call_openai(_QUESTION_PROMPT, f"{q}\n\n{_profile_prompt(profile)}")
        await _send_long(message, text)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Ошибка: {e}")


@router.message(CompatibilityForm.partner_name, F.text)
async def on_partner_name(message: Message, state: FSMContext) -> None:
    n = message.text.strip()
    if len(n) < 2:
        await message.answer("Имя партнёра подлиннее")
        return
    await state.update_data(partner_name=n)
    await state.set_state(CompatibilityForm.partner_birth_date)
    await message.answer(f"📅 Дата рождения {n} — ДД.ММ.ГГГГ")


@router.message(CompatibilityForm.partner_birth_date, F.text)
async def on_partner_date(message: Message, state: FSMContext) -> None:
    p = _parse_date(message.text)
    if not p:
        await message.answer("Формат ДД.ММ.ГГГГ")
        return
    y, mo, d = p
    data = await state.get_data()
    profile = await _get_profile(state)
    partner = data.get("partner_name", "Партнёр")
    date_s = f"{d:02d}.{mo:02d}.{y}"
    await state.set_state(None)
    await message.answer("❤️ Считаю совместимость…")
    prompt = (
        f"Партнёр: {partner}, {date_s}\n\n"
        f"Пользователь:\n{_profile_prompt(profile)}"
    )
    try:
        text = await _call_openai(_COMPAT_PROMPT, prompt)
        await _send_long(message, text)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"Ошибка: {e}")
