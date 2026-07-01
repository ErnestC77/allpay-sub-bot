"""Простой загрузчик переводов.

Тексты хранятся в JSON-файлах в каталоге ``locales/`` (один файл на язык).
``t(key, lang)`` возвращает строку с фолбэком: выбранный язык → en → ru → сам ключ.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCALES_DIR = Path(__file__).parent / "locales"

DEFAULT_LANG = "ru"
FALLBACK_LANG = "en"

# Порядок и оформление кнопок выбора языка (сетка 2×7, как на скриншоте).
# (код, родное название, флаг-эмодзи)
LANGUAGES: list[tuple[str, str, str]] = [
    ("ru", "Русский", "🇷🇺"),
    ("en", "English", "🇺🇸"),
    ("uk", "Українська", "🇺🇦"),
    ("it", "Italiano", "🇮🇹"),
    ("de", "Deutsch", "🇩🇪"),
    ("es", "Español", "🇪🇸"),
    ("pl", "Polski", "🇵🇱"),
    ("ro", "Română", "🇷🇴"),
    ("fr", "Français", "🇫🇷"),
    ("tg", "Тоҷикӣ", "🇹🇯"),
    ("az", "Azərbaycan", "🇦🇿"),
    ("tr", "Türkçe", "🇹🇷"),
    ("kk", "Қазақша", "🇰🇿"),
    ("uz", "Oʻzbekcha", "🇺🇿"),
]

SUPPORTED_LANGS = {code for code, _, _ in LANGUAGES}

_translations: dict[str, dict[str, str]] = {}


def _load() -> None:
    """Читает все JSON-файлы переводов в память (вызывается один раз при импорте)."""
    for path in LOCALES_DIR.glob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                _translations[path.stem] = json.load(f)
        except (json.JSONDecodeError, OSError):
            _translations[path.stem] = {}


def lang_name(code: str) -> str:
    for c, name, flag in LANGUAGES:
        if c == code:
            return f"{flag} {name}"
    return code


def normalize_lang(code: str | None) -> str:
    if code and code in SUPPORTED_LANGS:
        return code
    return DEFAULT_LANG


def t(key: str, lang: str | None = None, /, **kwargs) -> str:
    """Возвращает перевод ``key`` для языка ``lang`` с подстановкой ``kwargs``."""
    lang = normalize_lang(lang)
    for candidate in (lang, FALLBACK_LANG, DEFAULT_LANG):
        table = _translations.get(candidate)
        if table and key in table:
            value = table[key]
            break
    else:
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value


_load()
