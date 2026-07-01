"""Старт и выбор языка."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db import crud
from handlers.common import get_user_and_lang
from handlers.menu import show_welcome
from i18n import lang_name, t
from keyboards.inline import languages_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user, lang = await get_user_and_lang(message.from_user.id)
    if user.language is None:
        await message.answer(t("choose_language", lang), reply_markup=languages_kb())
    else:
        await show_welcome(message, lang)


@router.callback_query(F.data.startswith("lang:"))
async def on_language(callback: CallbackQuery) -> None:
    code = callback.data.split(":", 1)[1]
    await crud.set_user_language(callback.from_user.id, code)
    await callback.answer(t("language_saved", code, lang=lang_name(code)))
    # Убираем клавиатуру выбора языка из исходного сообщения.
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass
    await show_welcome(callback.message, code)
