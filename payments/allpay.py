"""Интеграция с платёжным шлюзом AllPay (Израиль).

Документация: https://www.allpay.co.il/en/api-reference

Подпись (sign) — точно по официальному алгоритму AllPay (PHP/JS getApiSignature):
ключи верхнего уровня сортируются по алфавиту; для массива ``items`` элементы берутся
по порядку, ключи каждого элемента сортируются; **в подпись попадают только непустые
СТРОКОВЫЕ значения** (числа — price/qty/vat — исключаются!); значения соединяются
через ``:``, в конец добавляется ``:API_KEY``, всё хэшируется SHA256.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

import aiohttp

API_URL = "https://allpay.to/app/?show=getpayment&mode=api11"


def _collect_chunks(params: dict[str, Any]) -> list[str]:
    """Собирает значения для подписи по алгоритму AllPay (только строки)."""
    chunks: list[str] = []
    for key in sorted(params.keys()):
        if key == "sign":
            continue
        value = params[key]
        if isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, dict):
                    for name in sorted(item.keys()):
                        val = item[name]
                        if isinstance(val, str) and val.strip() != "":
                            chunks.append(val)
        elif isinstance(value, str) and value.strip() != "":
            chunks.append(value)
        # нестроковые скаляры (числа, bool, None) в подпись не входят — как в AllPay
    return chunks


def build_sign(payload: dict[str, Any], api_key: str) -> str:
    """Считает SHA256-подпись по правилам AllPay."""
    raw = ":".join(_collect_chunks(payload)) + ":" + api_key
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
        # AllPay считает подпись от строковых значений — price/qty/vat ОБЯЗАТЕЛЬНО
        # передавать строками, иначе JSON пошлёт число и подпись не сойдётся.
        "items": [
            {"name": item_name, "price": f"{amount_major:.2f}", "qty": "1", "vat": "0"},
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
