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

## Меню

**Free:** 🌙 Моя карта · 💎 Premium · 💬 Поддержка

**Premium:** + ❤️ Совместимость · 🔮 Вопросы · ✍️ Задать вопрос · 📅 Гороскопы
