import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove

from access import (
    can_ask_custom,
    can_compat,
    can_full_chart,
    can_popular,
    custom_questions_left,
    has_horo_today,
    has_premium,
    horo_status_line,
    horo_subscription_active,
)
from database import (
    add_custom_questions,
    get_user,
    grant_horo_subscription,
    grant_horo_today,
    is_profile_complete,
    save_progress,
    save_texts,
    set_premium,
    upsert_user,
    use_custom_question,
)
from horo_scheduler import send_daily_horo
from keyboards import (
    BTN_ASK,
    BTN_CANCEL,
    BTN_CHART,
    BTN_COMPAT,
    BTN_HORO,
    BTN_PREMIUM,
    BTN_QUESTIONS,
    BTN_SUPPORT,
    KB_ASK,
    KB_HORO_MENU,
    KB_ONBOARD,
    KB_PAYWALL_ASK,
    KB_PAYWALL_HORO,
    KB_PAYWALL_PREMIUM,
    KB_POPULAR,
    KB_TIME,
    PAYWALL_ASK_TEXT,
    PAYWALL_HORO_TEXT,
    PAYWALL_PREMIUM_TEXT,
    POPULAR,
    menu_kb,
)
from services import (
    PROMPT_ANSWER,
    PROMPT_COMPAT,
    PROMPT_FREE,
    PROMPT_FULL,
    PROMPT_HORO_TODAY,
    ask_ai,
    parse_date,
    parse_time,
    profile_text,
)
from states import Ask, Onboarding, Partner

log = logging.getLogger(__name__)
router = Router()

CHART_TIMEOUT_SEC = 45
TEST_NOTE = "\n\n(тест: оплата подключим позже)"

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


def menu_for(user_id: int):
    u = get_user(user_id)
    return menu_kb(has_premium(u))


async def show_menu(msg: Message, user_id: int) -> None:
    await msg.answer("Выбери раздел 👇", reply_markup=menu_for(user_id))


async def prompt_custom_question(
    msg: Message, state: FSMContext, user_id: int
) -> None:
    u = get_user(user_id)
    left = custom_questions_left(u)
    if left <= 0:
        await state.clear()
        await msg.answer(PAYWALL_ASK_TEXT, reply_markup=KB_PAYWALL_ASK)
        return
    await state.set_state(Ask.waiting)
    await msg.answer(
        f"✍️ Напиши свой вопрос одним сообщением\n"
        f"Осталось вопросов: {left}",
        reply_markup=KB_ASK,
    )


async def deliver_full_chart(msg: Message, user_id: int) -> None:
    user = get_user(user_id)
    if not user:
        return
    if user.get("full_reading"):
        await msg.answer("💎 Полная натальная карта\n")
        await send_chunks(msg, user["full_reading"])
        return
    await msg.answer("Создаю полную карту…")
    try:
        full = await ask_ai(PROMPT_FULL, "Данные:\n" + profile_text(user))
        save_texts(user_id, full=full)
        await msg.answer("💎 Полная натальная карта\n")
        await send_chunks(msg, full)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")


async def deliver_today_horo(msg: Message, user_id: int) -> None:
    user = get_user(user_id)
    await msg.answer("📅 Гороскоп на сегодня…")
    try:
        text = await ask_ai(
            PROMPT_HORO_TODAY,
            f"Сегодня\n\n{profile_text(user)}",
        )
        await send_chunks(msg, text)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")


def onboarding_data(data: dict, user_id: int) -> dict | None:
    db = get_user(user_id) or {}
    merged = {
        "name": data.get("name") or db.get("name"),
        "birth_date": data.get("birth_date") or db.get("birth_date"),
        "birth_time": data.get("birth_time") or db.get("birth_time"),
        "birth_place": data.get("birth_place") or db.get("birth_place"),
    }
    if not all(merged.values()):
        return None
    return merged


