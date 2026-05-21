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
    has_horo_today,
    has_premium,
    horo_status_line,
    question_balance,
)
from database import (
    add_chart_questions,
    create_chart,
    get_active_chart,
    get_chart,
    get_user,
    grant_chart_horo,
    is_profile_complete,
    list_charts,
    save_chart_texts,
    set_active_chart,
    set_chart_premium,
    use_chart_question,
)
from horo_scheduler import send_daily_horo
from keyboards import (
    BTN_ASK,
    BTN_CANCEL,
    BTN_CHART,
    BTN_COMPAT,
    BTN_HORO,
    BTN_MY_CHARTS,
    BTN_NEW_CHART,
    BTN_PREMIUM,
    BTN_QUESTIONS,
    BTN_SUPPORT,
    KB_ASK,
    KB_ONBOARD,
    KB_POPULAR,
    KB_TIME,
    POPULAR,
    charts_list_kb,
    menu_kb,
)
from paywalls import send_paywall_ask, send_paywall_horo, send_paywall_premium
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
TEST_NOTE = "\n\n_Оплата в тестовом режиме — доступ открыт сразу._"

WELCOME = (
    "✨ Добро пожаловать в Lunara\n\n"
    "Создам твою натальную карту и расскажу про тебя, любовь и деньги.\n\n"
    "Шаг 1 из 4 — как тебя зовут?"
)

