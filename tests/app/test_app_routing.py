from __future__ import annotations

from dataclasses import dataclass

import pytest

import app.application_loop as application_loop_module
from app import app as app_module
import app.ui_event_handler as ui_event_handler_module
from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    GameFrameSyncRequested,
    GameLeftClickRequested,
    GameRightClickRequested,
    GameSupplyRouteRequested,
    GameStateSynced,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
    UIEvent,
    UIEventIgnored,
)
from contracts.game_state import (
    GameStateSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    UnitSnapshot,
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


class FakeGameSession:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.update_calls: list[tuple[int, int]] = []
        self.tick_calls = 0
        self.left_clicks: list[tuple[int, int]] = []
        self.right_clicks: list[tuple[int, int]] = []
        self.supply_routes: list[tuple[str, str]] = []

    def reset(self) -> None:
        self.reset_calls += 1

    def update_map_dimensions(self, *, width: int, height: int) -> None:
        self.update_calls.append((width, height))

    def tick(self) -> None:
        self.tick_calls += 1

    def sync_state(self, *, width: int, height: int) -> GameStateSnapshot:
        self.update_map_dimensions(width=width, height=height)
        self.tick()
        return GameStateSnapshot(
            map_objects=(MapObjectSnapshot(object_id="hq", bounds=(1, 2, 3, 4)),),
            units=(
                UnitSnapshot(
                    unit_id="u1",
                    unit_type_id="infantry_squad",
                    position=(5.0, 6.0),
                    target=None,
                    marker_size_px=18,
                ),
            ),
            selected_unit_id="u1",
            objective_definitions=(
                MissionObjectiveDefinitionSnapshot(
                    objective_id="o1",
                    description_key="objective.o1",
                ),
            ),
            objective_progress=(
                MissionObjectiveProgressSnapshot(objective_id="o1", completed=False),
            ),
        )

    def handle_left_click(self, position: tuple[int, int]) -> None:
        self.left_clicks.append(position)

    def handle_right_click(self, _position: tuple[int, int]) -> None:
        self.right_clicks.append(_position)

    def handle_supply_route(self, *, source_object_id: str, destination_object_id: str) -> None:
        self.supply_routes.append((source_object_id, destination_object_id))

    def map_objects_snapshot(self) -> list[dict[str, object]]:
        return [{"id": "hq", "bounds": (1, 2, 3, 4)}]

    def units_snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "unit_id": "u1",
                "unit_type_id": "infantry_squad",
                "position": (5.0, 6.0),
                "target": None,
                "marker_size_px": 18,
            }
        ]

    def selected_unit_id(self) -> str | None:
        return "u1"

    def objective_definitions_snapshot(self) -> tuple[dict[str, str], ...]:
        return ({"objective_id": "o1", "description_key": "objective.o1"},)

    def objective_status_snapshot(self) -> dict[str, bool]:
        return {"o1": False}


class FalseyGameSession(FakeGameSession):
    def __bool__(self) -> bool:
        return False


def test_route_domain_event_exit_stops_loop() -> None:
    assert app_module.route_domain_event(ExitFlowRouted()) is False


def test_route_domain_event_new_game_keeps_loop_running() -> None:
    assert app_module.route_domain_event(NewGameFlowRouted()) is True


def test_route_domain_event_load_game_keeps_loop_running() -> None:
    assert app_module.route_domain_event(LoadGameFlowRouted()) is True


def test_route_domain_event_ignored_keeps_loop_running() -> None:
    assert app_module.route_domain_event(UIEventIgnored()) is True


def test_handle_ui_event_new_game_resets_game_session() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(NewGameRequested(), game_session=session)

    assert session.reset_calls == 1
    assert len(domain_events) == 1
    assert isinstance(domain_events[0], NewGameFlowRouted)


def test_handle_ui_event_game_frame_sync_updates_session_and_emits_snapshot() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(
        GameFrameSyncRequested(width=1280, height=720),
        game_session=session,
    )

    assert session.update_calls == [(1280, 720)]
    assert session.tick_calls == 1
    assert len(domain_events) == 1
    assert isinstance(domain_events[0], GameStateSynced)
    assert domain_events[0].snapshot.units == (
        UnitSnapshot(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(5.0, 6.0),
            target=None,
            marker_size_px=18,
        ),
    )
    assert domain_events[0].snapshot.objective_definitions == (
        MissionObjectiveDefinitionSnapshot(
            objective_id="o1",
            description_key="objective.o1",
        ),
    )


