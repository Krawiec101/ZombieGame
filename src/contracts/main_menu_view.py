from __future__ import annotations

from typing import Protocol

try:
    from contracts.events import DomainEvent, UIEvent
except ModuleNotFoundError:
    from src.contracts.events import DomainEvent, UIEvent


class MainMenuView(Protocol):
    def render(self) -> None:
        ...

    def poll_ui_events(self) -> list[UIEvent]:
        ...

    def handle_domain_event(self, event: DomainEvent) -> None:
        ...

    def close(self) -> None:
        ...
