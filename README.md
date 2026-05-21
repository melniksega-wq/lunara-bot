# Lunara — Telegram-бот

## Flow

1. `/start` → onboarding (имя, дата, время, место)
2. PNG карта + бесплатный разбор
3. Paywall полной версии (249 ₽)
4. Меню free / premium

## Локально

```bash
pip install -r requirements.txt
cp .env.example .env   # BOT_TOKEN, OPENAI_API_KEY
python3 bot.py
```

## Railway

Variables: `BOT_TOKEN`, `OPENAI_API_KEY`

Start: `python bot.py`

**Только один экземпляр бота** (Railway ИЛИ локально).

## Доступ

**Free:** PNG карта + короткий разбор → paywall Premium (249 ₽)

**Premium (249 ₽):** полная карта · совместимость · 🔮 готовые вопросы

**✍️ Свои вопросы (отдельно):** 3 — 99 ₽ · 10 — 249 ₽

**📅 Гороскопы (отдельно):** Сегодня 29 ₽ · Неделя 99 ₽ (7 дней) · Месяц 199 ₽ (30 дней)

## Меню

**Free:** 🌙 Моя карта · 💎 Premium · ✍️ Задать вопрос · 📅 Гороскопы · 💬 Поддержка

**Premium:** 🌙 · ❤️ · 🔮 · ✍️ · 📅 · 💬
