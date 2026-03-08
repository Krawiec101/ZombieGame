from __future__ import annotations

import ui.i18n as i18n


def test_text_uses_default_locale_when_env_not_set(monkeypatch) -> None:
    monkeypatch.delenv("GAME_LANGUAGE", raising=False)

    assert i18n.text("main_menu.title") == "MENU GLOWNE"


def test_text_formats_placeholders_from_json() -> None:
    assert i18n.text("game.character.label", character_name="Kowalski") == "Postac: Kowalski"


def test_text_falls_back_to_default_locale_for_unknown_language(monkeypatch) -> None:
    monkeypatch.setenv("GAME_LANGUAGE", "xx")

    assert i18n.text("main_menu.option.new_game") == "Nowa gra"


def test_text_caches_fallback_catalog_for_unknown_language(monkeypatch) -> None:
    monkeypatch.setenv("GAME_LANGUAGE", "xx")
    i18n._load_catalog.cache_clear()
    i18n._get_catalog_for_resolved_language.cache_clear()

    calls: list[str] = []
    original_load_catalog = i18n._load_catalog

    def tracking_load_catalog(language: str) -> dict[str, str]:
        calls.append(language)
        return original_load_catalog(language)

    monkeypatch.setattr(i18n, "_load_catalog", tracking_load_catalog)

    assert i18n.text("main_menu.option.new_game") == "Nowa gra"
    assert i18n.text("main_menu.option.load_game") == "Wczytaj"
    assert calls == ["xx", "pl"]


def test_text_returns_bracketed_key_when_translation_is_missing() -> None:
    assert i18n.text("missing.key") == "[missing.key]"
