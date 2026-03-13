from __future__ import annotations

from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
    UIEvent,
    UIEventIgnored,
)


def handle_main_menu_ui_event(event: UIEvent) -> DomainEvent:
    if isinstance(event, ExitRequested):
        return ExitFlowRouted()

    if isinstance(event, NewGameRequested):
        return NewGameFlowRouted()

    if isinstance(event, LoadGameRequested):
        return LoadGameFlowRouted()

    return UIEventIgnored()
