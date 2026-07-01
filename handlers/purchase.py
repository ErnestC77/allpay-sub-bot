"""Поток покупки: выбор срока → карточка тарифа → оплата → e-mail → счёт AllPay."""
from __future__ import annotations

import logging
from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from db import crud
from db.models import Plan, User
from handlers.common import get_user_and_lang
from i18n import t
from keyboards.inline import durations_kb, pay_url_kb, payment_methods_kb
from payments.allpay import create_payment
from states import EmailInput
from utils import is_valid_email

logger = logging.getLogger(__name__)
router = Router()


# ---------- Шаг 1: список сроков ----------

async def show_durations(message: Message, lang: str) -> None:
    plans = await crud.list_active_plans()
    if not plans:
        await message.answer(t("plan_no_active", lang))
        return
    await message.answer(t("choose_duration", lang), reply_markup=durations_kb(plans, lang))


@router.callback_query(F.data == "buy:list")
async def cb_buy_list(callback: CallbackQuery) -> None:
    _, lang = await get_user_and_lang(callback.from_user.id)
    await callback.answer()
    await show_durations(callback.message, lang)


# ---------- Шаг 2: карточка тарифа + способы оплаты ----------

@router.callback_query(F.data.startswith("buy:pick:"))
async def cb_buy_pick(callback: CallbackQuery) -> None:
    _, lang = await get_user_and_lang(callback.from_user.id)
    plan_id = int(callback.data.rsplit(":", 1)[1])
    plan = await crud.get_plan(plan_id)
    await callback.answer()
    if plan is None or not plan.is_active:
        await callback.message.answer(t("plan_no_active", lang))
        return

    text = t("plan_detail", lang, title=plan.title(lang), description=plan.description(lang),
             days=plan.duration_days, price=plan.price_display(), currency=plan.currency)
    text += "\n\n" + t("choose_payment", lang)
    kb = payment_methods_kb(plan.id, lang)
    if plan.image_file_id:
        await callback.message.answer_photo(plan.image_file_id, caption=text, reply_markup=kb)
    else:
        await callback.message.answer(text, reply_markup=kb)


# ---------- Шаг 3: способ оплаты → проверка e-mail ----------

@router.callback_query(F.data.startswith("pay:allpay:"))
async def cb_pay_allpay(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    user, lang = await get_user_and_lang(callback.from_user.id)
    plan_id = int(callback.data.rsplit(":", 1)[1])
    plan = await crud.get_plan(plan_id)
    await callback.answer()
    if plan is None or not plan.is_active:
        await callback.message.answer(t("plan_no_active", lang))
        return

    if not user.email:
        # E-mail обязателен — уходим в FSM, запоминаем выбранный тариф.
        await state.set_state(EmailInput.waiting)
        await state.update_data(plan_id=plan_id)
        await callback.message.answer(t("email_ask", lang))
        return

    await _start_payment(callback.message, user, plan, lang, config)


@router.message(EmailInput.waiting, F.text)
async def on_email_entered(message: Message, state: FSMContext, config: Config) -> None:
    user, lang = await get_user_and_lang(message.from_user.id)
    email = (message.text or "").strip()
    if not is_valid_email(email):
        await message.answer(t("email_invalid", lang))
        return

    await crud.set_user_email(message.from_user.id, email)
    user.email = email
    data = await state.get_data()
    await state.clear()
    await message.answer(t("email_saved", lang))

    plan = await crud.get_plan(int(data.get("plan_id", 0)))
    if plan is None or not plan.is_active:
        await message.answer(t("plan_no_active", lang))
        return
    await _start_payment(message, user, plan, lang, config)


# ---------- Шаг 4: создание счёта в AllPay ----------

async def _start_payment(message: Message, user: User, plan: Plan, lang: str, config: Config) -> None:
    order_id = f"{user.tg_id}-{uuid4().hex[:12]}"
    await crud.create_payment(user.tg_id, plan, order_id)
    try:
        url = await create_payment(
            login=config.allpay_login,
            api_key=config.allpay_key,
            order_id=order_id,
            amount_major=plan.price_major,
            currency=plan.currency,
            item_name=plan.title(lang),
            client_email=user.email or "",
            webhook_url=config.allpay_webhook_url,
            success_url=config.allpay_success_url,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Ошибка создания платежа AllPay, order_id=%s", order_id)
        await message.answer(t("payment_error", lang))
        return

    await message.answer(t("payment_created", lang), reply_markup=pay_url_kb(url, lang))
