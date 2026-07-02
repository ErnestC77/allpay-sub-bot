"""Мидлвари бота."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db import crud


class UsernameMiddleware(BaseMiddleware):
    """Запоминает @username каждого, кто взаимодействует с ботом."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None and user.username:
            try:
                await crud.set_username(user.id, user.username)
            except Exception:  # noqa: BLE001
                pass
        return await handler(event, data)