async def finish_onboarding(msg: Message, state: FSMContext, place: str) -> None:
    user_id = tid(msg)
    data = await state.get_data()
    data["birth_place"] = place
    profile = onboarding_data(data, user_id)
    if not profile:
        await state.set_state(Onboarding.name)
        await msg.answer(
            "Сессия сбросилась. Начнём заново — как тебя зовут?",
            reply_markup=KB_ONBOARD,
        )
        return

    upsert_user(
        user_id,
        profile["name"],
        profile["birth_date"],
        profile["birth_time"],
        place,
    )
    user = get_user(user_id)
    await state.clear()

    await msg.answer(
        "✨ Приняла! Считаю карту и готовлю разбор — это 1–2 минуты.",
        reply_markup=menu_for(user_id),
    )

    await anim(msg)

    try:
        from chart_generator import generate_natal_chart_png

        path = await asyncio.wait_for(
            asyncio.to_thread(
                generate_natal_chart_png,
                telegram_id=user_id,
                name=user["name"],
                birth_date=user["birth_date"],
                birth_time=user["birth_time"],
                birth_place=place,
            ),
            timeout=CHART_TIMEOUT_SEC,
        )
        await msg.answer_photo(FSInputFile(path), caption="✨ Твоя натальная карта")
    except asyncio.TimeoutError:
        log.warning("chart timeout user=%s", user_id)
        await msg.answer("Карта долго строилась — продолжаю с текстовым разбором.")
    except Exception as e:
        log.warning("chart: %s", e)
        await msg.answer("Карту не удалось построить — даю текстовый разбор.")

    try:
        free = await ask_ai(PROMPT_FREE, "Данные:\n" + profile_text(user))
        save_texts(user_id, free=free)
        await msg.answer("🎁 Бесплатный разбор\n")
        await send_chunks(msg, free)
    except asyncio.TimeoutError:
        await msg.answer("Разбор занял слишком долго. Нажми 🌙 Моя карта позже.")
    except Exception as e:
        log.error("openai free: %s", e)
        await msg.answer(f"Не удалось получить разбор: {e}")

    await msg.answer(PAYWALL_PREMIUM_TEXT, reply_markup=KB_PAYWALL_PREMIUM)
    await show_menu(msg, user_id)


# ─── /start ───────────────────────────────────────────────────────────


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    u = get_user(tid(msg))
    if is_profile_complete(u):
        await msg.answer(
            f"С возвращением, {u['name']} ✨",
            reply_markup=menu_for(tid(msg)),
        )
        return
    await state.set_state(Onboarding.name)
    await msg.answer(WELCOME, reply_markup=KB_ONBOARD)


@router.message(Command("cancel"))
@router.message(StateFilter(Onboarding), F.text == BTN_CANCEL)
async def cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    u = get_user(tid(msg))
    if is_profile_complete(u):
        await msg.answer("Отменено.", reply_markup=menu_for(tid(msg)))
    else:
        await msg.answer(
            "Онбординг отменён. Нажми /start чтобы начать снова ✨",
            reply_markup=ReplyKeyboardRemove(),
        )


# ─── Onboarding ───────────────────────────────────────────────────────


@router.message(Onboarding.name, F.text)
async def on_name(msg: Message, state: FSMContext) -> None:
    if msg.text == BTN_CANCEL:
        return
    name = msg.text.strip()
    if len(name) < 2:
        await msg.answer("Напиши имя полностью 🙏")
        return
    await state.update_data(name=name)
    save_progress(tid(msg), name=name)
    await state.set_state(Onboarding.date)
    await msg.answer("Шаг 2 из 4 — дата рождения (ДД.ММ.ГГГГ)", reply_markup=KB_ONBOARD)


@router.message(Onboarding.date, F.text)
async def on_date(msg: Message, state: FSMContext) -> None:
    if msg.text == BTN_CANCEL:
        return
    d = parse_date(msg.text)
    if not d:
        await msg.answer("Формат: 15.03.1990")
        return
    await state.update_data(birth_date=d)
    save_progress(tid(msg), birth_date=d)
    await state.set_state(Onboarding.time)
    await msg.answer("Шаг 3 из 4 — время (ЧЧ:ММ) или «Не знаю»", reply_markup=KB_TIME)


@router.message(Onboarding.time, F.text)
async def on_time(msg: Message, state: FSMContext) -> None:
    if msg.text == BTN_CANCEL:
        return
    t = parse_time(msg.text)
    if not t:
        await msg.answer("ЧЧ:ММ или кнопка «Не знаю»")
        return
    await state.update_data(birth_time=t)
    save_progress(tid(msg), birth_time=t)
    await state.set_state(Onboarding.place)
    await msg.answer(
        "Шаг 4 из 4 — место рождения (город, страна)\n"
        "Например: Москва, Россия",
        reply_markup=KB_ONBOARD,
    )


@router.message(Onboarding.place, F.location)
async def on_place_location(msg: Message, state: FSMContext) -> None:
    await msg.answer(
        "📍 Геолокацию вижу. Для точной карты напиши город текстом:\n"
        "Москва, Россия",
        reply_markup=KB_ONBOARD,
    )


