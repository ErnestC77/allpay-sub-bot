"""Раздел «Моя подписка»."""
from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from db import crud
from db.models import User
from i18n import t
from keyboards.inline import subscription_kb
from utils import format_dt

router = Router()


async def show_subscription(message: Message, user: User, lang: str) -> None:
    sub = await crud.get_active_subscription(user.tg_id)
    if sub is None:
        await message.answer(t("subscription_none", lang), reply_markup=subscription_kb(lang))
        return

    plan = await crud.get_plan(sub.plan_id) if sub.plan_id else None
    title = plan.title(lang) if plan else "—"
    await message.answer(
        t("subscription_active", lang, title=title, date=format_dt(sub.end_at, user.timezone)),
        reply_markup=subscription_kb(lang),
    )
