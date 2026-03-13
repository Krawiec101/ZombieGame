from __future__ import annotations

from typing import Protocol

from contracts.events import DomainEvent, UIEvent


class MainMenuView(Protocol):
    def render(self) -> None:
        ...

    def poll_ui_events(self) -> list[UIEvent]:
        ...

    def handle_domain_event(self, event: DomainEvent) -> None:
        ...

    def close(self) -> None:
        ...
