import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove

from database import get_user, premium, save_texts, set_premium, upsert_user
from keyboards import (
    BTN_ASK,
    BTN_CHART,
    BTN_COMPAT,
    BTN_HORO,
    BTN_NO_TIME,
    BTN_PREMIUM,
    BTN_QUESTIONS,
    BTN_SUPPORT,
    KB_HORO,
    KB_PAYWALL,
    KB_POPULAR,
    KB_TIME,
    PAYWALL_TEXT,
    POPULAR,
    menu_kb,
)
from services import (
    HORO_LABELS,
    PROMPT_ANSWER,
    PROMPT_COMPAT,
    PROMPT_FREE,
    PROMPT_FULL,
    ask_ai,
    parse_date,
    parse_time,
    profile_text,
)
from states import Ask, Onboarding, Partner

log = logging.getLogger(__name__)
router = Router()

WELCOME = (
    "✨ Добро пожаловать в Lunara\n\n"
    "Создам твою натальную карту и расскажу про тебя, любовь и деньги.\n\n"
    "Шаг 1 из 4 — как тебя зовут?"
)

STEPS = (
    "✨ Считаю положение планет…",
    "🌙 Изучаю личность…",
    "❤️ Смотрю отношения…",
    "💰 Анализирую деньги…",
)


async def send_chunks(msg: Message, text: str) -> None:
    for i in range(0, len(text), 4000):
        await msg.answer(text[i : i + 4000])


async def anim(msg: Message) -> None:
    for i, s in enumerate(STEPS):
        await msg.answer(s)
        if i < len(STEPS) - 1:
            await asyncio.sleep(1.2)


def tid(msg: Message) -> int:
    return msg.from_user.id if msg.from_user else 0


async def show_menu(msg: Message, user_id: int) -> None:
    p = premium(user_id)
    await msg.answer("Выбери раздел 👇", reply_markup=menu_kb(p))


# ─── /start ───────────────────────────────────────────────────────────


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    u = get_user(tid(msg))
    if u and u.get("name"):
        await msg.answer(
            f"С возвращением, {u['name']} ✨",
            reply_markup=menu_kb(premium(tid(msg))),
        )
        return
    await state.set_state(Onboarding.name)
    await msg.answer(WELCOME, reply_markup=ReplyKeyboardRemove())


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    u = get_user(tid(msg))
    if u:
        await msg.answer("Отменено.", reply_markup=menu_kb(premium(tid(msg))))
    else:
        await msg.answer("Отменено. /start — начать.")


# ─── Onboarding ───────────────────────────────────────────────────────


@router.message(Onboarding.name, F.text)
async def on_name(msg: Message, state: FSMContext) -> None:
    name = msg.text.strip()
    if len(name) < 2:
        await msg.answer("Напиши имя полностью 🙏")
        return
    await state.update_data(name=name)
    await state.set_state(Onboarding.date)
    await msg.answer("Шаг 2 из 4 — дата рождения (ДД.ММ.ГГГГ)")


@router.message(Onboarding.date, F.text)
async def on_date(msg: Message, state: FSMContext) -> None:
    d = parse_date(msg.text)
    if not d:
        await msg.answer("Формат: 15.03.1990")
        return
    await state.update_data(birth_date=d)
    await state.set_state(Onboarding.time)
    await msg.answer("Шаг 3 из 4 — время (ЧЧ:ММ) или «Не знаю»", reply_markup=KB_TIME)


@router.message(Onboarding.time, F.text)
async def on_time(msg: Message, state: FSMContext) -> None:
    t = parse_time(msg.text)
    if not t:
        await msg.answer("ЧЧ:ММ или кнопка «Не знаю»")
        return
    await state.update_data(birth_time=t)
    await state.set_state(Onboarding.place)
    await msg.answer("Шаг 4 из 4 — место рождения (город, страна)", reply_markup=ReplyKeyboardRemove())


