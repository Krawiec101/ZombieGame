from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import app as app_module
from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    UIEvent,
    UIEventIgnored,
)


@dataclass(frozen=True)
class UnknownUIEvent(UIEvent):
    pass


class FakeView:
    def __init__(self, batches: list[list[UIEvent]]) -> None:
        self._batches = list(batches)
        self.handled_domain_events: list[DomainEvent] = []
        self.render_calls = 0
        self.poll_calls = 0
        self.close_calls = 0

    def render(self) -> None:
        self.render_calls += 1

    def poll_ui_events(self) -> list[UIEvent]:
        self.poll_calls += 1
        if self._batches:
            return self._batches.pop(0)
        raise RuntimeError("FakeView exhausted planned event batches.")

    def handle_domain_event(self, event: DomainEvent) -> None:
        self.handled_domain_events.append(event)

    def close(self) -> None:
        self.close_calls += 1


def test_route_domain_event_exit_stops_loop() -> None:
    assert app_module.route_domain_event(ExitFlowRouted()) is False


def test_route_domain_event_new_game_stops_loop() -> None:
    assert app_module.route_domain_event(NewGameFlowRouted()) is False


def test_route_domain_event_load_game_stops_loop() -> None:
    assert app_module.route_domain_event(LoadGameFlowRouted()) is False


def test_route_domain_event_ignored_keeps_loop_running() -> None:
    assert app_module.route_domain_event(UIEventIgnored()) is True


def test_run_creates_view_and_delegates_to_main_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([])
    called: dict[str, FakeView] = {}

    monkeypatch.setattr(app_module, "create_view", lambda: view)

    def fake_loop(received_view: FakeView) -> None:
        called["view"] = received_view

    monkeypatch.setattr(app_module, "_run_main_menu_loop", fake_loop)

    app_module.run()

    assert called["view"] is view


def test_run_main_menu_loop_stops_after_exit_event() -> None:
    view = FakeView([[ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 1
    assert view.poll_calls == 1
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], ExitFlowRouted)


def test_run_main_menu_loop_repeats_when_no_events_then_stops() -> None:
    view = FakeView([[], [LoadGameRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 2
    assert view.poll_calls == 2
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], LoadGameFlowRouted)


def test_run_main_menu_loop_routes_unknown_then_stops_after_next_batch() -> None:
    view = FakeView([[UnknownUIEvent()], [ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 2
    assert view.poll_calls == 2
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], UIEventIgnored)
    assert isinstance(view.handled_domain_events[1], ExitFlowRouted)


def test_run_main_menu_loop_closes_view_when_core_handler_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([[UnknownUIEvent()]])

    def raising_handler(_event: UIEvent) -> DomainEvent:
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "handle_main_menu_ui_event", raising_handler)

    with pytest.raises(RuntimeError, match="boom"):
        app_module._run_main_menu_loop(view)

    assert view.close_calls == 1


def test_run_main_menu_loop_stops_processing_remaining_events_in_same_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownUIEvent()
    second = UnknownUIEvent()
    view = FakeView([[first, second]])
    seen: list[DomainEvent] = []

    def fake_route_domain_event(event: DomainEvent) -> bool:
        seen.append(event)
        return False

    monkeypatch.setattr(app_module, "route_domain_event", fake_route_domain_event)

    app_module._run_main_menu_loop(view)

    assert len(seen) == 1
    assert isinstance(seen[0], UIEventIgnored)
    assert len(view.handled_domain_events) == 1
    assert view.render_calls == 1
    assert view.poll_calls == 1
    assert view.close_calls == 1


def test_run_main_menu_loop_only_calls_route_until_first_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownUIEvent()
    second = UnknownUIEvent()
    view = FakeView([[first, second]])
    call_count = 0

    def fake_route_domain_event(_event: DomainEvent) -> bool:
        nonlocal call_count
        call_count += 1
        return False if call_count == 1 else True

    monkeypatch.setattr(app_module, "route_domain_event", fake_route_domain_event)

    app_module._run_main_menu_loop(view)

    assert call_count == 1


def test_run_main_menu_loop_processes_until_false_when_false_is_not_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownUIEvent()
    second = UnknownUIEvent()
    third = UnknownUIEvent()
    view = FakeView([[first, second, third]])
    call_count = 0

    def fake_route_domain_event(_event: DomainEvent) -> bool:
        nonlocal call_count
        call_count += 1
        return call_count < 2

    monkeypatch.setattr(app_module, "route_domain_event", fake_route_domain_event)

    app_module._run_main_menu_loop(view)

    assert call_count == 2
    assert len(view.handled_domain_events) == 2
