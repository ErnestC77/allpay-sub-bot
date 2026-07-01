"""Запросы к БД."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from db.database import get_sessionmaker
from db.models import (Payment, Plan, ReminderLog, ReminderRule, Subscription,
                       User, utcnow)


# ---------- Пользователи ----------

async def get_or_create_user(tg_id: int) -> User:
    async with get_sessionmaker()() as session:
        user = await session.get(User, tg_id)
        if user is None:
            user = User(tg_id=tg_id)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


async def set_user_language(tg_id: int, lang: str) -> None:
    async with get_sessionmaker()() as session:
        user = await session.get(User, tg_id)
        if user:
            user.language = lang
            await session.commit()


async def set_user_email(tg_id: int, email: str) -> None:
    async with get_sessionmaker()() as session:
        user = await session.get(User, tg_id)
        if user:
            user.email = email
            await session.commit()


async def set_user_timezone(tg_id: int, tz: str) -> None:
    async with get_sessionmaker()() as session:
        user = await session.get(User, tg_id)
        if user:
            user.timezone = tz
            await session.commit()


# ---------- Тарифы ----------

async def list_active_plans() -> list[Plan]:
    async with get_sessionmaker()() as session:
        result = await session.scalars(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order, Plan.id)
        )
        return list(result)


async def list_all_plans() -> list[Plan]:
    async with get_sessionmaker()() as session:
        result = await session.scalars(select(Plan).order_by(Plan.sort_order, Plan.id))
        return list(result)


async def get_plan(plan_id: int) -> Plan | None:
    async with get_sessionmaker()() as session:
        return await session.get(Plan, plan_id)


async def update_plan(plan_id: int, **fields) -> Plan | None:
    async with get_sessionmaker()() as session:
        plan = await session.get(Plan, plan_id)
        if plan is None:
            return None
        for key, value in fields.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        await session.commit()
        await session.refresh(plan)
        return plan


# ---------- Платежи ----------

async def create_payment(user_id: int, plan: Plan, order_id: str) -> Payment:
    async with get_sessionmaker()() as session:
        payment = Payment(
            user_id=user_id,
            plan_id=plan.id,
            order_id=order_id,
            amount=plan.price,
            currency=plan.currency,
            status="pending",
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment


async def get_payment_by_order(order_id: str) -> Payment | None:
    async with get_sessionmaker()() as session:
        return await session.scalar(select(Payment).where(Payment.order_id == order_id))


# ---------- Подписки ----------

async def get_active_subscription(user_id: int) -> Subscription | None:
    """Последняя действующая подписка пользователя (end_at в будущем)."""
    async with get_sessionmaker()() as session:
        return await session.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.end_at > utcnow(),
            )
            .order_by(Subscription.end_at.desc())
            .limit(1)
        )


async def mark_paid_and_activate(order_id: str, allpay_ref: str | None) -> Subscription | None:
    """Идемпотентно отмечает платёж оплаченным и создаёт/продлевает подписку.

    Возвращает подписку при первой успешной обработке; ``None`` — если платёж
    уже был обработан ранее или не найден (защита от повторных webhook AllPay).
    """
    async with get_sessionmaker()() as session:
        payment = await session.scalar(select(Payment).where(Payment.order_id == order_id))
        if payment is None or payment.status == "paid":
            return None  # неизвестный или уже обработанный платёж — выходим

        plan = await session.get(Plan, payment.plan_id) if payment.plan_id else None
        duration = plan.duration_days if plan else 30

        # Точка продления: от конца текущей активной подписки, иначе от «сейчас».
        now = utcnow()
        current = await session.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == payment.user_id,
                Subscription.status == "active",
                Subscription.end_at > now,
            )
            .order_by(Subscription.end_at.desc())
            .limit(1)
        )
        base = current.end_at if current else now
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)

        # Прибавляем срок к концу текущей подписки (дни накапливаются корректно),
        # а время окончания привязываем к моменту ПОСЛЕДНЕГО оформления (now),
        # чтобы ориентир был по последней покупке, а не по самой первой.
        end_at = (base + timedelta(days=duration)).replace(
            hour=now.hour, minute=now.minute,
            second=now.second, microsecond=now.microsecond,
        )

        subscription = Subscription(
            user_id=payment.user_id,
            plan_id=payment.plan_id,
            start_at=now,
            end_at=end_at,
            status="active",
        )
        session.add(subscription)

        payment.status = "paid"
        payment.allpay_ref = allpay_ref
        payment.paid_at = now

        await session.commit()
        await session.refresh(subscription)
        return subscription


# ---------- Напоминания об окончании подписки ----------

async def list_reminder_rules(active_only: bool = False) -> list[ReminderRule]:
    async with get_sessionmaker()() as session:
        stmt = select(ReminderRule).order_by(ReminderRule.days_before.desc())
        if active_only:
            stmt = stmt.where(ReminderRule.is_active.is_(True))
        return list(await session.scalars(stmt))


async def get_reminder_rule(rule_id: int) -> ReminderRule | None:
    async with get_sessionmaker()() as session:
        return await session.get(ReminderRule, rule_id)


async def add_reminder_rule(days_before: int, text: str) -> ReminderRule | None:
    """Создаёт порог. Возвращает None, если такой days_before уже существует."""
    async with get_sessionmaker()() as session:
        exists = await session.scalar(
            select(ReminderRule).where(ReminderRule.days_before == days_before)
        )
        if exists is not None:
            return None
        rule = ReminderRule(days_before=days_before, text=text, is_active=True)
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def update_reminder_rule(rule_id: int, **fields) -> ReminderRule | None:
    async with get_sessionmaker()() as session:
        rule = await session.get(ReminderRule, rule_id)
        if rule is None:
            return None
        for key, value in fields.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        await session.commit()
        await session.refresh(rule)
        return rule


async def delete_reminder_rule(rule_id: int) -> bool:
    async with get_sessionmaker()() as session:
        rule = await session.get(ReminderRule, rule_id)
        if rule is None:
            return False
        await session.delete(rule)
        await session.commit()
        return True


async def due_reminders() -> list[tuple[Subscription, ReminderRule]]:
    """Возвращает пары (подписка, порог), по которым пора отправить уведомление.

    Условие для порога N дней: подписка активна, ещё не истекла, до конца осталось
    не больше N дней, и по этой паре (подписка, N) уведомление ещё не отправлялось.
    """
    from datetime import timedelta

    now = utcnow()
    result: list[tuple[Subscription, ReminderRule]] = []
    async with get_sessionmaker()() as session:
        rules = list(await session.scalars(
            select(ReminderRule).where(ReminderRule.is_active.is_(True))
        ))
        for rule in rules:
            threshold = now + timedelta(days=rule.days_before)
            sent_subq = (
                select(ReminderLog.subscription_id)
                .where(ReminderLog.days_before == rule.days_before)
                .scalar_subquery()
            )
            subs = await session.scalars(
                select(Subscription).where(
                    Subscription.status == "active",
                    Subscription.end_at > now,
                    Subscription.end_at <= threshold,
                    Subscription.id.notin_(sent_subq),
                )
            )
            for sub in subs:
                result.append((sub, rule))
    return result


async def log_reminder(subscription_id: int, days_before: int) -> bool:
    """Отмечает напоминание отправленным. False, если уже было (гонка/дубль)."""
    from sqlalchemy.exc import IntegrityError

    async with get_sessionmaker()() as session:
        session.add(ReminderLog(subscription_id=subscription_id, days_before=days_before))
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            return False