@router.message(Onboarding.place, F.text)
async def on_place(msg: Message, state: FSMContext) -> None:
    place = msg.text.strip()
    if len(place) < 2:
        await msg.answer("Укачни город и страну")
        return

    data = await state.get_data()
    user_id = tid(msg)
    upsert_user(
        user_id,
        data["name"],
        data["birth_date"],
        data["birth_time"],
        place,
    )
    user = get_user(user_id)
    await state.clear()

    await anim(msg)

    try:
        from chart_generator import generate_natal_chart_png

        path = await asyncio.to_thread(
            generate_natal_chart_png,
            telegram_id=user_id,
            name=user["name"],
            birth_date=user["birth_date"],
            birth_time=user["birth_time"],
            birth_place=place,
        )
        await msg.answer_photo(FSInputFile(path), caption="✨ Твоя натальная карта")
    except Exception as e:
        log.warning("chart: %s", e)
        await msg.answer("Карту не удалось построить — даю текстовый разбор.")

    try:
        free = await ask_ai(PROMPT_FREE, "Данные:\n" + profile_text(user))
    except Exception as e:
        await msg.answer(f"Ошибка OpenAI: {e}\nПроверь OPENAI_API_KEY на Railway.")
        return

    save_texts(user_id, free=free)
    await msg.answer("🎁 Бесплатный разбор\n")
    await send_chunks(msg, free)
    await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)
    await show_menu(msg, user_id)


# ─── Paywall ──────────────────────────────────────────────────────────


@router.callback_query(F.data == "pay")
async def on_pay(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    user = get_user(user_id)
    if not user:
        await cb.answer("Сначала /start", show_alert=True)
        return
    await cb.answer()
    set_premium(user_id, True)
    await cb.message.answer(
        "💎 Premium открыт!\n(тест: оплата 249 ₽ подключим позже)"
    )

    if user.get("full_reading"):
        full = user["full_reading"]
    else:
        await cb.message.answer("Создаю полную карту…")
        try:
            full = await ask_ai(PROMPT_FULL, "Данные:\n" + profile_text(user))
        except Exception as e:
            await cb.message.answer(f"Ошибка: {e}")
            return
        save_texts(user_id, full=full)

    await cb.message.answer("💎 Полная натальная карта\n")
    await send_chunks(cb.message, full)
    await show_menu(cb.message, user_id)


# ─── Меню (только вне FSM) ───────────────────────────────────────────


@router.message(StateFilter(None), F.text == BTN_CHART)
async def m_chart(msg: Message) -> None:
    u = get_user(tid(msg))
    if not u:
        await msg.answer("Сначала /start")
        return
    if u.get("free_reading"):
        await msg.answer("🌙 Бесплатный разбор\n")
        await send_chunks(msg, u["free_reading"])
    if premium(tid(msg)) and u.get("full_reading"):
        await msg.answer("💎 Полная карта\n")
        await send_chunks(msg, u["full_reading"])
    elif not premium(tid(msg)):
        await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)


@router.message(StateFilter(None), F.text == BTN_PREMIUM)
async def m_premium(msg: Message) -> None:
    if premium(tid(msg)):
        await msg.answer("💎 Premium уже активен ✨")
        return
    await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)


@router.message(StateFilter(None), F.text == BTN_SUPPORT)
async def m_support(msg: Message) -> None:
    await msg.answer(
        "💬 Поддержка Lunara\n\n"
        "Напиши сюда свой вопрос — поможем с доступом и оплатой."
    )


@router.message(StateFilter(None), F.text == BTN_COMPAT)
async def m_compat(msg: Message, state: FSMContext) -> None:
    if not premium(tid(msg)):
        await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)
        return
    await state.set_state(Partner.name)
    await msg.answer("❤️ Совместимость\n\nИмя партнёра?")


@router.message(StateFilter(None), F.text == BTN_QUESTIONS)
async def m_questions(msg: Message) -> None:
    if not premium(tid(msg)):
        await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)
        return
    await msg.answer("🔮 Популярные вопросы:", reply_markup=KB_POPULAR)


