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

from config import BOT_TOKEN, OPENAI_API_KEY, admin_ids
from database import init_db
from admin import router as admin_router
from handlers import router
from payments import payments_enabled, router as payments_router
from horo_scheduler import horo_scheduler_loop


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_health() -> None:
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), Health)
    logging.info("Healthcheck HTTP on 0.0.0.0:%s", port)
    server.serve_forever()


def start_health_server() -> None:
    thread = threading.Thread(target=run_health, daemon=True, name="health")
    thread.start()


async def main() -> None:
    if not BOT_TOKEN or not OPENAI_API_KEY:
        logging.error("Задай BOT_TOKEN и OPENAI_API_KEY в Railway Variables")
        sys.exit(1)
    logging.info("Keys OK. Admin IDs: %s", admin_ids())
    logging.info("Payments (ЮKassa): %s", "on" if payments_enabled() else "off (test stubs)")
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    dp.include_router(payments_router)
    dp.include_router(router)
    asyncio.create_task(horo_scheduler_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    start_health_server()
    asyncio.run(main())
