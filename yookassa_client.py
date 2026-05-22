"""Клиент REST API ЮKassa v3."""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any

import httpx

from config import (
    YOOKASSA_SECRET_KEY,
    YOOKASSA_SEND_RECEIPT,
    YOOKASSA_SHOP_ID,
    YOOKASSA_TAX_SYSTEM_CODE,
    YOOKASSA_VAT_CODE,
    yookassa_return_url,
)

log = logging.getLogger(__name__)

API_URL = "https://api.yookassa.ru/v3/payments"


class YooKassaAPIError(Exception):
    def __init__(self, status: int, message: str, *, parameter: str = ""):
        self.status = status
        self.parameter = parameter
        super().__init__(message)


def _auth_header() -> str:
    raw = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _headers() -> dict[str, str]:
    return {
        "Authorization": _auth_header(),
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def parse_api_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        return resp.text or f"HTTP {resp.status_code}"
    desc = data.get("description") or data.get("message") or resp.text
    param = data.get("parameter", "")
    code = data.get("code", "")
    parts = [p for p in (desc, f"код: {code}" if code else "", f"поле: {param}" if param else "") if p]
    return ". ".join(parts)


def build_receipt(
    product_title: str,
    amount_rub_str: str,
    *,
    customer_email: str | None = None,
    customer_phone: str | None = None,
) -> dict[str, Any]:
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
        ],
    }
    customer: dict[str, str] = {}
    if customer_email:
        customer["email"] = customer_email
    if customer_phone:
        customer["phone"] = customer_phone
    if customer:
        receipt["customer"] = customer
    if YOOKASSA_TAX_SYSTEM_CODE is not None:
        receipt["tax_system_code"] = YOOKASSA_TAX_SYSTEM_CODE
    return receipt


def _payment_body(
    *,
    amount_rub_str: str,
    description: str,
    product_title: str,
    order_id: int,
    user_id: int,
    chart_id: int,
    product_key: str,
    with_receipt: bool,
    customer_email: str | None = None,
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
    }
    if with_receipt:
        # Для чека нужен email или телефон покупателя (54-ФЗ)
        email = customer_email or f"user{user_id}@telegram.lunara.local"
        body["receipt"] = build_receipt(
            product_title,
            amount_rub_str,
            customer_email=email,
        )
    return body


async def _post_payment(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(API_URL, json=body, headers=_headers())
    if resp.status_code >= 400:
        msg = parse_api_error(resp)
        log.error("yookassa create %s: %s", resp.status_code, resp.text)
        try:
            data = resp.json()
            param = data.get("parameter", "")
        except Exception:
            param = ""
        raise YooKassaAPIError(resp.status_code, msg, parameter=param)
    return resp.json()


async def create_payment(
    *,
    amount_rub_str: str,
    description: str,
    product_title: str,
    order_id: int,
    user_id: int,
    chart_id: int,
    product_key: str,
    customer_email: str | None = None,
) -> dict[str, Any]:
    """
    Создаёт платёж. По умолчанию без receipt (подходит для схемы «Чеки отдельно» в ЛК).
    При YOOKASSA_SEND_RECEIPT=1 — с чеком (нужна схема «Платёж и чек одновременно»).
    """
    if YOOKASSA_SEND_RECEIPT:
        return await _post_payment(
            _payment_body(
                amount_rub_str=amount_rub_str,
                description=description,
                product_title=product_title,
                order_id=order_id,
                user_id=user_id,
                chart_id=chart_id,
                product_key=product_key,
                with_receipt=True,
                customer_email=customer_email,
            )
        )

    body = _payment_body(
        amount_rub_str=amount_rub_str,
        description=description,
        product_title=product_title,
        order_id=order_id,
        user_id=user_id,
        chart_id=chart_id,
        product_key=product_key,
        with_receipt=False,
    )
    try:
        return await _post_payment(body)
    except YooKassaAPIError as e:
        # Чек не нужен / запрещён — повтор без receipt
        if "receipt" in (e.parameter or "").lower() or "receipt" in str(e).lower():
            log.info("retry payment without receipt")
            return await _post_payment(
                _payment_body(
                    amount_rub_str=amount_rub_str,
                    description=description,
                    product_title=product_title,
                    order_id=order_id,
                    user_id=user_id,
                    chart_id=chart_id,
                    product_key=product_key,
                    with_receipt=False,
                )
            )
        raise


async def get_payment(payment_id: str) -> dict[str, Any]:
    url = f"{API_URL}/{payment_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_headers())
    if resp.status_code >= 400:
        raise YooKassaAPIError(resp.status_code, parse_api_error(resp))
    return resp.json()
