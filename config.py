import os
from pathlib import Path

from dotenv import load_dotenv

# Локально читаем .env; на Railway переменные задаются в Variables (не перезаписываем их)
_ENV_FILE = Path(__file__).resolve().parent / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE, override=False)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip().strip("\r")
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Локально: файл .env. Railway: Project → Service → Variables."
        )
    return value


BOT_TOKEN = _require("BOT_TOKEN")
OPENAI_API_KEY = _require("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
