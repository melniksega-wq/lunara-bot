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
    + "\n\nБесплатный разбор. Ровно 4 блока:\n"
    "✨ Кто человек\n💕 Любовь (коротко)\n💰 Деньги (коротко)\n⚡ Главная черта личности"
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


def profile_text(user: dict) -> str:
    return (
        f"Имя: {user['name']}\n"
        f"Дата: {user['birth_date']}\n"
        f"Время: {user['birth_time']}\n"
        f"Место: {user['birth_place']}"
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
