"""Мелкие утилиты."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_TZ_RE = re.compile(r"^UTC([+-])(\d{1,2})$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_tz_offset(tz: str) -> timezone:
    """Преобразует строку вида ``UTC+3`` / ``UTC-5`` / ``UTC`` в объект timezone."""
    if not tz or tz.upper() == "UTC":
        return timezone.utc
    m = _TZ_RE.match(tz.strip())
    if not m:
        return timezone.utc
    sign, hours = m.group(1), int(m.group(2))
    delta = timedelta(hours=hours if sign == "+" else -hours)
    return timezone(delta)


def is_valid_tz(tz: str) -> bool:
    return tz.upper() == "UTC" or bool(_TZ_RE.match(tz.strip()))


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def format_dt(dt: datetime, tz: str) -> str:
    """Форматирует datetime в часовом поясе пользователя."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(parse_tz_offset(tz))
    return local.strftime("%d.%m.%Y %H:%M")
