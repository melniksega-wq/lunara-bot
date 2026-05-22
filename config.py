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

# ЮKassa API (ЛК → Интеграция → shopId и секретный ключ)
YOOKASSA_SHOP_ID = env("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = env("YOOKASSA_SECRET_KEY")

# @username бота без @ — для return_url в Telegram
BOT_USERNAME = env("BOT_USERNAME").lstrip("@")

# Публичный URL Railway для webhook (https://xxx.up.railway.app)
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL").rstrip("/")

YOOKASSA_WEBHOOK_PATH = env("YOOKASSA_WEBHOOK_PATH") or "/yookassa/webhook"

# Код НДС в чеке (1 — без НДС)
YOOKASSA_VAT_CODE = int(env("YOOKASSA_VAT_CODE") or "1")
_tax = env("YOOKASSA_TAX_SYSTEM_CODE")
YOOKASSA_TAX_SYSTEM_CODE = int(_tax) if _tax.isdigit() else None

# 1 = отправлять receipt в запросе оплаты (нужна схема «Платёж и чек одновременно» в ЛК ЮKassa)
YOOKASSA_SEND_RECEIPT = env("YOOKASSA_SEND_RECEIPT").lower() in ("1", "true", "yes")

ADMIN_IDS = {510559563}


def payments_enabled() -> bool:
    return bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)


def yookassa_return_url(order_id: int) -> str:
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/payment/return?order={order_id}"
    if BOT_USERNAME:
        return f"https://t.me/{BOT_USERNAME}?start=paid_{order_id}"
    return "https://yookassa.ru/"


def yookassa_webhook_url() -> str:
    if not PUBLIC_BASE_URL:
        return ""
    path = YOOKASSA_WEBHOOK_PATH if YOOKASSA_WEBHOOK_PATH.startswith("/") else f"/{YOOKASSA_WEBHOOK_PATH}"
    return f"{PUBLIC_BASE_URL}{path}"


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
