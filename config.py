"""Конфигурация приложения: читает переменные окружения из .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    support_contact: str
    allpay_login: str
    allpay_key: str
    webhook_base_url: str
    port: int
    database_url: str
    default_currency: str
    reminder_check_interval: int

    # Путь webhook AllPay внутри aiohttp-приложения
    allpay_webhook_path: str = "/allpay/webhook"

    @property
    def allpay_webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.allpay_webhook_path}"

    @property
    def allpay_success_url(self) -> str:
        # Куда AllPay вернёт пользователя после оплаты
        return f"{self.webhook_base_url.rstrip('/')}/allpay/success"


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан. Заполните .env по образцу .env.example")

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL не задан. Укажите строку подключения к PostgreSQL")
    # Нормализуем драйвер под asyncpg, если провайдер дал «сырой» postgres URL
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgres://"):]
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]

    return Config(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        support_contact=os.getenv("SUPPORT_CONTACT", "@admin").strip(),
        allpay_login=os.getenv("ALLPAY_LOGIN", "").strip(),
        allpay_key=os.getenv("ALLPAY_KEY", "").strip(),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", "http://localhost").strip(),
        port=int(os.getenv("PORT", "8080")),
        database_url=database_url,
        default_currency=os.getenv("DEFAULT_CURRENCY", "ILS").strip().upper(),
        reminder_check_interval=int(os.getenv("REMINDER_CHECK_INTERVAL", "3600")),
    )
