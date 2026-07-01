"""Общие помощники для хендлеров."""
from __future__ import annotations

from pathlib import Path

from db import crud
from db.models import User
from i18n import normalize_lang

WELCOME_IMAGE = Path(__file__).parent.parent / "assets" / "welcome.jpg"


async def get_user_and_lang(tg_id: int) -> tuple[User, str]:
    user = await crud.get_or_create_user(tg_id)
    return user, normalize_lang(user.language)


async def get_lang(tg_id: int) -> str:
    _, lang = await get_user_and_lang(tg_id)
    return lang
