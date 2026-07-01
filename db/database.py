"""Инициализация async-движка SQLAlchemy и сессий."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base, Plan, ReminderRule

_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    global _engine, _sessionmaker
    _engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("init_engine() должен быть вызван до обращения к БД")
    return _sessionmaker


# Тарифы по умолчанию (создаются при первом запуске, дальше правятся в админке).
# price — в минимальных единицах (агорот); цены-заглушки, замените под свой прайс.
_DEFAULT_PLANS = [
    dict(duration_days=30, price=3900, title_ru="Подписка на месяц",
         title_en="Monthly plan", sort_order=1),
    dict(duration_days=60, price=6900, title_ru="Подписка на 2 месяца",
         title_en="2-month plan", sort_order=2),
    dict(duration_days=90, price=8900, title_ru="Подписка на 3 месяца",
         title_en="3-month plan", sort_order=3),
]


# Лёгкие миграции для уже существующих таблиц (Postgres). На свежей SQLite колонки
# создаёт create_all, а эти ALTER просто молча отваливаются (обёрнуты в try).
_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_renew BOOLEAN DEFAULT FALSE",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS allpay_token VARCHAR(128)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS card_mask VARCHAR(32)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_plan_id INTEGER",
]


async def init_db(default_currency: str = "ILS") -> None:
    """Создаёт таблицы, применяет миграции и наполняет данные по умолчанию."""
    assert _engine is not None
    from sqlalchemy import text

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    for stmt in _MIGRATIONS:
        try:
            async with _engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:  # noqa: BLE001 — колонка уже есть или SQLite-синтаксис
            pass

    from sqlalchemy import select

    async with get_sessionmaker()() as session:
        existing = await session.scalar(select(Plan).limit(1))
        if existing is None:
            for data in _DEFAULT_PLANS:
                session.add(Plan(currency=default_currency, is_active=True, **data))
            await session.commit()

        # Порог уведомления по умолчанию: за 14 дней (за две недели).
        has_rule = await session.scalar(select(ReminderRule).limit(1))
        if has_rule is None:
            session.add(ReminderRule(
                days_before=14,
                is_active=True,
                text=("⏳ Ваша подписка заканчивается через {days} дн. "
                      "(до {date}).\nПродлите её, чтобы не потерять доступ."),
            ))
            await session.commit()
