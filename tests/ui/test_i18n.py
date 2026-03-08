from __future__ import annotations

import io

import pytest

import ui.i18n as i18n


@pytest.fixture(autouse=True)
def clear_i18n_caches_between_tests():
    i18n._load_catalog.cache_clear()
    i18n._get_catalog_for_resolved_language.cache_clear()
    yield
    i18n._load_catalog.cache_clear()
    i18n._get_catalog_for_resolved_language.cache_clear()


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


def test_text_returns_template_when_placeholder_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(i18n, "_get_catalog", lambda _language: {"greeting": "Hello {name}"})

    assert i18n.text("greeting", user="Kowalski") == "Hello {name}"


def test_text_returns_template_when_template_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(i18n, "_get_catalog", lambda _language: {"greeting": "Hello {name"})

    assert i18n.text("greeting", name="Kowalski") == "Hello {name"


def test_resolve_language_prefers_explicit_argument_over_environment(monkeypatch) -> None:
    monkeypatch.setenv("GAME_LANGUAGE", "pl")

    assert i18n._resolve_language(" EN ") == "en"


def test_load_catalog_filters_out_non_string_values(monkeypatch) -> None:
    sample_data = {
        "ok": "ready",
        "number": 123,
        "none_value": None,
        "nested": {"x": "y"},
    }

    class FakeFileContext:
        def __enter__(self):
            return io.StringIO("{}")

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    monkeypatch.setattr(i18n.Path, "open", lambda self, mode, encoding=None: FakeFileContext())
    monkeypatch.setattr(i18n.json, "load", lambda _file: sample_data)

    loaded = i18n._load_catalog("xx")

    assert loaded == {"ok": "ready"}


def test_get_catalog_raises_when_default_catalog_is_missing(monkeypatch) -> None:
    i18n._get_catalog_for_resolved_language.cache_clear()

    def always_missing(_language: str) -> dict[str, str]:
        raise FileNotFoundError("missing")

    monkeypatch.setattr(i18n, "_load_catalog", always_missing)

    with pytest.raises(FileNotFoundError, match="missing"):
        i18n._get_catalog("pl")
