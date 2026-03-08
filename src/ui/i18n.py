from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

_LOCALE_ENV_VAR = "GAME_LANGUAGE"
_DEFAULT_LANGUAGE = "pl"
_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def _resolve_language(language: str | None) -> str:
    if language and language.strip():
        return language.strip().lower()

    from_env = os.getenv(_LOCALE_ENV_VAR, "").strip().lower()
    return from_env or _DEFAULT_LANGUAGE


@lru_cache(maxsize=8)
def _load_catalog(language: str) -> dict[str, str]:
    catalog_path = _LOCALES_DIR / f"{language}.json"
    with catalog_path.open("r", encoding="utf-8") as file:
        raw_data = json.load(file)

    if not isinstance(raw_data, dict):
        raise ValueError(f"Locale catalog must be an object: {catalog_path}")

    catalog: dict[str, str] = {}
    for key, value in raw_data.items():
        if isinstance(key, str) and isinstance(value, str):
            catalog[key] = value
    return catalog


def _get_catalog(language: str | None) -> Mapping[str, str]:
    resolved_language = _resolve_language(language)
    return _get_catalog_for_resolved_language(resolved_language)


@lru_cache(maxsize=8)
def _get_catalog_for_resolved_language(resolved_language: str) -> Mapping[str, str]:
    try:
        return _load_catalog(resolved_language)
    except FileNotFoundError:
        if resolved_language == _DEFAULT_LANGUAGE:
            raise
        return _load_catalog(_DEFAULT_LANGUAGE)


def text(key: str, *, language: str | None = None, **placeholders: Any) -> str:
    template = _get_catalog(language).get(key, f"[{key}]")
    if not placeholders:
        return template

    try:
        return template.format(**placeholders)
    except (KeyError, ValueError):
        return template
