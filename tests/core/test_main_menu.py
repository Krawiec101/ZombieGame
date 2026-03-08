from __future__ import annotations

from dataclasses import dataclass

import pytest

from contracts.events import (
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
    UIEvent,
    UIEventIgnored,
)
from core.main_menu import handle_main_menu_ui_event


@dataclass(frozen=True)
class UnknownUIEvent(UIEvent):
    pass


@pytest.mark.parametrize(
    ("ui_event", "expected_domain_event_type"),
    [
        (ExitRequested(), ExitFlowRouted),
        (NewGameRequested(), NewGameFlowRouted),
        (LoadGameRequested(), LoadGameFlowRouted),
    ],
)
def test_handle_main_menu_ui_event_routes_supported_events(
    ui_event: UIEvent,
    expected_domain_event_type: type,
) -> None:
    domain_event = handle_main_menu_ui_event(ui_event)

    assert isinstance(domain_event, expected_domain_event_type)


def test_handle_main_menu_ui_event_ignores_unknown_events() -> None:
    domain_event = handle_main_menu_ui_event(UnknownUIEvent())

    assert isinstance(domain_event, UIEventIgnored)
