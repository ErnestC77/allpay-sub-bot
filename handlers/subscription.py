"""Раздел «Моя подписка»."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from db import crud
from db.models import User
from handlers.common import get_user_and_lang
from i18n import t
from keyboards.inline import subscription_kb
from utils import format_dt

router = Router()


def _auto_note(user: User, lang: str) -> str:
    """Строка о состоянии автопродления (для активной подписки)."""
    state = t("auto_state_on" if user.auto_renew else "auto_state_off", lang)
    card = t("auto_card", lang, mask=user.card_mask) if (user.auto_renew and user.card_mask) else ""
    return t("auto_renew_note", lang, state=state, card=card)


async def show_subscription(message: Message, user: User, lang: str) -> None:
    sub = await crud.get_active_subscription(user.tg_id)
    if sub is None:
        await message.answer(t("subscription_none", lang),
                             reply_markup=subscription_kb(lang, has_sub=False))
        return

    plan = await crud.get_plan(sub.plan_id) if sub.plan_id else None
    title = plan.title(lang) if plan else "—"
    text = t("subscription_active", lang, title=title, date=format_dt(sub.end_at, user.timezone))
    text += _auto_note(user, lang)
    await message.answer(
        text, reply_markup=subscription_kb(lang, has_sub=True, auto_renew=user.auto_renew),
    )


@router.callback_query(F.data == "auto:sub")
async def cb_auto_toggle_sub(callback: CallbackQuery) -> None:
    """Переключатель автопродления в разделе «Моя подписка»."""
    user, lang = await get_user_and_lang(callback.from_user.id)
    new_value = not user.auto_renew
    await crud.set_auto_renew(callback.from_user.id, new_value)
    await callback.answer(t("auto_on" if new_value else "auto_off", lang))
    # Перерисуем экран подписки актуальным состоянием.
    user, lang = await get_user_and_lang(callback.from_user.id)
    try:
        await callback.message.delete()
    except Exception:  # noqa: BLE001
        pass
    await show_subscription(callback.message, user, lang)