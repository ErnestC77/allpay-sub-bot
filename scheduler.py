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
from i18n import normalize_lang
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
            await bot.send_message(sub.user_id, text, reply_markup=subscription_kb(lang))
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось отправить напоминание user=%s rule=%sд",
                             sub.user_id, rule.days_before)
    if sent:
        logger.info("Отправлено напоминаний: %s", sent)
    return sent


async def reminder_worker(bot: Bot, interval_seconds: int) -> None:
    """Бесконечный цикл проверки. Запускается как asyncio-задача из bot.py."""
    logger.info("Планировщик напоминаний запущен (интервал %s c)", interval_seconds)
    while True:
        try:
            await process_due_reminders(bot)
        except Exception:  # noqa: BLE001
            logger.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(interval_seconds)
