"""
Premium-карта Lunara: 12 персональных разделов (психологический профиль).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from aiogram.types import Message

from database import get_active_chart, save_chart_texts
from services import ask_ai, profile_text

log = logging.getLogger(__name__)

PREMIUM_VERSION = 2
PREMIUM_SECTION_TIMEOUT = 180.0
SECTION_PAUSE_SEC = 0.6

PREMIUM_VOICE = """
Ты Lunara — аналитик личности. Пишешь как опытный психолог и коуч, НЕ как астролог.
Используй данные натальной карты как основу для глубокого портрета личности.
Обращайся на «вы». Тон: уверенный, глубокий, конкретный.

СТРОГО ЗАПРЕЩЕНО:
- «Звёзды говорят…», «Планеты подсказывают…», «Возможно…», «Скорее всего…»
- Общие фразы: «вы романтичный человек», «у вас хороший потенциал», «способны вдохновлять»
- Вода, эзотерические клише, универсальный гороскоп
- Астрологический жаргон без перевода на язык поведения

ОБЯЗАТЕЛЬНО в каждом разделе:
- конкретные наблюдения о поведении и мышлении
- внутренние конфликты и мотивации
- сильные и слабые стороны
- зоны риска
- практические рекомендации (2–4 пункта в конце раздела)