def test_handle_ui_event_game_left_click_delegates_without_domain_event() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(
        GameLeftClickRequested(position=(320, 220)),
        game_session=session,
    )

    assert session.left_clicks == [(320, 220)]
    assert domain_events == ()


def test_handle_ui_event_game_right_click_delegates_without_domain_event() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(
        GameRightClickRequested(position=(420, 300)),
        game_session=session,
    )

    assert session.right_clicks == [(420, 300)]
    assert domain_events == ()


def test_handle_ui_event_supply_route_delegates_without_domain_event() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(
        GameSupplyRouteRequested(source_object_id="landing_pad", destination_object_id="hq"),
        game_session=session,
    )

    assert session.supply_routes == [("landing_pad", "hq")]
    assert domain_events == ()


def test_handle_ui_event_unknown_returns_ui_event_ignored_without_reset() -> None:
    session = FakeGameSession()

    domain_events = app_module.handle_ui_event(UnknownUIEvent(), game_session=session)

    assert session.reset_calls == 0
    assert len(domain_events) == 1
    assert isinstance(domain_events[0], UIEventIgnored)


def test_sync_game_state_builds_snapshot_from_game_session() -> None:
    session = FakeGameSession()

    domain_event = app_module._sync_game_state(session, width=640, height=480)

    assert session.update_calls == [(640, 480)]
    assert session.tick_calls == 1
    assert isinstance(domain_event, GameStateSynced)
    assert domain_event.snapshot.map_objects == (
        MapObjectSnapshot(object_id="hq", bounds=(1, 2, 3, 4)),
    )
    assert domain_event.snapshot.selected_unit_id == "u1"
    assert domain_event.snapshot.objective_progress == (
        MissionObjectiveProgressSnapshot(objective_id="o1", completed=False),
    )


def test_run_creates_view_and_delegates_to_main_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([])
    called: dict[str, FakeView] = {}

    monkeypatch.setattr(app_module, "create_view", lambda **_kwargs: view)

    def fake_loop(received_view: FakeView, _game_session: object) -> None:
        called["view"] = received_view

    monkeypatch.setattr(app_module, "_run_main_menu_loop", fake_loop)

    app_module.run()

    assert called["view"] is view


def test_run_passes_created_game_session_to_main_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    view = FakeView([])
    created_game_session = FakeGameSession()
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_module, "create_view", lambda: view)
    monkeypatch.setattr(app_module, "create_default_game_session", lambda: created_game_session)

    def fake_loop(received_view: FakeView, received_game_session: object) -> None:
        captured["view"] = received_view
        captured["game_session"] = received_game_session

    monkeypatch.setattr(app_module, "_run_main_menu_loop", fake_loop)

    app_module.run()

    assert captured["view"] is view
    assert captured["game_session"] is created_game_session


