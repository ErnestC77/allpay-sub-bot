"""Inline-клавиатуры."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Plan
from i18n import LANGUAGES, t


def languages_kb() -> InlineKeyboardMarkup:
    """Сетка выбора языка 2 в ряд (как на скриншоте)."""
    builder = InlineKeyboardBuilder()
    for code, name, flag in LANGUAGES:
        builder.button(text=f"{flag} {name}", callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()


def welcome_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_buy", lang), callback_data="buy:list")],
    ])


def durations_kb(plans: list[Plan], lang: str, back_cb: str | None = None) -> InlineKeyboardMarkup:
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
    return builder.as_markup()


def plan_view_kb(plan_id: int, lang: str) -> InlineKeyboardMarkup:
    """Под карточкой тарифа: купить + назад к списку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_buy", lang), callback_data=f"buy:pick:{plan_id}")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="plan:list")],
    ])


def subscription_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_renew", lang), callback_data="buy:list")],
    ])


def account_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_account_lang", lang), callback_data="acc:lang")],
        [InlineKeyboardButton(text=t("btn_account_tz", lang), callback_data="acc:tz")],
        [InlineKeyboardButton(text=t("btn_account_email", lang), callback_data="acc:email")],
    ])
