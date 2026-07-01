"""Старт и выбор языка."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db import crud
from handlers.common import get_user_and_lang
from handlers.menu import show_welcome

router = Router()

# Язык по умолчанию — русский; экран выбора языка убран.
DEFAULT_LANG = "ru"


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user, lang = await get_user_and_lang(message.from_user.id)
    if user.language is None:
        await crud.set_user_language(message.from_user.id, DEFAULT_LANG)
        lang = DEFAULT_LANG
    await show_welcome(message, lang)
