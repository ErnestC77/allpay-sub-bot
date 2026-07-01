"""Фоновая задача: уведомления об окончании подписки.

Периодически проверяет активные подписки против настроенных порогов (ReminderRule)
и отправляет уведомление, когда до конца остаётся не больше N дней. Каждый порог
отправляется один раз на подписку (дедупликация через ReminderLog), поэтому частые
проверки безопасны и устойчивы к перезапускам процесса.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from aiogram import Bot

from config import Config
from db import crud
from i18n import normalize_lang, t
from keyboards.inline import subscription_kb
from payments.allpay import charge_token
from utils import format_dt

logger = logging.getLogger("scheduler")


def _render(text: str, days: int, date: str) -> str:
    """Подставляет {days}/{date} в пользовательский текст порога (безопасно)."""
    try:
        return text.format(days=days, date=date)
    except (KeyError, IndexError, ValueError):
        return text


async def process_due_reminders(bot: Bot) -> int:
    """Один проход: рассылает все назревшие уведомления. Возвращает число отправленных."""
    sent = 0
    for sub, rule in await crud.due_reminders():
        # Сначала «занимаем» отправку (защита от дублей), затем шлём.
        if not await crud.log_reminder(sub.id, rule.days_before):
            continue
        try:
            user = await crud.get_or_create_user(sub.user_id)
            lang = normalize_lang(user.language)
            text = _render(rule.text, rule.days_before, format_dt(sub.end_at, user.timezone))
            await bot.send_message(sub.user_id, text,
                                   reply_markup=subscription_kb(lang, has_sub=True))
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось отправить напоминание user=%s rule=%sд",
                             sub.user_id, rule.days_before)
    if sent:
        logger.info("Отправлено напоминаний: %s", sent)
    return sent


async def _try_auto_renew(bot: Bot, config: Config, user, sub) -> bool:
    """Пытается автосписать по токену и продлить. True — успешно продлено."""
    if not (user.auto_renew and user.allpay_token and user.last_plan_id):
        return False
    plan = await crud.get_plan(user.last_plan_id)
    if plan is None or not plan.is_active:
        return False

    order_id = f"{user.tg_id}-auto-{uuid4().hex[:10]}"
    await crud.create_payment(user.tg_id, plan, order_id)
    try:
        ok = await charge_token(
            login=config.allpay_login, api_key=config.allpay_key,
            order_id=order_id, amount_major=plan.price_major,
            currency=plan.currency, item_name=plan.title(normalize_lang(user.language)),
            allpay_token=user.allpay_token,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Автосписание: ошибка запроса, user=%s", user.tg_id)
        ok = False
    if not ok:
        return False

    newsub = await crud.mark_paid_and_activate(order_id, None)
    if newsub is None:
        return False
    lang = normalize_lang(user.language)
    try:
        await bot.send_message(
            user.tg_id,
            t("auto_renew_ok", lang, date=format_dt(newsub.end_at, user.timezone)),
        )
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось уведомить об автопродлении, user=%s", user.tg_id)
    return True


async def process_expired(bot: Bot, config: Config) -> int:
    """Обрабатывает истёкшие подписки: автопродление или снятие доступа."""
    channel_id = config.channel_chat_id
    removed = 0
    for sub in await crud.get_due_subscriptions():
        user = await crud.get_or_create_user(sub.user_id)
        renewed = await _try_auto_renew(bot, config, user, sub)
        # Старую истёкшую подписку в любом случае закрываем.
        await crud.set_subscription_status(sub.id, "expired")
        if renewed:
            continue  # доступ сохраняется, новая подписка активна

        # Не продлили → уведомляем и, если активных подписок не осталось, снимаем доступ.
        lang = normalize_lang(user.language)
        if await crud.has_active_subscription(user.tg_id):
            continue
        try:
            await bot.send_message(user.tg_id, t("subscription_expired", lang),
                                   reply_markup=subscription_kb(lang, has_sub=False))
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось уведомить об окончании подписки user=%s", user.tg_id)
        if channel_id:
            try:
                await bot.ban_chat_member(channel_id, user.tg_id)
                await bot.unban_chat_member(channel_id, user.tg_id, only_if_banned=True)
                removed += 1
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось удалить из канала user=%s", user.tg_id)
    if removed:
        logger.info("Снят доступ по окончании подписки: %s", removed)
    return removed


async def reminder_worker(bot: Bot, config: Config) -> None:
    """Бесконечный цикл: напоминания + автопродление/снятие доступа."""
    logger.info("Планировщик запущен (интервал %s c, канал=%s)",
                config.reminder_check_interval, config.channel_chat_id or "выкл")
    while True:
        try:
            await process_due_reminders(bot)
            await process_expired(bot, config)
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка в цикле планировщика")
        await asyncio.sleep(config.reminder_check_interval)
