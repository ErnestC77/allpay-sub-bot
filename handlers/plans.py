"""Раздел «Тарифные планы»: список тарифов и карточка тарифа."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from db import crud
from handlers.common import get_lang
from i18n import t
from keyboards.inline import plan_view_kb, plans_list_kb

router = Router()


async def show_plans_list(message: Message, lang: str) -> None:
    plans = await crud.list_active_plans()
    if not plans:
        await message.answer(t("plan_no_active", lang))
        return
    await message.answer(t("choose_duration", lang), reply_markup=plans_list_kb(plans, lang))


async def show_plan_card(message: Message, plan_id: int, lang: str) -> None:
    plan = await crud.get_plan(plan_id)
    if plan is None or not plan.is_active:
        await message.answer(t("plan_no_active", lang))
        return
    text = t("plan_detail", lang, title=plan.title(lang), description=plan.description(lang),
             days=plan.duration_days, price=plan.price_display(), currency=plan.currency)
    kb = plan_view_kb(plan.id, lang)
    if plan.image_file_id:
        await message.answer_photo(plan.image_file_id, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "plan:list")
async def cb_plan_list(callback: CallbackQuery) -> None:
    lang = await get_lang(callback.from_user.id)
    await callback.answer()
    await show_plans_list(callback.message, lang)


@router.callback_query(F.data.startswith("plan:view:"))
async def cb_plan_view(callback: CallbackQuery) -> None:
    lang = await get_lang(callback.from_user.id)
    plan_id = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await show_plan_card(callback.message, plan_id, lang)
