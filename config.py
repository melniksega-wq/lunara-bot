import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parent / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=False)


def _get(name: str) -> str:
    return os.getenv(name, "").strip().strip("\r")


# Без падения при импорте — проверка в bot.py при старте
BOT_TOKEN = _get("BOT_TOKEN")
OPENAI_API_KEY = _get("OPENAI_API_KEY")
OPENAI_MODEL = _get("OPENAI_MODEL") or "gpt-4o-mini"
