import os
import sys

print("Lunara bot boot", flush=True)
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OPENAI_API_KEY
from database import init_db
from handlers import router


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_health():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), Health).serve_forever()


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not BOT_TOKEN or not OPENAI_API_KEY:
        logging.error("Задай BOT_TOKEN и OPENAI_API_KEY в Railway Variables")
        sys.exit(1)
    logging.info("Keys OK. Polling…")
    init_db()
    threading.Thread(target=run_health, daemon=True).start()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
