# Lunara — Telegram-бот (aiogram + OpenAI)

Бот собирает данные рождения через FSM и запрашивает у OpenAI краткий астрологический разбор.

## Запуск

1. Создайте виртуальное окружение и установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Скопируйте `.env.example` в `.env` и укажите `BOT_TOKEN` и `OPENAI_API_KEY`.

3. Запуск:

```bash
python bot.py
```

## Команды

- `/start` — приветствие; кнопка «✨ Создать мою карту» — анкета (имя → дата → время → место)
- `/form` — начать анкету заново
- `/cancel` — сбросить анкету

## Структура

| Файл | Назначение |
|------|------------|
| `bot.py` | Точка входа, `Dispatcher`, polling |
| `config.py` | Переменные окружения |
| `states.py` | Группа состояний FSM |
| `handlers.py` | Обработчики и вызов OpenAI |
| `database.py` | SQLite: сохранение пользователей |
| `chart_generator.py` | Premium-карта (kerykeion + matplotlib → PNG в `charts/`) |