Пиши уверенно, от первого лица аналитика («У вас…», «Ваша…», «Вы склонны…»).
Раздел — цельный текст из абзацев, без заголовков внутри. Можно использовать • для списков рекомендаций.
""".strip()


@dataclass(frozen=True)
class PremiumSection:
    num: int
    title: str
    min_chars: int
    focus: str


PREMIUM_SECTIONS: tuple[PremiumSection, ...] = (
    PremiumSection(
        1,
        "КТО ВЫ НА САМОМ ДЕЛЕ",
        1200,
        "Внутренний характер; что вами движет; как вас воспринимают другие; "
        "чем вы отличаетесь от большинства.",
    ),
    PremiumSection(
        2,
        "ЧТО ВЫ СКРЫВАЕТЕ ОТ ОКРУЖАЮЩИХ",
        1200,
        "Эмоции, переживания, страхи — то, что обычно не показываете людям.",
    ),
    PremiumSection(
        3,
        "ЛЮБОВЬ И ОТНОШЕНИЯ",
        1200,
        "Как влюбляетесь; что ищете в партнёре; что даёте; что разрушает отношения.",
    ),
    PremiumSection(
        4,
        "ПОЧЕМУ МОГУТ НЕ СКЛАДЫВАТЬСЯ ОТНОШЕНИЯ",
        1200,
        "Повторяющиеся сценарии, ошибки, эмоциональные ловушки, внутренние страхи. "
        "Без общих фраз — только конкретика.",
    ),
    PremiumSection(
        5,
        "ДЕНЬГИ И ФИНАНСЫ",
        1200,
        "Отношение к деньгам; что мешает доходу; через что проще зарабатывать; финансовые риски.",
    ),
    PremiumSection(
        6,
        "КАРЬЕРА И РЕАЛИЗАЦИЯ",
        1200,
        "Сильные профессиональные стороны; подходящие направления; "
        "найм или предпринимательство; стиль работы.",
    ),
    PremiumSection(
        7,
        "ПРЕДНАЗНАЧЕНИЕ",
        1200,
        "Какие уроки проходите; чему важно научиться; что помогает расти. Без эзотерической воды.",
    ),
    PremiumSection(
        8,
        "СКРЫТЫЕ ТАЛАНТЫ",
        1000,
        "Способности, которые можете недооценивать; как их проявить.",
    ),
    PremiumSection(
        9,
        "ДЕТИ И РОДИТЕЛЬСТВО",
        1000,
        "Каким родителем можете быть; сильные стороны воспитания; на что обратить внимание.",
    ),
    PremiumSection(
        10,
        "ГЛАВНЫЕ ЖИЗНЕННЫЕ УРОКИ",
        1200,
        "Повторяющиеся жизненные ситуации; чему они учат; какие ошибки не повторять.",
    ),
    PremiumSection(
        11,
        "ЧТО МОЖЕТ УДИВИТЬ ВАС В СЕБЕ",
        1000,
        "Неожиданные, но точные наблюдения. Читатель должен подумать: «Это правда про меня».",
    ),
    PremiumSection(
        12,
        "ИТОГОВЫЙ ПОРТРЕТ",
        1200,
        "Краткое резюме всей карты: 3 сильные стороны, 3 зоны роста, один главный совет.",
    ),
)

PROGRESS_LINES = (
    ("🔮 Анализируем положение планет…", "██░░░░░░░░ 20%"),
    ("🌙 Изучаем эмоциональный профиль…", "█████░░░░░ 50%"),
    ("✨ Формируем персональный отчёт…", "██████████ 100%"),
)


def _section_system_prompt(section: PremiumSection) -> str:
    return (
        f"{PREMIUM_VOICE}\n\n"
        f"Сейчас пишешь ТОЛЬКО раздел {section.num} из 12: «{section.title}».\n"
        f"Минимум {section.min_chars} символов в этом разделе.\n"
        f"Фокус раздела: {section.focus}\n"
        "Не упоминай другие разделы и не делай вступление «в этой карте»."
    )


def _section_user_prompt(chart: dict, section: PremiumSection) -> str:
    return (
        f"Данные натальной карты:\n{profile_text(chart)}\n\n"
        f"Напиши раздел «{section.title}» как персональное психологическое досье."
    )


def _encode_premium(sections: list[dict]) -> str:
    return json.dumps(
        {"v": PREMIUM_VERSION, "sections": sections},
        ensure_ascii=False,
    )


def _decode_premium(raw: str | None) -> list[dict] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("v") == PREMIUM_VERSION:
            secs = data.get("sections")
            if isinstance(secs, list) and secs:
                return secs
    except json.JSONDecodeError:
        pass
    return None


async def play_premium_progress(msg: Message) -> None:
    for text, bar in PROGRESS_LINES:
        await msg.answer(f"{text}\n\n{bar}")
        await asyncio.sleep(1.4)


async def _generate_section(chart: dict, section: PremiumSection) -> str:
    text = await ask_ai(
        _section_system_prompt(section),
        _section_user_prompt(chart, section),
        timeout=PREMIUM_SECTION_TIMEOUT,
    )
    if len(text) < section.min_chars * 0.7:
        log.warning(
            "section %s short: %s chars (min %s)",
            section.num,
            len(text),
            section.min_chars,
        )
    return text


async def _send_section(msg: Message, section: PremiumSection, body: str) -> None:
    header = f"🔮 Раздел {section.num} из 12\n\n*{section.title}*"
    text = f"{header}\n\n{body}"
    for i in range(0, len(text), 4000):
        await msg.answer(text[i : i + 4000], parse_mode="Markdown")


async def _send_sections_from_cache(msg: Message, sections: list[dict]) -> None:
    by_num = {int(s["num"]): s for s in sections}
    for section in PREMIUM_SECTIONS:
        item = by_num.get(section.num)
        if not item:
            continue
        await _send_section(msg, section, item["body"])
        await asyncio.sleep(SECTION_PAUSE_SEC)


async def deliver_premium_chart(
    msg: Message,
    user_id: int,
    *,
    chart: dict | None = None,
) -> None:
    chart = chart or get_active_chart(user_id)
    if not chart:
        await msg.answer("Сначала выбери или создай карту в 📋 Все карты")
        return

    name = chart["profile_name"]
    cached = _decode_premium(chart.get("full_reading"))
    if cached:
        await msg.answer(
            f"💎 *Premium-карта · {name}*\n\n"
            "Твой персональный отчёт из 12 разделов:",
            parse_mode="Markdown",
        )
        await _send_sections_from_cache(msg, cached)
        return

    await msg.answer(
        f"💎 *Premium · {name}*\n\n"
        "Готовлю персональное психологическое досье — 12 разделов.\n"
        "Это займёт несколько минут.",
        parse_mode="Markdown",
    )
    await play_premium_progress(msg)

    sections_out: list[dict] = []
    try:
        for section in PREMIUM_SECTIONS:
            await msg.answer(f"📝 Формирую раздел {section.num} из 12…")
            body = await _generate_section(chart, section)
            sections_out.append(
                {"num": section.num, "title": section.title, "body": body}
            )
            await _send_section(msg, section, body)
            await asyncio.sleep(SECTION_PAUSE_SEC)

        save_chart_texts(chart["id"], full=_encode_premium(sections_out))
        await msg.answer(
            "✨ *Premium-карта готова.*\n\n"
            "Сохранена в профиле — можно перечитать в ✨ Текущая карта.",
            parse_mode="Markdown",
        )
    except Exception as e:
        log.exception("premium chart user=%s chart=%s", user_id, chart.get("id"))
        if sections_out:
            save_chart_texts(chart["id"], full=_encode_premium(sections_out))
            await msg.answer(
                "Часть разделов уже сохранена. Открой ✨ Текущая карта позже "
                "или напиши в поддержку."
            )
        await msg.answer(f"Ошибка при создании Premium: {e}")
