# Lunara — Telegram-бот (aiogram + OpenAI)

Бот собирает данные рождения, строит premium натальную карту и даёт астрологический разбор через OpenAI.

## Локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # заполните BOT_TOKEN и OPENAI_API_KEY
python3 bot.py
```

## Деплой на Railway

1. Подключите репозиторий GitHub `lunara-bot` к Railway.
2. **Variables** (обязательно):

| Переменная | Описание |
|------------|----------|
| `BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `OPENAI_API_KEY` | Ключ [OpenAI API](https://platform.openai.com/api-keys) |
| `OPENAI_MODEL` | Необязательно, по умолчанию `gpt-4o-mini` |

3. **Start Command:** `python3 bot.py` (уже в `railway.toml`).
4. Обязательны **оба** ключа: `BOT_TOKEN` и `OPENAI_API_KEY` (имена точно так).
5. После деплоя в логах: `Health server on port …` → `Starting Telegram polling…` → `Run polling for bot @…`.
6. Не запускайте бота одновременно локально и на Railway — будет конфликт polling.

Если падает: откройте **Deployments → View logs** и проверьте строку с `RuntimeError` или `Missing env`.

Файл `.env` в git не попадает — секреты только в Railway Variables.

## Команды бота

- `/start` — приветствие; кнопка «✨ Создать мою карту» — анкета
- `/form` — начать анкету заново
- `/cancel` — сбросить анкету

## Структура

| Файл | Назначение |
|------|------------|
| `bot.py` | Точка входа, healthcheck, polling |
| `config.py` | Переменные окружения |
| `handlers.py` | Обработчики и OpenAI |
| `chart_generator.py` | Натальная карта (kerykeion + matplotlib) |
| `database.py` | SQLite пользователей |
| `railway.toml` | Настройки деплоя Railway |
