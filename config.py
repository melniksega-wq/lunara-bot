import os
from pathlib import Path

from dotenv import load_dotenv

# Явный путь + override: иначе в IDE/терминале может остаться your_openai_api_key из окружения
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE, override=True)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip().strip("\r")
    if not value:
        raise RuntimeError(f"Не задана переменная окружения {name}")
    return value


BOT_TOKEN = _require("BOT_TOKEN")
OPENAI_API_KEY = _require("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
