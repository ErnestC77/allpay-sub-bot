"""Приветствие и главное меню (reply-кнопки)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import FSInputFile, Message

from config import Config
from handlers.common import WELCOME_IMAGE, get_user_and_lang
from i18n import t
from keyboards.inline import welcome_kb
from keyboards.reply import main_menu

router = Router()


async def show_welcome(message: Message, lang: str) -> None:
    """Приветственное сообщение с картинкой + кнопка «Купить подписку»."""
    caption = t("welcome", lang)
    if WELCOME_IMAGE.exists():
        await message.answer_photo(FSInputFile(WELCOME_IMAGE), caption=caption,
                                   reply_markup=welcome_kb(lang))
    else:
        await message.answer(caption, reply_markup=welcome_kb(lang))
    # Reply-меню отдельным сообщением (inline и reply нельзя совместить).
    await message.answer(t("menu_hint", lang), reply_markup=main_menu(lang))


# --- Обработка нажатий нижнего меню ---
# Кнопки локализованы, поэтому сверяем текст с подписями на языке пользователя.

@router.message(F.text, StateFilter(None), ~F.text.startswith("/"))
async def route_menu(message: Message, config: Config) -> None:
    from handlers import account, plans, subscription, support

    user, lang = await get_user_and_lang(message.from_user.id)
    text = (message.text or "").strip()

    if text == t("menu_plans", lang):
        await plans.show_plans_list(message, lang)
    elif text == t("menu_subscription", lang):
        await subscription.show_subscription(message, user, lang)
    elif text == t("menu_account", lang):
        await account.show_account(message, user, lang)
    elif text == t("menu_support", lang):
        await support.show_support(message, lang, config.support_contact)
    # Прочий текст игнорируем (может перехватываться FSM в других роутерах).
