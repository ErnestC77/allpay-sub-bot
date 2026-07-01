"""Reply-клавиатуры (нижнее меню)."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from i18n import t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    """Главное меню 2×2, как на скриншоте."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("menu_plans", lang)),
             KeyboardButton(text=t("menu_subscription", lang))],
            [KeyboardButton(text=t("menu_account", lang)),
             KeyboardButton(text=t("menu_support", lang))],
        ],
        resize_keyboard=True,
    )