def test_run_main_menu_loop_stops_after_exit_event() -> None:
    view = FakeView([[ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 1
    assert view.poll_calls == 1
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], ExitFlowRouted)


def test_run_main_menu_loop_uses_provided_game_session_for_ui_event_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = FakeView([[UnknownUIEvent()]])
    provided_game_session = FakeGameSession()

    def fake_handle_ui_event(_event: UIEvent, *, game_session: object) -> tuple[DomainEvent, ...]:
        assert game_session is provided_game_session
        return (ExitFlowRouted(),)

    monkeypatch.setattr(app_module, "handle_ui_event", fake_handle_ui_event)

    app_module._run_main_menu_loop(view, provided_game_session)

    assert view.close_calls == 1


def test_run_main_menu_loop_creates_default_game_session_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = FakeView([[UnknownUIEvent()]])
    created_game_session = FakeGameSession()

    monkeypatch.setattr(app_module, "create_default_game_session", lambda: created_game_session)

    def fake_handle_ui_event(_event: UIEvent, *, game_session: object) -> tuple[DomainEvent, ...]:
        assert game_session is created_game_session
        return (ExitFlowRouted(),)

    monkeypatch.setattr(app_module, "handle_ui_event", fake_handle_ui_event)

    app_module._run_main_menu_loop(view)

    assert view.close_calls == 1


def test_run_main_menu_loop_uses_falsey_provided_session_instead_of_creating_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = FakeView([[UnknownUIEvent()]])
    provided_falsey_session = FalseyGameSession()
    created: list[bool] = []

    def fake_create_default_game_session() -> FakeGameSession:
        created.append(True)
        return FakeGameSession()

    def fake_handle_ui_event(_event: UIEvent, *, game_session: object) -> tuple[DomainEvent, ...]:
        assert game_session is provided_falsey_session
        return (ExitFlowRouted(),)

    monkeypatch.setattr(app_module, "create_default_game_session", fake_create_default_game_session)
    monkeypatch.setattr(app_module, "handle_ui_event", fake_handle_ui_event)

    app_module._run_main_menu_loop(view, provided_falsey_session)

    assert created == []


def test_run_main_menu_loop_repeats_when_load_game_is_stubbed_then_stops_on_exit() -> None:
    view = FakeView([[], [LoadGameRequested()], [ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 3
    assert view.poll_calls == 3
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], LoadGameFlowRouted)
    assert isinstance(view.handled_domain_events[1], ExitFlowRouted)


def test_run_main_menu_loop_continues_after_new_game_until_exit() -> None:
    view = FakeView([[NewGameRequested()], [ExitRequested()]])

    app_module._run_main_menu_loop(view)

    assert view.render_calls == 2
    assert view.poll_calls == 2
    assert view.close_calls == 1
    assert isinstance(view.handled_domain_events[0], NewGameFlowRouted)
    assert isinstance(view.handled_domain_events[1], ExitFlowRouted)


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

    monkeypatch.setattr(ui_event_handler_module, "handle_main_menu_ui_event", raising_handler)

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


def test_run_main_menu_loop_continues_when_ui_event_maps_to_no_domain_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UnknownUIEvent()
    second = UnknownUIEvent()
    view = FakeView([[first], [second]])
    calls = 0

    def fake_handle_ui_event(_event: UIEvent, *, game_session: object) -> tuple[DomainEvent, ...]:
        nonlocal calls
        calls += 1
        _ = game_session
        if calls == 1:
            return ()
        return (ExitFlowRouted(),)

    monkeypatch.setattr(app_module, "handle_ui_event", fake_handle_ui_event)

    app_module._run_main_menu_loop(view, FakeGameSession())

    assert calls == 2
    assert view.render_calls == 2
    assert view.poll_calls == 2
    assert len(view.handled_domain_events) == 1
    assert isinstance(view.handled_domain_events[0], ExitFlowRouted)


def test_application_loop_stops_without_processing_next_ui_event_in_same_batch() -> None:
    first = UnknownUIEvent()
    second = UnknownUIEvent()
    view = FakeView([[first, second]])
    handled_ui_events: list[UIEvent] = []

    def fake_handle_ui_event(event: UIEvent, _game_session: FakeGameSession) -> tuple[DomainEvent, ...]:
        handled_ui_events.append(event)
        return (ExitFlowRouted(),)

    application_loop_module.run_main_menu_loop(
        view,
        game_session=FakeGameSession(),
        create_default_game_session=FakeGameSession,
        handle_ui_event=fake_handle_ui_event,
        route_domain_event=lambda _event: False,
    )

    assert handled_ui_events == [first]
    assert len(view.handled_domain_events) == 1
    assert isinstance(view.handled_domain_events[0], ExitFlowRouted)


def test_application_loop_processes_multiple_domain_events_until_router_returns_false() -> None:
    ui_event = UnknownUIEvent()
    view = FakeView([[ui_event]])
    routed_events: list[DomainEvent] = []

    def fake_handle_ui_event(_event: UIEvent, _game_session: FakeGameSession) -> tuple[DomainEvent, ...]:
        return (NewGameFlowRouted(), ExitFlowRouted())

    def fake_route_domain_event(event: DomainEvent) -> bool:
        routed_events.append(event)
        return not isinstance(event, ExitFlowRouted)

    application_loop_module.run_main_menu_loop(
        view,
        game_session=FakeGameSession(),
        create_default_game_session=FakeGameSession,
        handle_ui_event=fake_handle_ui_event,
        route_domain_event=fake_route_domain_event,
    )

    assert routed_events == [NewGameFlowRouted(), ExitFlowRouted()]
    assert [type(event) for event in view.handled_domain_events] == [NewGameFlowRouted, ExitFlowRouted]
    assert view.render_calls == 1
    assert view.poll_calls == 1
