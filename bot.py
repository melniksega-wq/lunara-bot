import os
import sys

print("Lunara bot boot", flush=True)
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN,
    OPENAI_API_KEY,
    admin_ids,
    payments_enabled,
    yookassa_webhook_url,
)
from database import init_db
from admin import router as admin_router
from handlers import router
from payments import router as payments_router
from horo_scheduler import horo_scheduler_loop
from webapp import create_web_app


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not BOT_TOKEN or not OPENAI_API_KEY:
        logging.error("Задай BOT_TOKEN и OPENAI_API_KEY в Railway Variables")
        sys.exit(1)
    logging.info("Keys OK. Admin IDs: %s", admin_ids())
    mode = "ЮKassa API" if payments_enabled() else "test stubs"
    logging.info("Payments: %s", mode)
    wh = yookassa_webhook_url()
    if payments_enabled() and wh:
        logging.info("Webhook URL (укажи в ЛК ЮKassa): %s", wh)
    elif payments_enabled():
        logging.warning("Задай PUBLIC_BASE_URL для webhook ЮKassa")

    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    bot._lunara_dp = dp  # noqa: SLF001 — для проверки оплаты из callback

    dp.include_router(admin_router)
    dp.include_router(payments_router)
    dp.include_router(router)

    port = int(os.getenv("PORT", "8080"))
    app = create_web_app(bot, dp)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("HTTP on 0.0.0.0:%s (health + webhook)", port)

    asyncio.create_task(horo_scheduler_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
