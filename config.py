import os
from pathlib import Path

from dotenv import load_dotenv

_env = Path(__file__).resolve().parent / ".env"
if _env.is_file():
    load_dotenv(_env, override=False)


def env(name: str) -> str:
    return os.getenv(name, "").strip().strip("\r")


BOT_TOKEN = env("BOT_TOKEN")
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL") or "gpt-4o-mini"

# Платёжный токен из @BotFather после подключения бота к ЮKassa (Telegram Payments)
YOOKASSA_PROVIDER_TOKEN = env("YOOKASSA_PROVIDER_TOKEN") or env(
    "TELEGRAM_PROVIDER_TOKEN"
)

# Код НДС для чека (1 — без НДС; см. справочник ЮKassa)
YOOKASSA_VAT_CODE = int(env("YOOKASSA_VAT_CODE") or "1")

ADMIN_IDS = {510559563}


def payments_enabled() -> bool:
    return bool(YOOKASSA_PROVIDER_TOKEN)


def admin_ids() -> set[int]:
    ids = set(ADMIN_IDS)
    raw = env("ADMIN_IDS")
    if not raw:
        return ids
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids
