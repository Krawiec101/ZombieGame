from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import app as app_module
from core.orders import ExitRequested, LoadGameRequested, NewGameRequested, Order


@dataclass(frozen=True)
class UnknownOrder(Order):
    pass


class FakeView:
    def __init__(self, batches: list[list[Order]]) -> None:
        self._batches = list(batches)
        self.render_calls = 0
        self.poll_calls = 0
        self.close_calls = 0

    def render(self) -> None:
        self.render_calls += 1

    def poll_orders(self) -> list[Order]:
        self.poll_calls += 1
        if self._batches:
            return self._batches.pop(0)
        raise RuntimeError("FakeView exhausted planned order batches.")

    def close(self) -> None:
        self.close_calls += 1


def test_route_order_exit_requested_stops_loop(capsys: pytest.CaptureFixture[str]) -> None:
    assert app_module.route_order(ExitRequested()) is False
    assert capsys.readouterr().out == ""


def test_route_order_new_game_requested_stops_menu_and_prints(capsys: pytest.CaptureFixture[str]) -> None:
    assert app_module.route_order(NewGameRequested()) is False
    assert capsys.readouterr().out.strip() == "Wybrano: Nowa gra"


def test_route_order_load_game_requested_stops_menu_and_prints(capsys: pytest.CaptureFixture[str]) -> None:
    assert app_module.route_order(LoadGameRequested()) is False
    assert capsys.readouterr().out.strip() == "Wybrano: Wczytaj"


def test_route_order_unknown_keeps_loop_running(capsys: pytest.CaptureFixture[str]) -> None:
    assert app_module.route_order(UnknownOrder()) is True
    assert capsys.readouterr().out == ""


def test_run_creates_view_and_delegates_to_main_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([])
    called: dict[str, FakeView] = {}

    monkeypatch.setattr(app_module, "create_view", lambda: view)

    def fake_loop(received_view: FakeView) -> None:
        called["view"] = received_view

    monkeypatch.setattr(app_module, "_run_main_menu_loop", fake_loop)

    app_module.run()

    assert called["view"] is view


def test_run_main_menu_loop_stops_after_exit_order() -> None:
    view = FakeView([[ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 1
    assert view.poll_calls == 1
    assert view.close_calls == 1


def test_run_main_menu_loop_repeats_when_no_orders_then_stops() -> None:
    view = FakeView([[], [LoadGameRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 2
    assert view.poll_calls == 2
    assert view.close_calls == 1


def test_run_main_menu_loop_closes_view_when_route_order_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([[NewGameRequested()]])

    def raising_route_order(_order: Order) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "route_order", raising_route_order)

    with pytest.raises(RuntimeError, match="boom"):
        app_module._run_main_menu_loop(view)

    assert view.close_calls == 1


def test_run_main_menu_loop_stops_processing_remaining_orders_in_same_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownOrder()
    second = UnknownOrder()
    view = FakeView([[first, second]])
    seen: list[Order] = []

    def fake_route_order(order: Order) -> bool:
        seen.append(order)
        return False

    monkeypatch.setattr(app_module, "route_order", fake_route_order)

    app_module._run_main_menu_loop(view)

    assert seen == [first]
    assert view.render_calls == 1
    assert view.poll_calls == 1
    assert view.close_calls == 1


def test_run_main_menu_loop_only_calls_route_order_until_first_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownOrder()
    second = UnknownOrder()
    view = FakeView([[first, second]])
    call_count = 0

    def fake_route_order(_order: Order) -> bool:
        nonlocal call_count
        call_count += 1
        return False if call_count == 1 else True

    monkeypatch.setattr(app_module, "route_order", fake_route_order)

    app_module._run_main_menu_loop(view)

    assert call_count == 1


def test_run_main_menu_loop_processes_until_false_when_false_is_not_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownOrder()
    second = UnknownOrder()
    third = UnknownOrder()
    view = FakeView([[first, second, third]])
    seen: list[Order] = []

    def fake_route_order(order: Order) -> bool:
        seen.append(order)
        return order is not second

    monkeypatch.setattr(app_module, "route_order", fake_route_order)

    app_module._run_main_menu_loop(view)

    assert seen == [first, second]
