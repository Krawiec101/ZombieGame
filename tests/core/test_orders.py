from __future__ import annotations

from contracts.events import UIEvent
from core import orders


def test_order_alias_points_to_ui_event() -> None:
    assert orders.Order is UIEvent


def test_orders_module_exports_expected_symbols() -> None:
    assert set(orders.__all__) == {"Order", "NewGameRequested", "LoadGameRequested", "ExitRequested"}


def test_reexported_events_are_ui_events() -> None:
    assert isinstance(orders.NewGameRequested(), UIEvent)
    assert isinstance(orders.LoadGameRequested(), UIEvent)
    assert isinstance(orders.ExitRequested(), UIEvent)
