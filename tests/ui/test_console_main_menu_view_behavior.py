from __future__ import annotations

from dataclasses import dataclass

import pytest

import ui.console_main_menu_view as console_view_module
from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
)


@dataclass(frozen=True)
class UnknownDomainEvent(DomainEvent):
    pass


def _identity_text(key: str, **_: object) -> str:
    return key


def test_poll_ui_events_returns_event_for_valid_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = console_view_module.ConsoleMainMenuView()
    monkeypatch.setattr(console_view_module, "text", _identity_text)
    monkeypatch.setattr("builtins.input", lambda _prompt: " 2 ")

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], LoadGameRequested)


def test_poll_ui_events_returns_empty_and_prints_error_for_invalid_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = console_view_module.ConsoleMainMenuView()
    printed: list[str] = []
    monkeypatch.setattr(console_view_module, "text", _identity_text)
    monkeypatch.setattr("builtins.input", lambda _prompt: "x")
    monkeypatch.setattr("builtins.print", lambda message="": printed.append(str(message)))

    events = view.poll_ui_events()

    assert events == []
    assert printed == ["main_menu.error.invalid_choice_retry"]


def test_render_prints_menu_structure_without_translation_coupling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = console_view_module.ConsoleMainMenuView()
    printed: list[str] = []

    def fake_text(key: str, **kwargs: object) -> str:
        if key == "console.menu.option":
            return f"{kwargs['choice']}:{kwargs['label']}"
        return key

    monkeypatch.setattr(console_view_module, "text", fake_text)
    monkeypatch.setattr("builtins.print", lambda message="": printed.append(str(message)))

    view.render()

    assert "console.menu.header" in printed
    assert "1:main_menu.option.new_game" in printed
    assert "2:main_menu.option.load_game" in printed
    assert "3:main_menu.option.exit" in printed


@pytest.mark.parametrize(
    ("event", "expected_output"),
    [
        (NewGameFlowRouted(), "flow.new_game.stub"),
        (LoadGameFlowRouted(), "flow.load_game.stub"),
        (ExitFlowRouted(), "flow.exit"),
    ],
)
def test_handle_domain_event_prints_message_for_supported_events(
    event: DomainEvent,
    expected_output: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = console_view_module.ConsoleMainMenuView()
    printed: list[str] = []
    monkeypatch.setattr(console_view_module, "text", _identity_text)
    monkeypatch.setattr("builtins.print", lambda message="": printed.append(str(message)))

    view.handle_domain_event(event)

    assert printed == [expected_output]


def test_handle_domain_event_ignores_unknown_event(monkeypatch: pytest.MonkeyPatch) -> None:
    view = console_view_module.ConsoleMainMenuView()
    printed: list[str] = []
    monkeypatch.setattr(console_view_module, "text", _identity_text)
    monkeypatch.setattr("builtins.print", lambda message="": printed.append(str(message)))

    view.handle_domain_event(UnknownDomainEvent())

    assert printed == []


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ("1", NewGameRequested),
        ("2", LoadGameRequested),
        ("3", ExitRequested),
    ],
)
def test_map_choice_to_order_alias_matches_current_mapper(raw: str, expected_type: type) -> None:
    event = console_view_module.map_choice_to_order(raw)

    assert isinstance(event, expected_type)
