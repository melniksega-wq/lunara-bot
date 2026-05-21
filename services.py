import asyncio
import re

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

AI_TIMEOUT_SEC = 90

DATE_RE = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\s*$")
TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")

STYLE = (
    "Ты Lunara — премиальный астрологический AI. "
    "Пиши эмоционально, современно, без сложных терминов. "
    "Читатель должен чувствовать: «это про меня». Коротко и атмосферно."
)

PROMPT_FREE = (
    STYLE
    + "\n\nОчень короткий бесплатный разбор. Не больше 350 символов на весь ответ.\n"
    "Ровно 4 микро-блока (по 1 короткому предложению):\n"
    "✨ Кто человек\n💕 Любовь — один факт\n💰 Деньги — один факт\n⚡ Главная черта"
)

PROMPT_HORO_DAILY = (
    STYLE
    + "\n\nЕжедневный гороскоп на сегодня. 2–3 коротких абзаца с эмодзи. "
    "Без общих фраз — конкретно под человека."
)

PROMPT_HORO_TODAY = (
    STYLE
    + "\n\nГороскоп на сегодня. 2–3 коротких абзаца с эмодзи."
)

PROMPT_FULL = (
    STYLE
    + "\n\nПолная карта. 5 блоков:\n"
    "💕 Отношения\n🌟 Предназначение\n💰 Деньги\n🔮 Жизненные сценарии\n✨ Скрытые таланты"
)

PROMPT_ANSWER = STYLE + "\n\nОтветь на вопрос по данным рождения. 2–3 абзаца, с эмодзи."

PROMPT_COMPAT = STYLE + "\n\nРазбор совместимости пары. 5 коротких блоков с эмодзи."

HORO_LABELS = {"today": "Сегодня", "week": "Неделя", "month": "Месяц"}


def parse_date(text: str) -> str | None:
    m = DATE_RE.match(text.strip())
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
    return f"{d:02d}.{mo:02d}.{y}"


def parse_time(text: str) -> str | None:
    if text.strip().lower() in ("не знаю", "неизвестно"):
        return "неизвестно"
    m = TIME_RE.match(text.strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return f"{h:02d}:{mi:02d}"
    return None


def profile_text(chart: dict) -> str:
    name = chart.get("profile_name") or chart.get("name", "")
    return (
        f"Имя: {name}\n"
        f"Дата: {chart['birth_date']}\n"
        f"Время: {chart['birth_time']}\n"
        f"Место: {chart['birth_place']}"
    )


async def ask_ai(system: str, user_msg: str, *, timeout: float = AI_TIMEOUT_SEC) -> str:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def _call() -> str:
        r = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
        )
        return (r.choices[0].message.content or "").strip()

    return await asyncio.wait_for(_call(), timeout=timeout)
