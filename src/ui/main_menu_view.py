from __future__ import annotations

from typing import Protocol

from src.core.orders import Order


class MainMenuView(Protocol):
    def render(self) -> None:
        ...

    def poll_orders(self) -> list[Order]:
        ...

    def close(self) -> None:
        ...
