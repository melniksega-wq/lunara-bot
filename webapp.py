"""HTTP: healthcheck Railway и webhook ЮKassa."""

from __future__ import annotations

import json
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher

from config import BOT_USERNAME, PUBLIC_BASE_URL, YOOKASSA_WEBHOOK_PATH
from payments import process_payment_object

log = logging.getLogger(__name__)


async def health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def payment_return(request: web.Request) -> web.Response:
    """return_url после оплаты — редирект в Telegram."""
    order = request.query.get("order", "")
    if BOT_USERNAME and order.isdigit():
        raise web.HTTPFound(location=f"https://t.me/{BOT_USERNAME}?start=paid_{order}")
    return web.Response(
        text="Оплата завершена. Вернитесь в Telegram-бот Lunara.",
        content_type="text/html; charset=utf-8",
    )


async def yookassa_webhook(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    dp: Dispatcher = request.app["dp"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.Response(status=400, text="bad json")

    event = body.get("event", "")
    obj = body.get("object") or {}
    log.info("yookassa webhook event=%s id=%s", event, obj.get("id"))

    if event in ("payment.succeeded", "payment.waiting_for_capture"):
        status = obj.get("status", "")
        if status in ("succeeded", "waiting_for_capture"):
            await process_payment_object(bot, dp, obj)

    return web.Response(text="ok")


def create_web_app(bot: Bot, dp: Dispatcher) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app.router.add_get("/", health)
    app.router.add_get("/payment/return", payment_return)
    if PUBLIC_BASE_URL:
        log.info("Return URL base: %s/payment/return", PUBLIC_BASE_URL)
    path = (
        YOOKASSA_WEBHOOK_PATH
        if YOOKASSA_WEBHOOK_PATH.startswith("/")
        else f"/{YOOKASSA_WEBHOOK_PATH}"
    )
    app.router.add_post(path, yookassa_webhook)
    log.info("Webhook ЮKassa: POST %s", path)
    return app
