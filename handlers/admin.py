"""Админ-панель внутри бота: управление тарифами.

Доступ только для Telegram ID из ADMIN_IDS. Все тексты — на русском (оператор один).
Редактируются русские поля тарифа; английские подхватываются с фолбэком на русские.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (CallbackQuery, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message)

from config import Config
from db import crud
from db.models import Plan, ReminderRule
from i18n import normalize_lang, t
from keyboards.reply import main_menu
from states import AdminEditPlan, AdminImport, AdminManage, AdminReminder
from utils import format_dt, parse_admin_datetime

logger = logging.getLogger("admin")
router = Router()


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, config: Config) -> bool:
        if not event.from_user:
            return False
        uid = event.from_user.id
        if uid in config.admin_ids:   # супер-админы из настроек
            return True
        return await crud.is_admin_db(uid)


# Ограничиваем весь роутер администраторами.
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _plans_list_kb(plans: list[Plan]) -> InlineKeyboardMarkup:
    rows = []
    for p in plans:
        mark = "🟢" if p.is_active else "🔴"
        rows.append([InlineKeyboardButton(
            text=f"{mark} {p.title_ru or p.title_en or ('#'+str(p.id))} · "
                 f"{p.duration_days}д · {p.price_display()} {p.currency}",
            callback_data=f"adm:plan:{p.id}")])
    rows.append([InlineKeyboardButton(text="← В меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _plan_edit_kb(plan: Plan) -> InlineKeyboardMarkup:
    toggle = "Скрыть 🔴" if plan.is_active else "Показать 🟢"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена", callback_data=f"adm:edit:price:{plan.id}"),
         InlineKeyboardButton(text="⏳ Срок (дни)", callback_data=f"adm:edit:days:{plan.id}")],
        [InlineKeyboardButton(text="📝 Название", callback_data=f"adm:edit:title:{plan.id}"),
         InlineKeyboardButton(text="📄 Описание", callback_data=f"adm:edit:desc:{plan.id}")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data=f"adm:edit:image:{plan.id}")],
        [InlineKeyboardButton(text=toggle, callback_data=f"adm:toggle:{plan.id}")],
        [InlineKeyboardButton(text="← К списку", callback_data="adm:list")],
    ])


def _plan_summary(plan: Plan) -> str:
    return (f"<b>Тариф #{plan.id}</b>\n\n"
            f"Название (RU): {plan.title_ru or '—'}\n"
            f"Описание (RU): {plan.description_ru or '—'}\n"
            f"Срок: {plan.duration_days} дней\n"
            f"Цена: {plan.price_display()} {plan.currency}\n"
            f"Фото: {'есть' if plan.image_file_id else 'нет'}\n"
            f"Статус: {'активен 🟢' if plan.is_active else 'скрыт 🔴'}")


async def _show_plan(message: Message, plan: Plan) -> None:
    await message.answer(_plan_summary(plan), reply_markup=_plan_edit_kb(plan))


def _admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📆 Тарифы", callback_data="adm:plans")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="adm:reminders")],
        [InlineKeyboardButton(text="💳 Подписчики", callback_data="adm:subs")],
        [InlineKeyboardButton(text="👥 Импорт подписчиков", callback_data="adm:import")],
        [InlineKeyboardButton(text="👮 Админы", callback_data="adm:admins")],
    ])


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🛠 <b>Админка</b>\nВыберите раздел:", reply_markup=_admin_menu_kb())


@router.callback_query(F.data == "adm:menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("🛠 <b>Админка</b>\nВыберите раздел:",
                                  reply_markup=_admin_menu_kb())


@router.callback_query(F.data == "adm:plans")
async def cb_admin_plans(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_plans_list(callback.message)


@router.callback_query(F.data == "adm:list")
async def cb_admin_list(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_plans_list(callback.message)


async def _show_plans_list(message: Message) -> None:
    plans = await crud.list_all_plans()
    if not plans:
        await message.answer("Тарифов пока нет.")
        return
    await message.answer("📆 <b>Тарифы</b>\nВыберите тариф для редактирования:",
                         reply_markup=_plans_list_kb(plans))


@router.callback_query(F.data.startswith("adm:plan:"))
async def cb_admin_plan(callback: CallbackQuery) -> None:
    plan_id = int(callback.data.rsplit(":", 1)[1])
    plan = await crud.get_plan(plan_id)
    await callback.answer()
    if plan:
        await _show_plan(callback.message, plan)


@router.callback_query(F.data.startswith("adm:toggle:"))
async def cb_admin_toggle(callback: CallbackQuery) -> None:
    plan_id = int(callback.data.rsplit(":", 1)[1])
    plan = await crud.get_plan(plan_id)
    if plan:
        plan = await crud.update_plan(plan_id, is_active=not plan.is_active)
        await callback.answer("Статус изменён")
        await _show_plan(callback.message, plan)
    else:
        await callback.answer()


_FIELD_PROMPTS = {
    "price": ("price", AdminEditPlan.price, "Введите новую цену в основной валюте (например, 39 или 39.90):"),
    "days": ("days", AdminEditPlan.days, "Введите срок подписки в днях (целое число):"),
    "title": ("title", AdminEditPlan.title, "Введите название тарифа (RU):"),
    "desc": ("desc", AdminEditPlan.description, "Введите описание тарифа (RU):"),
    "image": ("image", AdminEditPlan.image, "Отправьте фото тарифа одним изображением:"),
}


@router.callback_query(F.data.startswith("adm:edit:"))
async def cb_admin_edit(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, field, plan_id = callback.data.split(":")
    if field not in _FIELD_PROMPTS:
        await callback.answer()
        return
    _, fsm_state, prompt = _FIELD_PROMPTS[field]
    await state.set_state(fsm_state)
    await state.update_data(plan_id=int(plan_id))
    await callback.answer()
    await callback.message.answer(prompt)


async def _finish_edit(message: Message, state: FSMContext, **fields) -> None:
    data = await state.get_data()
    plan_id = int(data.get("plan_id", 0))
    await state.clear()
    plan = await crud.update_plan(plan_id, **fields)
    if plan:
        await message.answer("✅ Сохранено.")
        await _show_plan(message, plan)


@router.message(AdminEditPlan.price, F.text)
async def edit_price(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").replace(",", ".").strip()
    try:
        minor = int(round(float(raw) * 100))
        if minor < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверная цена. Пример: 39 или 39.90")
        return
    await _finish_edit(message, state, price=minor)


@router.message(AdminEditPlan.days, F.text)
async def edit_days(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Введите положительное целое число дней.")
        return
    await _finish_edit(message, state, duration_days=int(raw))


@router.message(AdminEditPlan.title, F.text)
async def edit_title(message: Message, state: FSMContext) -> None:
    await _finish_edit(message, state, title_ru=(message.text or "").strip())


@router.message(AdminEditPlan.description, F.text)
async def edit_description(message: Message, state: FSMContext) -> None:
    await _finish_edit(message, state, description_ru=(message.text or "").strip())


@router.message(AdminEditPlan.image, F.photo)
async def edit_image(message: Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id
    await _finish_edit(message, state, image_file_id=file_id)


@router.message(AdminEditPlan.image)
async def edit_image_invalid(message: Message) -> None:
    await message.answer("❌ Пришлите именно фото (изображение).")


# ==================== Раздел «Уведомления» ====================

def _rule_label(days: int) -> str:
    if days > 0:
        return f"за {days} дн. до"
    if days == 0:
        return "в день окончания"
    return f"через {abs(days)} дн. после"


def _reminders_kb(rules: list[ReminderRule]) -> InlineKeyboardMarkup:
    rows = []
    for r in rules:
        mark = "🟢" if r.is_active else "🔴"
        rows.append([
            InlineKeyboardButton(text=f"{mark} {_rule_label(r.days_before)}",
                                 callback_data=f"adm:rem:toggle:{r.id}"),
            InlineKeyboardButton(text="✏️ текст", callback_data=f"adm:rem:text:{r.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"adm:rem:del:{r.id}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Добавить порог", callback_data="adm:rem:add")])
    rows.append([InlineKeyboardButton(text="← В меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_reminders(message: Message) -> None:
    rules = await crud.list_reminder_rules()
    header = ("🔔 <b>Уведомления об окончании подписки</b>\n\n"
              "Пороги (можно несколько):\n"
              "• <b>положительное</b> число — за N дней ДО окончания;\n"
              "• <b>0</b> — в день окончания;\n"
              "• <b>отрицательное</b> — через N дней ПОСЛЕ окончания.\n"
              "🟢 — активен, 🔴 — выключен. В тексте доступны {days} и {date}.")
    if not rules:
        header += "\n\n<i>Порогов пока нет.</i>"
    await message.answer(header, reply_markup=_reminders_kb(rules))


@router.callback_query(F.data == "adm:reminders")
async def cb_reminders(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_reminders(callback.message)


@router.callback_query(F.data.startswith("adm:rem:toggle:"))
async def cb_rem_toggle(callback: CallbackQuery) -> None:
    rule_id = int(callback.data.rsplit(":", 1)[1])
    rule = await crud.get_reminder_rule(rule_id)
    if rule:
        await crud.update_reminder_rule(rule_id, is_active=not rule.is_active)
        await callback.answer("Статус изменён")
    else:
        await callback.answer()
    await _show_reminders(callback.message)


@router.callback_query(F.data.startswith("adm:rem:del:"))
async def cb_rem_del(callback: CallbackQuery) -> None:
    rule_id = int(callback.data.rsplit(":", 1)[1])
    await crud.delete_reminder_rule(rule_id)
    await callback.answer("Порог удалён")
    await _show_reminders(callback.message)


@router.callback_query(F.data.startswith("adm:rem:text:"))
async def cb_rem_text(callback: CallbackQuery, state: FSMContext) -> None:
    rule_id = int(callback.data.rsplit(":", 1)[1])
    await state.set_state(AdminReminder.edit_text)
    await state.update_data(rule_id=rule_id)
    await callback.answer()
    await callback.message.answer(
        "Пришлите новый текст уведомления.\n"
        "Можно использовать {days} (дней до конца) и {date} (дата окончания).")


@router.callback_query(F.data == "adm:rem:add")
async def cb_rem_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminReminder.add_days)
    await callback.answer()
    await callback.message.answer(
        "Когда слать уведомление? Введите целое число:\n"
        "• <b>N</b> — за N дней ДО окончания (напр. 3)\n"
        "• <b>0</b> — в день окончания\n"
        "• <b>-N</b> — через N дней ПОСЛЕ окончания (напр. -7)")


@router.message(AdminReminder.add_days, F.text)
async def rem_add_days(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not (raw.lstrip("-").isdigit()) or abs(int(raw)) > 3650:
        await message.answer("❌ Введите целое число (например 3, 0 или -7).")
        return
    await state.update_data(days=int(raw))
    await state.set_state(AdminReminder.add_text)
    await message.answer("Теперь пришлите текст уведомления.\n"
                         "Доступны подстановки {days} и {date}.")


@router.message(AdminReminder.add_text, F.text)
async def rem_add_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    days = int(data.get("days", 0))
    await state.clear()
    rule = await crud.add_reminder_rule(days, (message.text or "").strip())
    if rule is None:
        await message.answer(f"❌ Порог на {days} дн. уже существует.")
    else:
        await message.answer("✅ Порог добавлен.")
    await _show_reminders(message)


@router.message(AdminReminder.edit_text, F.text)
async def rem_edit_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    rule_id = int(data.get("rule_id", 0))
    await state.clear()
    await crud.update_reminder_rule(rule_id, text=(message.text or "").strip())
    await message.answer("✅ Текст обновлён.")
    await _show_reminders(message)


# ==================== Импорт существующих подписчиков ====================

@router.callback_query(F.data == "adm:import")
async def cb_import(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminImport.end_date)
    await callback.answer()
    await callback.message.answer(
        "👥 <b>Импорт подписчиков</b>\n\n"
        "Шаг 1/2. Введите дату и время окончания подписки для этой партии (UTC).\n"
        "Формат: <code>ДД.ММ.ГГГГ</code> или <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
        "Например: <code>31.12.2026</code> или <code>31.12.2026 20:00</code>")


@router.message(AdminImport.end_date, F.text)
async def import_date(message: Message, state: FSMContext) -> None:
    end_at = parse_admin_datetime(message.text or "")
    if end_at is None:
        await message.answer("❌ Неверный формат. Пример: 31.12.2026 или 31.12.2026 20:00")
        return
    await state.update_data(end_iso=end_at.isoformat())
    await state.set_state(AdminImport.ids)
    await message.answer(
        "Шаг 2/2. Пришлите подписчиков — <b>ID</b> или <b>@username</b> "
        "(вперемешку), через пробел, запятую или с новой строки.\n"
        "Пример: <code>910256253 @ivan_petrov @nastya</code>\n\n"
        "⚠️ @username сработает только для тех, у кого он задан публично.")


async def _resolve_targets(bot, tokens: list[str]) -> tuple[list[int], list[str]]:
    """Превращает ID/@username в user_id. Возвращает (id-шники, неразрешённые)."""
    ids: list[int] = []
    unresolved: list[str] = []
    seen: set[int] = set()
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok.lstrip("-").isdigit():
            uid = int(tok)
        else:
            uname = tok.lstrip("@")
            try:
                chat = await bot.get_chat("@" + uname)
                if chat.type != "private":   # это канал/группа, а не пользователь
                    unresolved.append(tok)
                    continue
                uid = chat.id
                if chat.username:
                    await crud.set_username(uid, chat.username)
            except Exception:  # noqa: BLE001 — не найден / нет username
                unresolved.append(tok)
                continue
        if uid not in seen:
            seen.add(uid)
            ids.append(uid)
    return ids, unresolved


@router.message(AdminImport.ids, F.text)
async def import_ids(message: Message, state: FSMContext) -> None:
    from datetime import datetime

    data = await state.get_data()
    await state.clear()
    end_at = datetime.fromisoformat(data["end_iso"])

    tokens = (message.text or "").replace(",", " ").split()
    ids, unresolved = await _resolve_targets(message.bot, tokens)
    if not ids and not unresolved:
        await message.answer("❌ Пусто. Начните заново: /admin")
        return

    added = notified = 0
    failed_notify: list[int] = []
    for uid in ids:
        try:
            sub = await crud.grant_subscription(uid, end_at)
            added += 1
        except Exception:  # noqa: BLE001
            logger.exception("Импорт: не удалось создать подписку uid=%s", uid)
            continue
        try:
            u = await crud.get_or_create_user(uid)
            lang = normalize_lang(u.language)
            await message.bot.send_message(
                uid, t("import_welcome", lang, date=format_dt(sub.end_at, u.timezone)),
                reply_markup=main_menu(lang))
            notified += 1
        except Exception:  # noqa: BLE001 — обычно пользователь не запускал бота
            failed_notify.append(uid)

    report = (f"✅ Добавлено подписок: <b>{added}</b>\n"
              f"✉️ Уведомлено: <b>{notified}</b>\n"
              f"⚠️ Не удалось написать (не запускали бота): <b>{len(failed_notify)}</b>")
    if failed_notify:
        report += "\n<code>" + " ".join(str(x) for x in failed_notify[:100]) + "</code>"
    if unresolved:
        report += ("\n\n🚫 Не удалось определить (нет публичного @username / не найдены):\n"
                   + " ".join(unresolved[:100]))
    await message.answer(report)


# ==================== Управление админами ====================

def _admins_kb(db_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🗑 Удалить {i}", callback_data=f"adm:admdel:{i}")]
            for i in db_ids]
    rows.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:admadd")])
    rows.append([InlineKeyboardButton(text="← В меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_admins(message: Message, config: Config) -> None:
    db_ids = await crud.list_admin_ids()
    env_ids = sorted(config.admin_ids)
    text = "👮 <b>Администраторы</b>\n\n<b>Из настроек</b> (несменяемые):\n"
    text += ("\n".join(f"• <code>{i}</code>" for i in env_ids) or "—")
    text += "\n\n<b>Добавленные</b>:\n"
    text += ("\n".join(f"• <code>{i}</code>" for i in db_ids) or "—")
    await message.answer(text, reply_markup=_admins_kb(db_ids))


@router.callback_query(F.data == "adm:admins")
async def cb_admins(callback: CallbackQuery, state: FSMContext, config: Config) -> None:
    await state.clear()
    await callback.answer()
    await _show_admins(callback.message, config)


@router.callback_query(F.data == "adm:admadd")
async def cb_admin_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminManage.add_admin)
    await callback.answer()
    await callback.message.answer(
        "Пришлите Telegram ID нового администратора (число).\n"
        "ID можно узнать, например, через @userinfobot.")


@router.message(AdminManage.add_admin, F.text)
async def admin_add_id(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("❌ Нужно число (Telegram ID). Начните заново: /admin")
        return
    uid = int(raw)
    added = await crud.add_admin(uid)
    if uid in config.admin_ids:
        await message.answer("ℹ️ Этот ID уже админ из настроек.")
    elif added:
        await message.answer(f"✅ Админ <code>{uid}</code> добавлен.")
    else:
        await message.answer("ℹ️ Этот ID уже был админом.")
    await _show_admins(message, config)


@router.callback_query(F.data.startswith("adm:admdel:"))
async def cb_admin_del(callback: CallbackQuery, config: Config) -> None:
    uid = int(callback.data.rsplit(":", 1)[1])
    await crud.remove_admin(uid)
    await callback.answer("Удалён")
    await _show_admins(callback.message, config)


# ==================== Подписчики (просмотр/удаление) ====================

SUBS_PAGE = 8


async def _show_subscribers(message: Message, page: int) -> None:
    total = await crud.count_active_subscribers()
    subs = await crud.list_active_subscribers(limit=SUBS_PAGE, offset=page * SUBS_PAGE)
    rows = []
    for s in subs:
        u = await crud.get_or_create_user(s.user_id)
        name = u.username
        if not name:   # подтягиваем ник на лету и запоминаем
            try:
                chat = await message.bot.get_chat(s.user_id)
                if chat.username:
                    name = chat.username
                    await crud.set_username(s.user_id, name)
            except Exception:  # noqa: BLE001
                pass
        label = f"@{name}" if name else str(s.user_id)
        rows.append([InlineKeyboardButton(
            text=f"👤 {label} · до {format_dt(s.end_at, u.timezone)[:10]}",
            callback_data=f"adm:sub:{s.user_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"adm:subs:page:{page-1}"))
    if (page + 1) * SUBS_PAGE < total:
        nav.append(InlineKeyboardButton(text="→", callback_data=f"adm:subs:page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="← В меню", callback_data="adm:menu")])
    header = f"💳 <b>Активные подписчики</b>: {total}"
    if not subs:
        header += "\n\n<i>Пока нет.</i>"
    await message.answer(header, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "adm:subs")
async def cb_subs(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await _show_subscribers(callback.message, 0)


@router.callback_query(F.data.startswith("adm:subs:page:"))
async def cb_subs_page(callback: CallbackQuery) -> None:
    page = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    await _show_subscribers(callback.message, page)


@router.callback_query(F.data.startswith("adm:sub:"))
async def cb_sub_detail(callback: CallbackQuery) -> None:
    uid = int(callback.data.rsplit(":", 1)[1])
    await callback.answer()
    user = await crud.get_or_create_user(uid)
    sub = await crud.get_active_subscription(uid)
    plan = await crud.get_plan(sub.plan_id) if (sub and sub.plan_id) else None
    # попробуем показать имя/username
    handle = ""
    try:
        chat = await callback.bot.get_chat(uid)
        handle = ("@" + chat.username) if chat.username else (chat.full_name or "")
    except Exception:  # noqa: BLE001
        pass
    lines = [f"👤 <b>Подписчик {uid}</b>"]
    if handle:
        lines.append(f"Имя: {handle}")
    if sub:
        lines.append(f"Действует до: <b>{format_dt(sub.end_at, user.timezone)}</b>")
        lines.append(f"Тариф: {plan.title('ru') if plan else 'вручную/импорт'}")
    else:
        lines.append("Активной подписки нет.")
    lines.append(f"Автопродление: {'вкл' if user.auto_renew else 'выкл'}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить подписку", callback_data=f"adm:subdel:{uid}")],
        [InlineKeyboardButton(text="← К списку", callback_data="adm:subs")],
    ])
    await callback.message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("adm:subdel:"))
async def cb_sub_del(callback: CallbackQuery, config: Config) -> None:
    uid = int(callback.data.rsplit(":", 1)[1])
    n = await crud.revoke_user_subscriptions(uid)
    # снять доступ в канале
    if config.channel_chat_id:
        try:
            await callback.bot.ban_chat_member(config.channel_chat_id, uid)
            await callback.bot.unban_chat_member(config.channel_chat_id, uid, only_if_banned=True)
        except Exception:  # noqa: BLE001
            logger.exception("Не удалось удалить из канала uid=%s", uid)
    # уведомить пользователя
    try:
        u = await crud.get_or_create_user(uid)
        await callback.bot.send_message(uid, t("subscription_revoked", normalize_lang(u.language)))
    except Exception:  # noqa: BLE001
        pass
    await callback.answer(f"Отозвано подписок: {n}")
    await _show_subscribers(callback.message, 0)