@router.message(Onboarding.place, F.text)
async def on_place(msg: Message, state: FSMContext) -> None:
    if msg.text == BTN_CANCEL:
        return
    place = msg.text.strip()
    if len(place) < 2:
        await msg.answer("Укажи город и страну, например: Москва, Россия")
        return
    await finish_onboarding(msg, state, place)


# ─── Оплата (тест) ────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("pay:"))
async def on_pay(cb: CallbackQuery, state: FSMContext) -> None:
    user_id = cb.from_user.id
    user = get_user(user_id)
    if not user or not is_profile_complete(user):
        await cb.answer("Сначала /start", show_alert=True)
        return

    parts = cb.data.split(":")
    await cb.answer()

    if parts[1] == "premium":
        set_premium(user_id, True)
        await cb.message.answer(f"💎 Premium активирован!{TEST_NOTE}")
        await deliver_full_chart(cb.message, user_id)
        await show_menu(cb.message, user_id)
        return

    if parts[1] == "ask" and len(parts) == 3:
        count = int(parts[2])
        add_custom_questions(user_id, count)
        u = get_user(user_id)
        left = custom_questions_left(u)
        await cb.message.answer(
            f"✍️ Пакет на {count} вопросов открыт!{TEST_NOTE}\n"
            f"Можешь задать {left} вопрос(ов)."
        )
        await prompt_custom_question(cb.message, state, user_id)
        return

    if parts[1] == "horo" and len(parts) == 3:
        kind = parts[2]
        if kind == "today":
            grant_horo_today(user_id)
            await cb.message.answer(f"📅 Гороскоп «Сегодня» открыт!{TEST_NOTE}")
            await deliver_today_horo(cb.message, user_id)
        elif kind == "week":
            grant_horo_subscription(user_id, "week", 7)
            await cb.message.answer(
                f"📅 Подписка «Неделя» активна — 7 дней подряд!{TEST_NOTE}"
            )
            fresh = get_user(user_id)
            await send_daily_horo(cb.bot, fresh, 1, 7)
        elif kind == "month":
            grant_horo_subscription(user_id, "month", 30)
            await cb.message.answer(
                f"📅 Подписка «Месяц» активна — 30 дней подряд!{TEST_NOTE}"
            )
            fresh = get_user(user_id)
            await send_daily_horo(cb.bot, fresh, 1, 30)
        await show_menu(cb.message, user_id)
        return


# ─── Гороскопы (меню) ─────────────────────────────────────────────────


