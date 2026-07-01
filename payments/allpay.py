"""Интеграция с платёжным шлюзом AllPay (Израиль).

Документация: https://www.allpay.co.il/en/api-reference

Подпись (sign): из payload убираются поле ``sign`` и пустые значения, оставшиеся
ключи (включая вложенные элементы ``items``) сортируются по алфавиту, их значения
соединяются через ``:``, в конец добавляется API-ключ, всё хэшируется SHA256.

ВАЖНО: точный порядок «выравнивания» вложенных ``items`` стоит сверить с официальным
PHP-примером AllPay из личного кабинета — здесь используется представление с
dotted-ключами (``items.0.name`` и т.п.), которое затем сортируется по ключу.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import aiohttp

API_URL = "https://allpay.to/app/?show=getpayment&mode=api11"


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Разворачивает вложенный dict/list в плоский словарь с dotted-ключами."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{full}."))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    flat.update(_flatten(item, f"{full}.{i}."))
                else:
                    flat[f"{full}.{i}"] = str(item)
        else:
            flat[full] = str(value)
    return flat


def build_sign(payload: dict[str, Any], api_key: str) -> str:
    """Считает SHA256-подпись по правилам AllPay."""
    flat = _flatten(payload)
    flat.pop("sign", None)
    # Убираем пустые значения
    flat = {k: v for k, v in flat.items() if v != "" and v is not None}
    values = [flat[k] for k in sorted(flat.keys())]
    values.append(api_key)
    raw = ":".join(values)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_webhook_sign(data: dict[str, Any], api_key: str) -> bool:
    """Проверяет подпись входящего webhook."""
    received = str(data.get("sign", ""))
    if not received:
        return False
    expected = build_sign(data, api_key)
    return hmac.compare_digest(received.lower(), expected.lower())


def _extract_payment_url(response: dict[str, Any]) -> str | None:
    """Достаёт URL оплаты из ответа AllPay (поле называется по-разному)."""
    for key in ("payment_url", "url", "redirect_url", "link"):
        if response.get(key):
            return str(response[key])
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("payment_url", "url", "redirect_url", "link"):
            if data.get(key):
                return str(data[key])
    return None


async def create_payment(
    *,
    login: str,
    api_key: str,
    order_id: str,
    amount_major: float,
    currency: str,
    item_name: str,
    client_email: str,
    webhook_url: str,
    success_url: str,
) -> str:
    """Создаёт платёж в AllPay и возвращает URL страницы оплаты.

    Бросает RuntimeError, если ответ не содержит ссылки на оплату.
    """
    payload: dict[str, Any] = {
        "login": login,
        "order_id": order_id,
        "currency": currency,
        "client_email": client_email,
        "webhook_url": webhook_url,
        "success_url": success_url,
        "items": [
            {"name": item_name, "price": amount_major, "qty": 1, "vat": 0},
        ],
    }
    payload["sign"] = build_sign(payload, api_key)

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            body = await resp.json(content_type=None)

    url = _extract_payment_url(body)
    if not url:
        raise RuntimeError(f"AllPay не вернул ссылку на оплату: {body}")
    return url
