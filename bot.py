import os

# До тяжёлых импортов: matplotlib и Railway
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import asyncio
import logging
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import router


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        pass


def _start_health_server() -> None:
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info("Health server on port %s", port)


def _check_env() -> None:
    missing = [
        name
        for name in ("BOT_TOKEN", "OPENAI_API_KEY")
        if not os.getenv(name, "").strip()
    ]
    if missing:
        logging.error(
            "Не заданы переменные: %s. Railway → Service → Variables.",
            ", ".join(missing),
        )
        sys.exit(1)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _check_env()
    init_db()
    _start_health_server()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logging.info("Starting Telegram polling…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logging.exception("Bot crashed")
        raise