@router.callback_query(F.data.startswith("horo:"))
async def cb_horo_menu(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    u = get_user(user_id)
    if not is_profile_complete(u):
        await cb.answer("Сначала /start", show_alert=True)
        return

    kind = cb.data.split(":")[1]
    await cb.answer()

    u = get_user(user_id)

    if kind == "today":
        if has_horo_today(u):
            await deliver_today_horo(cb.message, user_id)
        else:
            await cb.message.answer(PAYWALL_HORO_TEXT, reply_markup=KB_PAYWALL_HORO)
        return

    if kind in ("week", "month") and horo_subscription_active(u) and u.get("horo_sub_kind") == kind:
        left = int(u["horo_sub_days_total"]) - int(u["horo_days_delivered"])
        await cb.message.answer(
            f"📅 Подписка «{kind}» уже активна.\n"
            f"Осталось дней: {left}. Гороскоп приходит каждый день ✨"
        )
        return

    await cb.message.answer(PAYWALL_HORO_TEXT, reply_markup=KB_PAYWALL_HORO)


# ─── Меню ─────────────────────────────────────────────────────────────


@router.message(StateFilter(None), F.text == BTN_CHART)
async def m_chart(msg: Message) -> None:
    u = get_user(tid(msg))
    if not is_profile_complete(u):
        await msg.answer("Сначала /start — создадим карту")
        return
    if u.get("free_reading"):
        await msg.answer("🌙 Бесплатный разбор\n")
        await send_chunks(msg, u["free_reading"])
    else:
        await msg.answer("Разбор ещё не готов. Подожди или нажми /start.")
    if can_full_chart(u):
        await deliver_full_chart(msg, tid(msg))
    elif not has_premium(u):
        await msg.answer(PAYWALL_PREMIUM_TEXT, reply_markup=KB_PAYWALL_PREMIUM)


@router.message(StateFilter(None), F.text == BTN_PREMIUM)
async def m_premium(msg: Message) -> None:
    u = get_user(tid(msg))
    if has_premium(u):
        await msg.answer("💎 Premium уже активен ✨")
        if not u.get("full_reading"):
            await deliver_full_chart(msg, tid(msg))
        return
    await msg.answer(PAYWALL_PREMIUM_TEXT, reply_markup=KB_PAYWALL_PREMIUM)


@router.message(StateFilter(None), F.text == BTN_SUPPORT)
async def m_support(msg: Message) -> None:
    await msg.answer(
        "💬 Поддержка Lunara\n\n"
        "Напиши сюда свой вопрос — поможем с доступом и оплатой."
    )


@router.message(StateFilter(None), F.text == BTN_COMPAT)
async def m_compat(msg: Message, state: FSMContext) -> None:
    u = get_user(tid(msg))
    if not can_compat(u):
        await msg.answer(PAYWALL_PREMIUM_TEXT, reply_markup=KB_PAYWALL_PREMIUM)
        return
    await state.set_state(Partner.name)
    await msg.answer("❤️ Совместимость\n\nИмя партнёра?")


@router.message(StateFilter(None), F.text == BTN_QUESTIONS)
async def m_questions(msg: Message) -> None:
    u = get_user(tid(msg))
    if not can_popular(u):
        await msg.answer(PAYWALL_PREMIUM_TEXT, reply_markup=KB_PAYWALL_PREMIUM)
        return
    await msg.answer("🔮 Популярные вопросы:", reply_markup=KB_POPULAR)


@router.message(StateFilter(None), F.text == BTN_ASK)
async def m_ask(msg: Message, state: FSMContext) -> None:
    u = get_user(tid(msg))
    if not can_ask_custom(u):
        await msg.answer(PAYWALL_ASK_TEXT, reply_markup=KB_PAYWALL_ASK)
        return
    await prompt_custom_question(msg, state, tid(msg))


@router.message(StateFilter(None), F.text == BTN_HORO)
async def m_horo(msg: Message) -> None:
    u = get_user(tid(msg))
    status = horo_status_line(u)
    header = "📅 Гороскопы\n"
    if status:
        header += f"\n{status}\n"
    header += "\nВыбери период:"
    await msg.answer(header, reply_markup=KB_HORO_MENU)


@router.callback_query(F.data.startswith("q:"))
async def cb_question(cb: CallbackQuery) -> None:
    u = get_user(cb.from_user.id)
    if not can_popular(u):
        await cb.answer("Нужен Premium", show_alert=True)
        return
    key = cb.data.split(":")[1]
    q = POPULAR.get(key)
    if not q:
        await cb.answer()
        return
    await cb.answer()
    await cb.message.answer(f"🔮 {q}")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(u)}")
        await send_chunks(cb.message, text)
    except Exception as e:
        await cb.message.answer(f"Ошибка: {e}")


@router.message(Ask.waiting, F.text == BTN_CANCEL)
async def on_ask_cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    left = custom_questions_left(get_user(tid(msg)))
    note = f"\n\nНеиспользованных вопросов: {left}." if left else ""
    await msg.answer(f"Вопросы отложены.{note}", reply_markup=menu_for(tid(msg)))


@router.message(Ask.waiting, F.text)
async def on_ask_text(msg: Message, state: FSMContext) -> None:
    user_id = tid(msg)
    u = get_user(user_id)
    if not can_ask_custom(u):
        await state.clear()
        await msg.answer(PAYWALL_ASK_TEXT, reply_markup=KB_PAYWALL_ASK)
        return
    q = msg.text.strip()
    if len(q) < 3:
        await msg.answer("Вопрос подлиннее 🙂")
        return

    await msg.answer("✍️ Ищу ответ…")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(u)}")
        if not use_custom_question(user_id):
            await state.clear()
            await msg.answer(PAYWALL_ASK_TEXT, reply_markup=KB_PAYWALL_ASK)
            return
        left = custom_questions_left(get_user(user_id))
        await send_chunks(msg, text)
        if left > 0:
            await msg.answer(f"Использовано. Осталось вопросов: {left}")
            await prompt_custom_question(msg, state, user_id)
        else:
            await state.clear()
            await msg.answer(
                "✨ Пакет вопросов использован.\n"
                "Чтобы задать ещё — купи новый пакет в ✍️ Задать вопрос.",
                reply_markup=menu_for(user_id),
            )
    except Exception as e:
        await msg.answer(f"Ошибка: {e}\nПопробуй написать вопрос ещё раз.")
        await prompt_custom_question(msg, state, user_id)


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


@router.message(StateFilter(None), F.text)
async def any_text(msg: Message) -> None:
    if msg.text.startswith("/"):
        return
    u = get_user(tid(msg))
    if is_profile_complete(u):
        await msg.answer("Выбери кнопку в меню 👇", reply_markup=menu_for(tid(msg)))
    else:
        await msg.answer("Нажми /start чтобы начать ✨")
