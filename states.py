"""FSM-состояния бота."""
from aiogram.fsm.state import State, StatesGroup


class EmailInput(StatesGroup):
    """Ввод e-mail перед оплатой."""
    waiting = State()


class AccountEdit(StatesGroup):
    email = State()
    timezone = State()


class AdminEditPlan(StatesGroup):
    price = State()
    days = State()
    title = State()
    description = State()
    image = State()


class AdminEditText(StatesGroup):
    support_contact = State()


class AdminReminder(StatesGroup):
    add_days = State()   # ждём число дней для нового порога
    add_text = State()   # ждём текст для нового порога
    edit_text = State()  # ждём новый текст для существующего порога
