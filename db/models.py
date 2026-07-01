"""Модели БД (SQLAlchemy 2.0, async)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str] = mapped_column(String(16), default="UTC")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Автопродление по токену карты AllPay
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    allpay_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_mask: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    # Цена в минимальных единицах валюты (агорот для ILS): 3900 = 39.00 ILS
    price: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="ILS")

    title_ru: Mapped[str] = mapped_column(String(255), default="")
    title_en: Mapped[str] = mapped_column(String(255), default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    description_en: Mapped[str] = mapped_column(Text, default="")

    image_file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # --- Помощники представления ---
    @property
    def price_major(self) -> float:
        return self.price / 100

    def price_display(self) -> str:
        major = self.price_major
        return f"{major:.0f}" if major.is_integer() else f"{major:.2f}"

    def title(self, lang: str) -> str:
        if lang == "ru" and self.title_ru:
            return self.title_ru
        return self.title_en or self.title_ru

    def description(self, lang: str) -> str:
        if lang == "ru" and self.description_ru:
            return self.description_ru
        return self.description_en or self.description_ru


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | expired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    plan: Mapped["Plan | None"] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.tg_id"))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)  # минимальные единицы
    currency: Mapped[str] = mapped_column(String(8), default="ILS")
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | paid | failed
    allpay_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["Plan | None"] = relationship()


class ReminderRule(Base):
    """Порог уведомления об окончании подписки (за N дней до конца).

    Порогов может быть несколько (например, 14, 7, 1). У каждого — свой текст,
    который админ задаёт вручную (подставляются {days} и {date})."""
    __tablename__ = "reminder_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    days_before: Mapped[int] = mapped_column(Integer, unique=True)
    text: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReminderLog(Base):
    """Факт отправки конкретного напоминания — защита от повторов.

    Уникальность по (subscription_id, days_before): каждый порог шлётся один раз
    на подписку. Продление создаёт новую подписку → пороги отработают заново."""
    __tablename__ = "reminder_logs"
    __table_args__ = (
        UniqueConstraint("subscription_id", "days_before", name="uq_reminder_once"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"))
    days_before: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
