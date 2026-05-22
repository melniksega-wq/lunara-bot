"""Клиент REST API ЮKassa v3."""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

import httpx

from config import (
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SHOP_ID,
    YOOKASSA_TAX_SYSTEM_CODE,
    YOOKASSA_VAT_CODE,
    yookassa_return_url,
)

log = logging.getLogger(__name__)

API_URL = "https://api.yookassa.ru/v3/payments"


def _auth_header() -> str:
    raw = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _headers() -> dict[str, str]:
    return {
        "Authorization": _auth_header(),
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def build_receipt(product_title: str, amount_rub_str: str) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "items": [
            {
                "description": product_title[:128],
                "quantity": "1.00",
                "amount": {"value": amount_rub_str, "currency": "RUB"},
                "vat_code": int(YOOKASSA_VAT_CODE),
                "payment_mode": "full_payment",
                "payment_subject": "service",
            }
        ]
    }
    if YOOKASSA_TAX_SYSTEM_CODE is not None:
        receipt["tax_system_code"] = YOOKASSA_TAX_SYSTEM_CODE
    return receipt


async def create_payment(
    *,
    amount_rub_str: str,
    description: str,
    product_title: str,
    order_id: int,
    user_id: int,
    chart_id: int,
    product_key: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "amount": {"value": amount_rub_str, "currency": "RUB"},
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": yookassa_return_url(order_id),
        },
        "description": description[:128],
        "metadata": {
            "order_id": str(order_id),
            "user_id": str(user_id),
            "chart_id": str(chart_id),
            "product_key": product_key,
        },
        "receipt": build_receipt(product_title, amount_rub_str),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(API_URL, json=body, headers=_headers())
    if resp.status_code >= 400:
        log.error("yookassa create %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()


async def get_payment(payment_id: str) -> dict[str, Any]:
    url = f"{API_URL}/{payment_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_headers())
    if resp.status_code >= 400:
        log.error("yookassa get %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    return resp.json()