WELCOME_NEW = (
    "➕ Новая натальная карта\n\n"
    "Шаг 1 из 4 — имя для этой карты (как подписать профиль)?"
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
    chart = get_active_chart(user_id)
    return menu_kb(has_premium(chart))


async def show_menu(msg: Message, user_id: int) -> None:
    await msg.answer("Выбери раздел 👇", reply_markup=menu_for(user_id))


async def prompt_custom_question(
    msg: Message, state: FSMContext, user_id: int
) -> None:
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Выбери активную карту в 📋 Все карты")
        return
    left = question_balance(chart)
    if left <= 0:
        await state.clear()
        await send_paywall_ask(msg)
        return
    await state.set_state(Ask.waiting)
    await msg.answer(
        f"✍️ Напиши свой вопрос одним сообщением\n"
        f"Осталось вопросов: {left}",
        reply_markup=KB_ASK,
    )


async def deliver_full_chart(msg: Message, user_id: int) -> None:
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Сначала выбери или создай карту в 📋 Все карты")
        return
    if chart.get("full_reading"):
        await msg.answer(f"💎 Полная карта · {chart['profile_name']}\n")
        await send_chunks(msg, chart["full_reading"])
        return
    await msg.answer("Создаю полную карту…")
    try:
        full = await ask_ai(PROMPT_FULL, "Данные:\n" + profile_text(chart))
        save_chart_texts(chart["id"], full=full)
        await msg.answer(f"💎 Полная карта · {chart['profile_name']}\n")
        await send_chunks(msg, full)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")


async def deliver_today_horo(msg: Message, user_id: int) -> None:
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Сначала выбери активную карту в 📋 Все карты")
        return
    await msg.answer(f"📅 Прогноз на сегодня · {chart['profile_name']}…")
    try:
        text = await ask_ai(
            PROMPT_HORO_TODAY,
            f"Сегодня\n\n{profile_text(chart)}",
        )
        await send_chunks(msg, text)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")


def onboarding_data(data: dict) -> dict | None:
    merged = {
        "name": data.get("name"),
        "birth_date": data.get("birth_date"),
        "birth_time": data.get("birth_time"),
        "birth_place": data.get("birth_place"),
    }
    if not all(merged.values()):
        return None
    return merged


async def finish_onboarding(msg: Message, state: FSMContext, place: str) -> None:
    user_id = tid(msg)
    data = await state.get_data()
    data["birth_place"] = place
    profile = onboarding_data(data)
    if not profile:
        await state.set_state(Onboarding.name)
        await msg.answer(
            "Сессия сбросилась. Начнём заново — как тебя зовут?",
            reply_markup=KB_ONBOARD,
        )
        return

    chart = create_chart(
        user_id,
        profile["name"],
        profile["birth_date"],
        profile["birth_time"],
        place,
    )
    await state.clear()

    await msg.answer(
        f"✨ Карта «{chart['profile_name']}» создана!\n"
        "Считаю положение планет — 1–2 минуты.",
        reply_markup=menu_for(user_id),
    )

    await anim(msg)

    try:
        from chart_generator import generate_natal_chart_png

        path = await asyncio.wait_for(
            asyncio.to_thread(
                generate_natal_chart_png,
                chart_id=chart["id"],
                telegram_id=user_id,
                name=chart["profile_name"],
                birth_date=chart["birth_date"],
                birth_time=chart["birth_time"],
                birth_place=place,
            ),
            timeout=CHART_TIMEOUT_SEC,
        )
        await msg.answer_photo(
            FSInputFile(path),
            caption=f"✨ {chart['profile_name']}",
        )
    except asyncio.TimeoutError:
        log.warning("chart timeout user=%s chart=%s", user_id, chart["id"])
        await msg.answer("Карта долго строилась — продолжаю с текстовым разбором.")
    except Exception as e:
        log.warning("chart: %s", e)
        await msg.answer("Карту не удалось построить — даю текстовый разбор.")

    try:
        free = await ask_ai(PROMPT_FREE, "Данные:\n" + profile_text(chart))
        save_chart_texts(chart["id"], free=free)
        await msg.answer("🎁 Бесплатный разбор\n")
        await send_chunks(msg, free)
    except asyncio.TimeoutError:
        await msg.answer("Разбор занял слишком долго. Открой ✨ Текущая карта позже.")
    except Exception as e:
        log.error("openai free: %s", e)
        await msg.answer(f"Не удалось получить разбор: {e}")

    await send_paywall_premium(msg)
    await show_menu(msg, user_id)


# ─── /start ───────────────────────────────────────────────────────────


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if chart:
        await msg.answer(
            f"С возвращением ✨\nАктивная карта: *{chart['profile_name']}*",
            reply_markup=menu_for(user_id),
            parse_mode="Markdown",
        )
        return
    await state.set_state(Onboarding.name)
    await msg.answer(WELCOME, reply_markup=KB_ONBOARD)


@router.message(Command("cancel"))
@router.message(StateFilter(Onboarding), F.text == BTN_CANCEL)
async def cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    if is_profile_complete(tid(msg)):
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
    if not is_profile_complete(user_id):
        await cb.answer("Сначала создай карту — /start", show_alert=True)
        return
    chart = get_active_chart(user_id)
    if not chart:
        await cb.answer("Выбери активную карту", show_alert=True)
        return

    parts = cb.data.split(":")
    await cb.answer()
    cname = chart["profile_name"]

    if parts[1] == "premium":
        set_chart_premium(chart["id"], True)
        await cb.message.answer(
            f"💎 Premium для «{cname}» активирован.{TEST_NOTE}",
            parse_mode="Markdown",
        )
        await deliver_full_chart(cb.message, user_id)
        await show_menu(cb.message, user_id)
        return

    if parts[1] == "ask" and len(parts) == 3:
        count = int(parts[2])
        add_chart_questions(chart["id"], count)
        chart = get_chart(chart["id"], user_id)
        left = question_balance(chart)
        await cb.message.answer(
            f"✍️ +{count} вопросов для «{cname}»{TEST_NOTE}\n"
            f"Осталось: {left}"
        )
        await prompt_custom_question(cb.message, state, user_id)
        return

    if parts[1] == "horo" and len(parts) == 3:
        kind = parts[2]
        if kind == "today":
            grant_chart_horo(chart["id"], "today", 1)
            await cb.message.answer(
                f"📅 Прогноз «Сегодня» для «{cname}»{TEST_NOTE}"
            )
            await deliver_today_horo(cb.message, user_id)
        elif kind == "week":
            grant_chart_horo(chart["id"], "week", 7)
            chart = get_chart(chart["id"], user_id)
            await cb.message.answer(
                f"📅 «Неделя» для «{cname}» — 7 дней{TEST_NOTE}"
            )
            await send_daily_horo(cb.bot, chart)
        elif kind == "month":
            grant_chart_horo(chart["id"], "month", 30)
            chart = get_chart(chart["id"], user_id)
            await cb.message.answer(
                f"📅 «Месяц» для «{cname}» — 30 дней{TEST_NOTE}"
            )
            await send_daily_horo(cb.bot, chart)
        await show_menu(cb.message, user_id)
        return


# ─── Гороскопы (меню) ─────────────────────────────────────────────────


@router.callback_query(F.data == "horo:deliver:today")
async def cb_horo_deliver_today(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    chart = get_active_chart(user_id)
    if not chart:
        await cb.answer("Сначала создай карту", show_alert=True)
        return
    if not has_horo_today(chart):
        await cb.answer("Сначала оплати прогноз на сегодня", show_alert=True)
        await send_paywall_horo(cb.message)
        return
    await cb.answer()
    await deliver_today_horo(cb.message, user_id)


# ─── Мои карты ────────────────────────────────────────────────────────


@router.message(StateFilter(None), F.text == BTN_MY_CHARTS)
async def m_my_charts(msg: Message) -> None:
    user_id = tid(msg)
    charts = list_charts(user_id)
    if not charts:
        await msg.answer(
            "У тебя пока нет карт.\nНажми ➕ Создать новую карту или /start"
        )
        return
    u = get_user(user_id)
    active_id = u.get("active_chart_id") if u else None
    await msg.answer(
        "📋 Твои натальные карты\n\n"
        "Нажми на карту, чтобы сделать её активной ✅",
        reply_markup=charts_list_kb(charts, active_id),
    )


@router.callback_query(F.data.startswith("chart:"))
async def cb_set_chart(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    try:
        chart_id = int(cb.data.split(":")[1])
    except (IndexError, ValueError):
        await cb.answer()
        return
    if not set_active_chart(user_id, chart_id):
        await cb.answer("Карта не найдена", show_alert=True)
        return
    chart = get_active_chart(user_id)
    await cb.answer(f"Активна: {chart['profile_name']}")
    prem = "\n💎 Premium активен" if chart.get("premium_unlocked") else ""
    await cb.message.answer(
        f"✅ Активная карта: *{chart['profile_name']}*{prem}\n"
        f"{chart['birth_date']} · {chart['birth_time']} · {chart['birth_place']}\n\n"
        "Гороскопы, вопросы и совместимость — для этой карты.",
        parse_mode="Markdown",
        reply_markup=menu_for(user_id),
    )


@router.message(StateFilter(None), F.text == BTN_NEW_CHART)
async def m_new_chart(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Onboarding.name)
    await msg.answer(WELCOME_NEW, reply_markup=KB_ONBOARD)


# ─── Меню ─────────────────────────────────────────────────────────────


@router.message(StateFilter(None), F.text == BTN_CHART)
async def m_chart(msg: Message) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Сначала создай или выбери карту в 📋 Все карты")
        return
    prem = " 💎" if chart.get("premium_unlocked") else ""
    await msg.answer(
        f"🌙 *{chart['profile_name']}* (активная){prem}",
        parse_mode="Markdown",
    )
    if chart.get("free_reading"):
        await msg.answer("🎁 Бесплатный разбор\n")
        await send_chunks(msg, chart["free_reading"])
    else:
        await msg.answer("Бесплатный разбор ещё не готов.")
    if can_full_chart(chart):
        await deliver_full_chart(msg, user_id)
    elif not has_premium(chart):
        await send_paywall_premium(msg)


@router.message(StateFilter(None), F.text == BTN_PREMIUM)
async def m_premium(msg: Message) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Сначала создай или выбери карту")
        return
    if has_premium(chart):
        await msg.answer(f"💎 Premium для «{chart['profile_name']}» уже активен ✨")
        if not chart.get("full_reading"):
            await deliver_full_chart(msg, user_id)
        return
    await send_paywall_premium(msg)


@router.message(StateFilter(None), F.text == BTN_SUPPORT)
async def m_support(msg: Message) -> None:
    await msg.answer(
        "💬 Поддержка Lunara\n\n"
        "Напиши сюда свой вопрос — поможем с доступом и оплатой."
    )


@router.message(StateFilter(None), F.text == BTN_COMPAT)
async def m_compat(msg: Message, state: FSMContext) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Выбери активную карту в 📋 Все карты")
        return
    if not can_compat(chart):
        await send_paywall_premium(msg)
        return
    await state.set_state(Partner.name)
    await msg.answer(
        f"❤️ Совместимость · {chart['profile_name']}\n\nИмя партнёра?"
    )


@router.message(StateFilter(None), F.text == BTN_QUESTIONS)
async def m_questions(msg: Message) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Выбери активную карту в 📋 Все карты")
        return
    if not can_popular(chart):
        await send_paywall_premium(msg)
        return
    await msg.answer(
        f"🔮 Популярные вопросы · {chart['profile_name']}:",
        reply_markup=KB_POPULAR,
    )


@router.message(StateFilter(None), F.text == BTN_ASK)
async def m_ask(msg: Message, state: FSMContext) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await msg.answer("Выбери активную карту в 📋 Все карты")
        return
    if not can_ask_custom(chart):
        await send_paywall_ask(msg)
        return
    await prompt_custom_question(msg, state, user_id)


@router.message(StateFilter(None), F.text == BTN_HORO)
async def m_horo(msg: Message) -> None:
    user_id = tid(msg)
    if not get_active_chart(user_id):
        await msg.answer("Сначала выбери активную карту в 📋 Все карты")
        return
    chart = get_active_chart(user_id)
    extra = f"Карта: {chart['profile_name']}"
    status = horo_status_line(chart)
    if status:
        extra += f"\n{status}"
    await send_paywall_horo(
        msg,
        extra=extra,
        show_today_btn=has_horo_today(chart),
    )


@router.callback_query(F.data.startswith("q:"))
async def cb_question(cb: CallbackQuery) -> None:
    user_id = cb.from_user.id
    chart = get_active_chart(user_id)
    if not chart:
        await cb.answer("Выбери активную карту", show_alert=True)
        return
    if not can_popular(chart):
        await cb.answer("Нужен Premium для этой карты", show_alert=True)
        return
    key = cb.data.split(":")[1]
    q = POPULAR.get(key)
    if not q:
        await cb.answer()
        return
    await cb.answer()
    await cb.message.answer(f"🔮 {q}")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(chart)}")
        await send_chunks(cb.message, text)
    except Exception as e:
        await cb.message.answer(f"Ошибка: {e}")


@router.message(Ask.waiting, F.text == BTN_CANCEL)
async def on_ask_cancel(msg: Message, state: FSMContext) -> None:
    await state.clear()
    chart = get_active_chart(tid(msg))
    left = question_balance(chart) if chart else 0
    note = f"\n\nНеиспользованных вопросов: {left}." if left else ""
    await msg.answer(f"Вопросы отложены.{note}", reply_markup=menu_for(tid(msg)))


@router.message(Ask.waiting, F.text)
async def on_ask_text(msg: Message, state: FSMContext) -> None:
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await state.clear()
        await msg.answer("Выбери активную карту в 📋 Все карты")
        return
    if not chart or not can_ask_custom(chart):
        await state.clear()
        await send_paywall_ask(msg)
        return
    q = msg.text.strip()
    if len(q) < 3:
        await msg.answer("Вопрос подлиннее 🙂")
        return

    await msg.answer("✍️ Ищу ответ…")
    try:
        text = await ask_ai(PROMPT_ANSWER, f"{q}\n\n{profile_text(chart)}")
        if not use_chart_question(chart["id"]):
            await state.clear()
            await send_paywall_ask(msg)
            return
        chart = get_chart(chart["id"], user_id)
        left = question_balance(chart)
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
    user_id = tid(msg)
    chart = get_active_chart(user_id)
    if not chart:
        await state.clear()
        await msg.answer("Нет активной карты")
        return
    await state.clear()
    await msg.answer("❤️ Считаю совместимость…")
    try:
        text = await ask_ai(
            PROMPT_COMPAT,
            f"Партнёр: {data['pname']}, {d}\n\n"
            f"Пользователь:\n{profile_text(chart)}",
        )
        await send_chunks(msg, text)
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    await show_menu(msg, tid(msg))


@router.message(StateFilter(None), F.text)
async def any_text(msg: Message) -> None:
    if msg.text.startswith("/"):
        return
    if is_profile_complete(tid(msg)):
        await msg.answer("Выбери кнопку в меню 👇", reply_markup=menu_for(tid(msg)))
    else:
        await msg.answer("Нажми /start чтобы начать ✨")
