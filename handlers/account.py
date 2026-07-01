"""Раздел «Мой аккаунт»: язык, часовой пояс, e-mail."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db import crud
from db.models import User
from handlers.common import get_user_and_lang
from i18n import lang_name, t
from keyboards.inline import account_kb, languages_kb
from states import AccountEdit
from utils import is_valid_email, is_valid_tz

router = Router()


async def show_account(message: Message, user: User, lang: str) -> None:
    email = user.email or t("account_email_none", lang)
    await message.answer(
        t("account_body", lang, tg_id=user.tg_id, lang=lang_name(lang),
          tz=user.timezone, email=email),
        reply_markup=account_kb(lang),
    )


@router.callback_query(F.data == "acc:lang")
async def cb_acc_lang(callback: CallbackQuery) -> None:
    lang = (await get_user_and_lang(callback.from_user.id))[1]
    await callback.answer()
    await callback.message.answer(t("choose_language", lang), reply_markup=languages_kb())


@router.callback_query(F.data == "acc:email")
async def cb_acc_email(callback: CallbackQuery, state: FSMContext) -> None:
    lang = (await get_user_and_lang(callback.from_user.id))[1]
    await state.set_state(AccountEdit.email)
    await callback.answer()
    await callback.message.answer(t("account_email_ask", lang))


@router.callback_query(F.data == "acc:tz")
async def cb_acc_tz(callback: CallbackQuery, state: FSMContext) -> None:
    lang = (await get_user_and_lang(callback.from_user.id))[1]
    await state.set_state(AccountEdit.timezone)
    await callback.answer()
    await callback.message.answer(t("account_tz_ask", lang))


@router.message(AccountEdit.email, F.text)
async def on_account_email(message: Message, state: FSMContext) -> None:
    lang = (await get_user_and_lang(message.from_user.id))[1]
    email = (message.text or "").strip()
    if not is_valid_email(email):
        await message.answer(t("email_invalid", lang))
        return
    await crud.set_user_email(message.from_user.id, email)
    await state.clear()
    await message.answer(t("account_email_updated", lang))


@router.message(AccountEdit.timezone, F.text)
async def on_account_tz(message: Message, state: FSMContext) -> None:
    lang = (await get_user_and_lang(message.from_user.id))[1]
    tz = (message.text or "").strip().upper()
    if not is_valid_tz(tz):
        await message.answer(t("account_tz_invalid", lang))
        return
    await crud.set_user_timezone(message.from_user.id, tz)
    await state.clear()
    await message.answer(t("account_tz_updated", lang, tz=tz))
