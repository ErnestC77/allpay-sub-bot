"""aiohttp-обработчики для AllPay: webhook подтверждения оплаты и success-страница."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

from config import Config
from db import crud
from i18n import normalize_lang, t
from payments.allpay import verify_webhook_sign
from utils import format_dt

logger = logging.getLogger(__name__)


async def _read_payload(request: web.Request) -> dict:
    """AllPay может слать JSON или form-urlencoded — принимаем оба варианта."""
    if request.content_type and "application/json" in request.content_type:
        try:
            return await request.json()
        except Exception:  # noqa: BLE001
            return {}
    data = await request.post()
    return {k: v for k, v in data.items()}


def make_webhook_handler(bot: Bot, config: Config):
    async def handler(request: web.Request) -> web.Response:
        data = await _read_payload(request)
        order_id = str(data.get("order_id", ""))

        # Webhook подписывается отдельным webhook-секретом; если он не задан —
        # пробуем API-ключ как запасной вариант.
        secret = config.allpay_webhook_secret or config.allpay_key
        if not verify_webhook_sign(data, secret):
            # Безопасная диагностика: только имена полей, префикс полученной подписи
            # и признак совпадения с API-ключом. Без значений/PII, без секретов и
            # без вычисленных подписей.
            logger.warning(
                "AllPay webhook: неверная подпись, order_id=%s; field_types=%s; "
                "sign_prefix=%s; match_apikey=%s; match_login=%s; webhook_secret_set=%s",
                order_id,
                {k: type(v).__name__ for k, v in data.items() if k != "sign"},
                str(data.get("sign", ""))[:8],
                verify_webhook_sign(data, config.allpay_key),
                verify_webhook_sign(data, config.allpay_login),
                bool(config.allpay_webhook_secret),
            )
            # 200, чтобы AllPay не ретраил бесконечно на «чужих» запросах
            return web.Response(text="bad sign", status=200)

        status = str(data.get("status", ""))
        if status != "1":
            logger.info("AllPay webhook: статус %s (не оплачено), order_id=%s", status, order_id)
            return web.Response(text="ok", status=200)

        allpay_ref = str(data.get("transaction_id") or data.get("id") or "") or None
        subscription = await crud.mark_paid_and_activate(order_id, allpay_ref)

        if subscription is None:
            # Уже обработан ранее или платёж неизвестен — подтверждаем приём.
            logger.info("AllPay webhook: повтор/неизвестный платёж, order_id=%s", order_id)
            return web.Response(text="ok", status=200)

        # Уведомляем пользователя об активации подписки.
        try:
            user = await crud.get_or_create_user(subscription.user_id)
            lang = normalize_lang(user.language)
            await bot.send_message(
                subscription.user_id,
                t("payment_success_notify", lang,
                  date=format_dt(subscription.end_at, user.timezone)),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось уведомить пользователя об оплате, order_id=%s", order_id)

        # Выдаём одноразовую ссылку в закрытый канал.
        await _send_channel_invite(bot, config, subscription.user_id)

        return web.Response(text="ok", status=200)

    return handler


async def _send_channel_invite(bot: Bot, config: Config, user_id: int) -> None:
    """Создаёт одноразовую ссылку в закрытый канал и присылает её пользователю."""
    chat_id = config.channel_chat_id
    if not chat_id:
        return
    try:
        user = await crud.get_or_create_user(user_id)
        lang = normalize_lang(user.language)
        link = await bot.create_chat_invite_link(
            chat_id, member_limit=1, name=f"sub-{user_id}"[:32],
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("channel_join_button", lang), url=link.invite_link)]])
        await bot.send_message(user_id, t("channel_access", lang), reply_markup=kb)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось выдать ссылку в канал user=%s", user_id)


async def _success_page(request: web.Request) -> web.Response:
    return web.Response(
        text="Оплата обрабатывается. Можно вернуться в Telegram ✅",
        content_type="text/plain",
    )


def setup_routes(app: web.Application, bot: Bot, config: Config) -> None:
    app.router.add_post(config.allpay_webhook_path, make_webhook_handler(bot, config))
    app.router.add_get("/allpay/success", _success_page)
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
