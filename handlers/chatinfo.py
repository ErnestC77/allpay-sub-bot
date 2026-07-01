"""Логирование ID чата/канала при изменении статуса бота.

Нужен, чтобы легко узнать CHANNEL_ID: добавьте бота админом в закрытый канал —
в логах появится строка с id канала, её и пропишите в переменную CHANNEL_ID.
"""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ChatMemberUpdated

logger = logging.getLogger("chatinfo")
router = Router()


@router.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    chat = event.chat
    logger.info(
        "СТАТУС БОТА В ЧАТЕ: chat_id=%s type=%s title=%r status=%s",
        chat.id, chat.type, chat.title, event.new_chat_member.status,
    )
