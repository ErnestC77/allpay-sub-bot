"""Фоновая задача: уведомления об окончании подписки.

Периодически проверяет активные подписки против настроенных порогов (ReminderRule)
и отправляет уведомление, когда до конца остаётся не больше N дней. Каждый порог
отправляется один раз на подписку (дедупликация через ReminderLog), поэтому частые
проверки безопасны и устойчивы к перезапускам процесса.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from db import crud
from i18n import normalize_lang, t
from keyboards.inline import subscription_kb
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


async def process_expired(bot: Bot, channel_id: int | str | None) -> int:
    """Помечает истёкшие подписки и удаляет таких пользователей из закрытого канала."""
    removed = 0
    for uid in await crud.expire_due_subscriptions():
        user = await crud.get_or_create_user(uid)
        lang = normalize_lang(user.language)
        # Уведомляем об окончании
        try:
            await bot.send_message(uid, t("subscription_expired", lang),
                                   reply_markup=subscription_kb(lang, has_sub=False))
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось уведомить об окончании подписки user=%s", uid)
        # Удаляем из канала (ban + unban, чтобы мог вернуться после продления)
        if channel_id:
            try:
                await bot.ban_chat_member(channel_id, uid)
                await bot.unban_chat_member(channel_id, uid, only_if_banned=True)
                removed += 1
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось удалить из канала user=%s", uid)
    if removed:
        logger.info("Удалено из канала по окончании подписки: %s", removed)
    return removed


async def reminder_worker(bot: Bot, interval_seconds: int,
                          channel_id: int | str | None = None) -> None:
    """Бесконечный цикл: напоминания + снятие доступа по окончании подписки."""
    logger.info("Планировщик запущен (интервал %s c, канал=%s)",
                interval_seconds, channel_id or "выкл")
    while True:
        try:
            await process_due_reminders(bot)
            await process_expired(bot, channel_id)
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка в цикле планировщика")
        await asyncio.sleep(interval_seconds)
