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

ADMIN_IDS = {510559563}


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