@router.message(StateFilter(None), F.text == BTN_ASK)
async def m_ask(msg: Message, state: FSMContext) -> None:
    if not premium(tid(msg)):
        await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)
        return
    await state.set_state(Ask.waiting)
    await msg.answer("✍️ Напиши свой вопрос одним сообщением")


@router.message(StateFilter(None), F.text == BTN_HORO)
async def m_horo(msg: Message) -> None:
    if not premium(tid(msg)):
        await msg.answer(PAYWALL_TEXT, reply_markup=KB_PAYWALL)
        return
    await msg.answer("📅 Гороскоп:", reply_markup=KB_HORO)


# ─── Premium: вопросы, гороскоп ───────────────────────────────────────


@router.callback_query(F.data.startswith("q:"))
async def cb_question(cb: CallbackQuery) -> None:
    if not premium(cb.from_user.id):
        await cb.answer("Нужен Premium", show_alert=True)
        return
    key = cb.data.split(":")[1]
    q = POPULAR.get(key)
    if not q:
        await cb.answer()
        return
    u = get_user(cb.from_user.id)
    await cb.answer()
    await cb.message.answer(f"🔮 {q}")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(u)}")
        await send_chunks(cb.message, text)
    except Exception as e:
        await cb.message.answer(f"Ошибка: {e}")


@router.callback_query(F.data.startswith("h:"))
async def cb_horo(cb: CallbackQuery) -> None:
    if not premium(cb.from_user.id):
        await cb.answer("Нужен Premium", show_alert=True)
        return
    period = cb.data.split(":")[1]
    label = HORO_LABELS.get(period, "Прогноз")
    u = get_user(cb.from_user.id)
    await cb.answer()
    await cb.message.answer(f"📅 {label}…")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"Гороскоп {label.lower()}:\n\n{profile_text(u)}")
        await send_chunks(cb.message, text)
    except Exception as e:
        await cb.message.answer(f"Ошибка: {e}")


@router.message(Ask.waiting, F.text)
async def on_ask_text(msg: Message, state: FSMContext) -> None:
    q = msg.text.strip()
    if len(q) < 3:
        await msg.answer("Вопрос подлиннее 🙂")
        return
    await state.clear()
    u = get_user(tid(msg))
    await msg.answer("✍️ Ищу ответ…")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(u)}")
        await send_chunks(msg, text)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    await show_menu(msg, tid(msg))


# ─── Совместимость ────────────────────────────────────────────────────


@router.message(Partner.name, F.text)
async def p_name(msg: Message, state: FSMContext) -> None:
    n = msg.text.strip()
    if len(n) < 2:
        await msg.answer("Имя партнёра подлиннее")
        return
    await state.update_data(pname=n)
    await state.set_state(Partner.date)
    await msg.answer(f"Дата рождения {n} (ДД.ММ.ГГГГ)")


@router.message(Partner.date, F.text)
async def p_date(msg: Message, state: FSMContext) -> None:
    d = parse_date(msg.text)
    if not d:
        await msg.answer("Формат ДД.ММ.ГГГГ")
        return
    data = await state.get_data()
    u = get_user(tid(msg))
    await state.clear()
    await msg.answer("❤️ Считаю совместимость…")
    try:
        text = await ask_ai(
            PROMPT_COMPAT,
            f"Партнёр: {data['pname']}, {d}\n\nПользователь:\n{profile_text(u)}",
        )
        await send_chunks(msg, text)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    await show_menu(msg, tid(msg))


# ─── Любой текст вне сценария ─────────────────────────────────────────


@router.message(StateFilter(None), F.text)
async def any_text(msg: Message) -> None:
    if msg.text.startswith("/"):
        return
    u = get_user(tid(msg))
    if u:
        await msg.answer("Выбери кнопку в меню 👇", reply_markup=menu_kb(premium(tid(msg))))
    else:
        await msg.answer("Нажми /start чтобы начать ✨")
