"""aiohttp-обработчики для AllPay: webhook подтверждения оплаты и success-страница."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

from config import Config
from db import crud
from i18n import normalize_lang, t
from payments.allpay import get_token, verify_webhook_sign
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

        # Запоминаем тариф и сохраняем токен карты для автопродления.
        if subscription.plan_id:
            await crud.set_last_plan(subscription.user_id, subscription.plan_id)
        try:
            if config.allpay_login and config.allpay_key:
                token, mask = await get_token(
                    login=config.allpay_login, api_key=config.allpay_key, order_id=order_id)
                if token:
                    await crud.save_card_token(
                        subscription.user_id, token, mask, subscription.plan_id)
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось получить токен карты, order_id=%s", order_id)

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


def _success_html(bot_username: str) -> str:
    back = f"https://t.me/{bot_username}" if bot_username else "https://t.me"
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Оплата</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;text-align:center;
padding:48px 20px;color:#222}}a{{display:inline-block;margin-top:20px;padding:12px 20px;
background:#2ea6ff;color:#fff;border-radius:10px;text-decoration:none}}</style></head>
<body>
<h2>✅ Оплата обрабатывается</h2>
<p>Подписка активируется автоматически. Возвращаем вас в бота…</p>
<a href="{back}">Вернуться в бота</a>
<script>
  try {{
    if (window.Telegram && Telegram.WebApp) {{
      Telegram.WebApp.ready();
      setTimeout(function(){{ try {{ Telegram.WebApp.close(); }} catch(e){{}} }}, 1800);
    }}
  }} catch (e) {{}}
</script>
</body></html>"""


def make_success_handler(bot_username: str):
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text=_success_html(bot_username), content_type="text/html")
    return handler


def setup_routes(app: web.Application, bot: Bot, config: Config,
                 bot_username: str = "") -> None:
    app.router.add_post(config.allpay_webhook_path, make_webhook_handler(bot, config))
    app.router.add_get("/allpay/success", make_success_handler(bot_username))
    app.router.add_get("/health", lambda r: web.Response(text="ok"))
