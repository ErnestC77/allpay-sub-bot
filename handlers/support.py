"""Раздел «Поддержка»."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from i18n import t
from keyboards.inline import back_kb

router = Router()


async def show_support(message: Message, lang: str, contact: str) -> None:
    await message.answer(t("support_text", lang, contact=contact or "@admin"),
                         reply_markup=back_kb(lang))
