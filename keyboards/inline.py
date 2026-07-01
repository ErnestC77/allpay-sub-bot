"""Inline-клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Plan
from i18n import t


def back_kb(lang: str, cb: str = "nav:close") -> InlineKeyboardMarkup:
    """Одна кнопка «Назад»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data=cb)],
    ])


def welcome_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_buy", lang), callback_data="buy:list")],
    ])


def durations_kb(plans: list[Plan], lang: str, back_cb: str | None = "nav:close") -> InlineKeyboardMarkup:
    """Подменю выбора срока подписки."""
    builder = InlineKeyboardBuilder()
    for plan in plans:
        text = t("plan_button", lang, title=plan.title(lang), days=plan.duration_days,
                 price=plan.price_display(), currency=plan.currency)
        builder.button(text=text, callback_data=f"buy:pick:{plan.id}")
    builder.adjust(1)
    if back_cb:
        builder.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data=back_cb))
    return builder.as_markup()


def payment_methods_kb(plan_id: int, lang: str) -> InlineKeyboardMarkup:
    """Выбор способа оплаты для конкретного тарифа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("pay_allpay", lang),
                              callback_data=f"pay:allpay:{plan_id}")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="buy:list")],
    ])


def pay_url_kb(url: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("pay_open_button", lang), url=url)],
    ])


def plans_list_kb(plans: list[Plan], lang: str) -> InlineKeyboardMarkup:
    """Список тарифов в разделе «Тарифные планы»."""
    builder = InlineKeyboardBuilder()
    for plan in plans:
        text = t("plan_button", lang, title=plan.title(lang), days=plan.duration_days,
                 price=plan.price_display(), currency=plan.currency)
        builder.button(text=text, callback_data=f"plan:view:{plan.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:close"))
    return builder.as_markup()


def plan_view_kb(plan_id: int, lang: str) -> InlineKeyboardMarkup:
    """Под карточкой тарифа: купить + назад к списку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_buy", lang), callback_data=f"buy:pick:{plan_id}")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="plan:list")],
    ])


def subscription_kb(lang: str, has_sub: bool) -> InlineKeyboardMarkup:
    """Есть подписка → «Продлить», нет → «Купить». Плюс «Назад»."""
    action = t("btn_renew", lang) if has_sub else t("btn_buy", lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=action, callback_data="buy:list")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:close")],
    ])


def account_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_account_tz", lang), callback_data="acc:tz")],
        [InlineKeyboardButton(text=t("btn_account_email", lang), callback_data="acc:email")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:close")],
    ])
