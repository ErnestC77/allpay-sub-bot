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


def payment_methods_kb(plan_id: int, lang: str, auto_renew: bool = False) -> InlineKeyboardMarkup:
    """Выбор способа оплаты + переключатель автопродления."""
    toggle = t("auto_on" if auto_renew else "auto_off", lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data=f"auto:pick:{plan_id}")],
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


def subscription_kb(lang: str, has_sub: bool, auto_renew: bool = False) -> InlineKeyboardMarkup:
    """Есть подписка → «Продлить» + переключатель автопродления, нет → «Купить». Плюс «Назад»."""
    action = t("btn_renew", lang) if has_sub else t("btn_buy", lang)
    rows = [[InlineKeyboardButton(text=action, callback_data="buy:list")]]
    if has_sub:
        toggle = t("auto_on" if auto_renew else "auto_off", lang)
        rows.append([InlineKeyboardButton(text=toggle, callback_data="auto:sub")])
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_account_tz", lang), callback_data="acc:tz")],
        [InlineKeyboardButton(text=t("btn_account_email", lang), callback_data="acc:email")],
        [InlineKeyboardButton(text=t("btn_back", lang), callback_data="nav:close")],
    ])
