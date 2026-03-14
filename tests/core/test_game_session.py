from __future__ import annotations

import math

from contracts.game_state import (
    BaseSnapshot,
    GameStateSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MissionObjectiveProgressSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
)
from core.game_session import (
    SUPPLY_TRANSPORT_TYPE_SPECS,
    BaseState,
    UNIT_TYPE_SPECS,
    LandingPadState,
    SupplyRouteState,
    SupplyTransportState,
    UnitState,
    create_default_game_session,
)


def _unit_by_id(units: list[dict[str, object]], unit_id: str) -> dict[str, object]:
    return next(unit for unit in units if unit["unit_id"] == unit_id)


def _unit_center(unit: dict[str, object]) -> tuple[int, int]:
    x, y = unit["position"]
    return (int(float(x)), int(float(y)))


class _FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.current = start

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def _landing_pad_snapshot(session) -> LandingPadSnapshot:
    return session.landing_pads_snapshot()[0]


def test_game_session_initializes_map_objects_and_units() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    map_object_ids = {obj["id"] for obj in session.map_objects_snapshot()}
    unit_type_ids = {unit["unit_type_id"] for unit in session.units_snapshot()}
    assert map_object_ids == {"hq", "landing_pad"}
    assert unit_type_ids == {"infantry_squad", "mechanized_squad"}


def test_snapshot_exposes_typed_contract_for_ui_sync() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    snapshot = session.snapshot()

    assert isinstance(snapshot, GameStateSnapshot)
    assert {map_object.object_id for map_object in snapshot.map_objects} == {"hq", "landing_pad"}
    assert {unit.unit_type_id for unit in snapshot.units} == {
        "infantry_squad",
        "mechanized_squad",
    }
    assert snapshot.objective_progress == (
        MissionObjectiveProgressSnapshot(
            objective_id="motorized_to_landing_pad",
            completed=False,
        ),
    )
    assert snapshot.landing_pads == (
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="small",
            is_secured=False,
            capacity=90,
            total_stored=0,
            next_transport_seconds=None,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=session.snapshot().landing_pads[0].resources,
        ),
    )
    assert snapshot.bases == (
        BaseSnapshot(
            object_id="hq",
            capacity=120,
            total_stored=0,
            resources=session.snapshot().bases[0].resources,
        ),
    )
    assert snapshot.supply_transports == ()
    assert snapshot.supply_routes == ()
    assert snapshot.selected_unit_id is None
    assert snapshot.objective_definitions == (
        session.snapshot().objective_definitions[0].__class__(
            objective_id="motorized_to_landing_pad",
            description_key="mission.objective.motorized_to_landing_pad",
        ),
    )


def test_snapshot_includes_selected_unit_and_pending_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    snapshot = session.snapshot()

    assert snapshot.selected_unit_id == "alpha_infantry"
    alpha = next(unit for unit in snapshot.units if unit.unit_id == "alpha_infantry")
    assert alpha.target == (840.0, 500.0)
    assert alpha.marker_size_px == UNIT_TYPE_SPECS["infantry_squad"].marker_size_px


def test_snapshot_returns_value_objects_independent_from_future_session_mutation() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    snapshot_before = session.snapshot()

    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    session.tick()

    snapshot_after = session.snapshot()

    assert snapshot_before != snapshot_after
    alpha_before = next(unit for unit in snapshot_before.units if unit.unit_id == "alpha_infantry")
    alpha_after = next(unit for unit in snapshot_after.units if unit.unit_id == "alpha_infantry")
    assert alpha_before.target is None
    assert alpha_after.target is not None


def test_sync_state_updates_dimensions_ticks_and_returns_snapshot() -> None:
    session = create_default_game_session()

    snapshot = session.sync_state(width=960, height=640)

    assert isinstance(snapshot, GameStateSnapshot)
    assert session._map_size == (960, 640)
    assert snapshot.map_objects
    assert snapshot.units
    assert snapshot == session.snapshot()


def test_landing_pad_supply_schedule_starts_after_objective_secured() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    initial_landing_pad = _landing_pad_snapshot(session)
    assert initial_landing_pad.is_secured is False
    assert initial_landing_pad.next_transport_seconds is None

    session._objective_status["motorized_to_landing_pad"] = True
    session.tick()

    secured_landing_pad = _landing_pad_snapshot(session)
    assert secured_landing_pad.is_secured is True
    assert secured_landing_pad.next_transport_seconds == 45
    assert secured_landing_pad.total_stored == 0


def test_supply_transport_appears_and_delivers_resources_after_real_time_elapsed() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["motorized_to_landing_pad"] = True
    session.tick()

    clock.advance(45)
    session.tick()

    transport_snapshot = session.supply_transports_snapshot()
    assert transport_snapshot == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=transport_snapshot[0].position,
            target_object_id="landing_pad",
        ),
    )

    clock.advance(6)
    session.tick()

    unloading_landing_pad = _landing_pad_snapshot(session)
    assert unloading_landing_pad.active_transport_phase == "unloading"
    assert unloading_landing_pad.active_transport_seconds_remaining == 14

    clock.advance(14)
    session.tick()

    outbound_landing_pad = _landing_pad_snapshot(session)
    delivered_by_resource = {
        resource.resource_id: resource.amount for resource in outbound_landing_pad.resources
    }
    outbound_transport = session.supply_transports_snapshot()
    assert outbound_landing_pad.total_stored == 30
    assert delivered_by_resource == {"fuel": 12, "mre": 8, "ammo": 10}
    assert outbound_landing_pad.active_transport_phase == "outbound"
    assert outbound_landing_pad.active_transport_seconds_remaining == 6
    assert outbound_transport == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="outbound",
            position=outbound_transport[0].position,
            target_object_id="landing_pad",
        ),
    )
    assert outbound_landing_pad.next_transport_seconds is None

    clock.advance(6)
    session.tick()

    delivered_landing_pad = _landing_pad_snapshot(session)
    delivered_by_resource = {
        resource.resource_id: resource.amount for resource in delivered_landing_pad.resources
    }
    assert delivered_landing_pad.total_stored == 30
    assert delivered_by_resource == {"fuel": 12, "mre": 8, "ammo": 10}
    assert session.supply_transports_snapshot() == ()
    assert delivered_landing_pad.next_transport_seconds == 45


def test_full_landing_pad_stops_future_supply_transport() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["motorized_to_landing_pad"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 40, "mre": 20, "ammo": 30}

    session.tick()
    landing_pad = _landing_pad_snapshot(session)

    assert landing_pad.total_stored == landing_pad.capacity
    assert landing_pad.next_transport_seconds is None
    assert landing_pad.active_transport_phase is None
    assert session.supply_transports_snapshot() == ()


def test_left_click_selects_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))

    assert session.selected_unit_id() == "alpha_infantry"


def test_left_click_on_map_issues_order_for_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    assert updated_infantry["target"] is not None


def test_left_click_without_selection_does_not_issue_order() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    initial_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click((840, 500))
    for _ in range(60):
        session.tick()

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert updated_infantry["target"] is None
    assert updated_infantry["position"] == initial_infantry["position"]


def test_right_click_deselects_without_clearing_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    target_before = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]

    session.handle_right_click((20, 20))

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert session.selected_unit_id() is None
    assert updated_infantry["target"] == target_before


def test_right_click_without_selection_is_noop() -> None:
    session = create_default_game_session()

    session.handle_right_click((20, 20))

    assert session.selected_unit_id() is None


def test_supply_route_can_be_created_only_for_motorized_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert session.supply_routes_snapshot() == ()


def test_supply_route_requires_selection_and_valid_objects() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    assert session.supply_routes_snapshot() == ()

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="hq", destination_object_id="landing_pad")

    assert session.supply_routes_snapshot() == ()


def test_supply_route_moves_motorized_unit_and_transfers_supply_to_hq() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["motorized_to_landing_pad"] = True
    session.tick()

    clock.advance(45)
    session.tick()
    clock.advance(6)
    session.tick()
    clock.advance(14)
    session.tick()
    clock.advance(6)
    session.tick()

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    route_snapshot = session.supply_routes_snapshot()
    assert route_snapshot == (
        SupplyRouteSnapshot(
            route_id=route_snapshot[0].route_id,
            unit_id="bravo_mechanized",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase=route_snapshot[0].phase,
            carried_total=route_snapshot[0].carried_total,
            capacity=24,
        ),
    )

    for _ in range(800):
        session.tick()
        route = session.supply_routes_snapshot()[0]
        if route.phase == "to_pickup" and route.carried_total == 0 and session.bases_snapshot()[0].total_stored > 0:
            break

    assert session.bases_snapshot()[0].total_stored == 24
    assert session.landing_pads_snapshot()[0].total_stored == 6
    assert session.supply_routes_snapshot()[0].phase == "to_pickup"


def test_left_click_does_not_override_active_supply_route_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._landing_pads["landing_pad"].resources = {"fuel": 12, "mre": 8, "ammo": 4}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    target_before = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"]

    session.handle_left_click((40, 40))

    assert _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] == target_before


def test_motorized_squad_moves_faster_than_foot_infantry() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    target = (40, 40)
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click(target)
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(target)
    infantry_start = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_start = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["position"]

    for _ in range(120):
        session.tick()

    infantry_now = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_now = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["position"]
    infantry_distance = math.hypot(
        float(infantry_now[0]) - float(infantry_start[0]),
        float(infantry_now[1]) - float(infantry_start[1]),
    )
    motorized_distance = math.hypot(
        float(motorized_now[0]) - float(motorized_start[0]),
        float(motorized_now[1]) - float(motorized_start[1]),
    )

    assert (
        UNIT_TYPE_SPECS["mechanized_squad"].speed_kmph
        > UNIT_TYPE_SPECS["infantry_squad"].speed_kmph
    )
    assert motorized_distance > infantry_distance * 2


def test_objective_completed_only_by_motorized_squad_on_landing_pad() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]
    center = ((left + right) // 2, (top + bottom) // 2)
    motorized_target = (min(right - 10, center[0] + 18), center[1])

    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click(center)
    for _ in range(3000):
        session.tick()
        if _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"] is None:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is False

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(motorized_target)
    for _ in range(3000):
        session.tick()
        if _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] is None:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is True


def test_reset_clears_units_selection_and_objective_progress() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]
    center = ((left + right) // 2, (top + bottom) // 2)

    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(center)
    for _ in range(3000):
        session.tick()
        if session.objective_status_snapshot()["motorized_to_landing_pad"]:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is True

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.selected_unit_id() is None
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is False


def test_update_map_dimensions_ignores_non_positive_values() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=0, height=640)
    session.update_map_dimensions(width=960, height=0)
    session.update_map_dimensions(width=-1, height=100)

    assert session.map_objects_snapshot() == []
    assert session.units_snapshot() == []
    assert session.selected_unit_id() is None


def test_update_map_dimensions_builds_expected_map_layout_and_rebuilds_on_resize() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=1000, height=500)
    first_layout = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    assert first_layout["hq"] == (178, 262, 262, 318)
    assert first_layout["landing_pad"] == (744, 146, 816, 194)

    session.update_map_dimensions(width=2000, height=1000)
    resized_layout = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    assert resized_layout["hq"] == (398, 552, 482, 608)
    assert resized_layout["landing_pad"] == (1524, 316, 1596, 364)
    assert resized_layout != first_layout


def test_update_map_dimensions_clamps_unit_position_and_target_after_resize() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((955, 635))

    session.update_map_dimensions(width=120, height=90)
    motorized_after_resize = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    min_x = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2
    max_x = 120 - min_x
    min_y = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2
    max_y = 90 - min_y

    x, y = motorized_after_resize["position"]
    assert min_x <= float(x) <= max_x
    assert min_y <= float(y) <= max_y

    assert motorized_after_resize["target"] is not None
    target_x, target_y = motorized_after_resize["target"]
    assert min_x <= float(target_x) <= max_x
    assert min_y <= float(target_y) <= max_y


def test_update_map_dimensions_same_size_does_not_reclamp_existing_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    target_before = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]
    assert target_before is not None

    session.update_map_dimensions(width=960, height=640)
    target_after = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]

    assert target_after == target_before


def test_units_snapshot_contains_expected_keys_marker_sizes_and_targets() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    units = session.units_snapshot()

    assert units
    for unit in units:
        assert set(unit.keys()) == {
            "unit_id",
            "unit_type_id",
            "position",
            "target",
            "marker_size_px",
            "can_transport_supplies",
            "supply_capacity",
            "carried_supply_total",
            "active_supply_route_id",
        }
        assert unit["marker_size_px"] == UNIT_TYPE_SPECS[unit["unit_type_id"]].marker_size_px

    updated_infantry = _unit_by_id(units, "alpha_infantry")
    assert updated_infantry["target"] == (840.0, 500.0)
    assert updated_infantry["can_transport_supplies"] is False
    assert updated_infantry["supply_capacity"] == 0
    assert updated_infantry["carried_supply_total"] == 0
    assert updated_infantry["active_supply_route_id"] is None

    updated_motorized = _unit_by_id(units, "bravo_mechanized")
    assert updated_motorized["can_transport_supplies"] is True
    assert updated_motorized["supply_capacity"] == 24


def test_reset_clears_runtime_state_but_keeps_map_layout() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    map_layout_before_reset = session.map_objects_snapshot()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((840, 500))
    assert _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] is not None

    session.reset()

    assert session.units_snapshot() == []
    assert session.selected_unit_id() is None
    assert session.map_objects_snapshot() == map_layout_before_reset
    assert session.objective_status_snapshot() == {"motorized_to_landing_pad": False}


def test_reset_allows_reinitialization_without_resizing_map() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    assert session.units_snapshot()

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.units_snapshot()


def test_init_sets_expected_internal_defaults() -> None:
    session = create_default_game_session()

    assert session._map_size == (0, 0)
    assert session._map_objects == []
    assert session._bases == {}
    assert session._landing_pads == {}
    assert session._supply_routes == {}
    assert session._units == []
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._last_supply_update_at is None
    assert session._objective_status == {"motorized_to_landing_pad": False}
    assert session._objective_definitions == (
        {
            "objective_id": "motorized_to_landing_pad",
            "description_key": "mission.objective.motorized_to_landing_pad",
        },
    )


def test_reset_restores_internal_runtime_state_to_defaults() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))

    session.reset()

    assert session._units == []
    assert session._bases == {}
    assert session._landing_pads == {}
    assert session._supply_routes == {}
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._last_supply_update_at is None
    assert session._objective_status == {"motorized_to_landing_pad": False}


def test_update_map_dimensions_coerces_dimensions_to_ints() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=960.9, height=640.4)

    assert session._map_size == (960, 640)
    assert session.map_objects_snapshot()


def test_update_map_dimensions_rebuilds_map_when_objects_missing_even_without_size_change() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    first_layout = session.map_objects_snapshot()
    session._map_objects = []

    session.update_map_dimensions(width=960, height=640)

    assert session.map_objects_snapshot() == first_layout


def test_build_map_objects_preserves_configured_object_sizes() -> None:
    session = create_default_game_session()

    objects = session._build_map_objects(960, 640)
    layout_by_id = {obj["id"]: obj["bounds"] for obj in objects}

    hq_left, hq_top, hq_right, hq_bottom = layout_by_id["hq"]
    assert (hq_right - hq_left, hq_bottom - hq_top) == (84, 56)

    pad_left, pad_top, pad_right, pad_bottom = layout_by_id["landing_pad"]
    assert (pad_right - pad_left, pad_bottom - pad_top) == (72, 48)


def test_initialize_units_sets_expected_unit_ids_and_offsets_from_hq_center() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    hq = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "hq")
    left, top, right, bottom = hq["bounds"]
    center = ((left + right) / 2.0, (top + bottom) / 2.0)
    units = {unit["unit_id"]: unit for unit in session.units_snapshot()}

    assert set(units) == {"alpha_infantry", "bravo_mechanized"}
    alpha_x, alpha_y = units["alpha_infantry"]["position"]
    bravo_x, bravo_y = units["bravo_mechanized"]["position"]
    assert (alpha_x, alpha_y) == (center[0] - 22.0, center[1] + 8.0)
    assert (bravo_x, bravo_y) == (center[0] + 26.0, center[1] + 8.0)


def test_initialize_units_keeps_units_within_map_after_clamp_on_small_map() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=40, height=40)
    units = session.units_snapshot()
    assert units

    for unit in units:
        half_size = unit["marker_size_px"] / 2
        x, y = unit["position"]
        assert half_size <= float(x) <= 40 - half_size
        assert half_size <= float(y) <= 40 - half_size


def test_initialize_units_returns_early_when_hq_is_missing() -> None:
    session = create_default_game_session()
    session._map_objects = [{"id": "landing_pad", "bounds": (1, 2, 3, 4)}]

    session._initialize_units()

    assert session._units == []
    assert session._units_initialized is False


def test_update_units_position_clears_target_when_distance_is_within_step() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(100.0, 100.0),
            target=(101.0, 100.0),
        ),
    ]

    session._update_units_position()

    assert session._units[0].position == (101.0, 100.0)
    assert session._units[0].target is None


def test_update_units_position_moves_unit_by_expected_step_towards_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(100.0, 100.0),
            target=(200.0, 100.0),
        ),
    ]
    expected_step = session._movement_pixels_per_tick("infantry_squad")

    session._update_units_position()

    moved_x, moved_y = session._units[0].position
    assert moved_y == 100.0
    assert moved_x == 100.0 + expected_step
    assert session._units[0].target == (200.0, 100.0)


def test_update_units_position_skips_movement_when_speed_is_zero() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(100.0, 100.0),
            target=(200.0, 100.0),
        ),
    ]
    session._movement_pixels_per_tick = lambda _unit_type_id: 0.0

    session._update_units_position()

    assert session._units[0].position == (100.0, 100.0)
    assert session._units[0].target == (200.0, 100.0)


def test_apply_transport_delivery_handles_full_pad_empty_cargo_and_fractional_trim() -> None:
    session = create_default_game_session()
    full_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 40, "mre": 20, "ammo": 30},
    )

    session._apply_transport_delivery(full_pad, "light_supply_helicopter")
    assert full_pad.resources == {"fuel": 40, "mre": 20, "ammo": 30}

    original_cargo = dict(SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo)
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(
        {"fuel": 0, "mre": 0, "ammo": 0}
    )
    try:
        partial_pad = LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=10,
            secured_by_objective_id="",
            resources={"fuel": 0, "mre": 0, "ammo": 0},
        )
        session._apply_transport_delivery(partial_pad, "light_supply_helicopter")
        assert partial_pad.resources == {"fuel": 0, "mre": 0, "ammo": 0}
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(original_cargo)

    fractional_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=10,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )
    session._apply_transport_delivery(fractional_pad, "heavy_supply_helicopter")

    assert sum(fractional_pad.resources.values()) == 10
    assert fractional_pad.resources["fuel"] >= fractional_pad.resources["ammo"]


def test_movement_pixels_per_tick_returns_zero_for_non_positive_width() -> None:
    session = create_default_game_session()
    session._map_size = (0, 640)

    assert session._movement_pixels_per_tick("infantry_squad") == 0.0


def test_movement_pixels_per_tick_matches_expected_formula() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)

    speed = UNIT_TYPE_SPECS["infantry_squad"].speed_kmph
    km_per_tick = (speed / 3600.0) * 8.0
    km_per_pixel = 20.0 / 960.0
    expected = km_per_tick / km_per_pixel

    assert session._movement_pixels_per_tick("infantry_squad") == expected


def test_update_supply_routes_handles_missing_units_and_invalid_destinations() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._supply_routes = {
        "missing": SupplyRouteState(
            route_id="missing",
            unit_id="ghost",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes()
    assert session._supply_routes == {}

    session._units = [
        UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(100.0, 100.0)),
    ]
    session._supply_routes = {
        "u1-route": SupplyRouteState(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="missing",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes()

    assert session._supply_routes == {}


def test_refresh_route_pickup_waits_for_supply_and_capacity() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._units = [unit]
    session._bases["hq"].resources = {"fuel": 120, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)
    assert route.phase == "awaiting_supply"
    assert unit.target is None

    session._landing_pads["landing_pad"].resources = {"fuel": 10, "mre": 0, "ammo": 0}
    session._refresh_route_pickup(route, unit)
    assert route.phase == "awaiting_capacity"
    assert unit.target is None


def test_refresh_route_delivery_waits_for_capacity_and_preserves_remaining_cargo() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("hq", "mechanized_squad"),
        carried_resources={"fuel": 10, "mre": 8, "ammo": 6},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    session._bases["hq"].resources = {"fuel": 118, "mre": 1, "ammo": 0}

    session._refresh_route_delivery(route, unit)

    assert route.phase == "awaiting_capacity"
    assert unit.target is None
    assert unit.carried_resources == {"fuel": 9, "mre": 8, "ammo": 6}


def test_helpers_cover_missing_map_object_route_clear_and_resource_math() -> None:
    session = create_default_game_session()
    session._supply_routes = {
        "route": SupplyRouteState(
            route_id="route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    assert session._map_object_center("missing") == (0.0, 0.0)
    session._clear_supply_route_for_unit("u1")
    assert session._supply_routes == {}
    assert session._subtract_resources({"fuel": 4, "mre": 2, "ammo": 1}, {"fuel": 1, "mre": 3, "ammo": 1}) == {
        "fuel": 3,
        "mre": 0,
        "ammo": 0,
    }


def test_point_in_map_boundaries_are_inclusive() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)

    assert session._point_in_map((0, 0)) is True
    assert session._point_in_map((960, 640)) is True
    assert session._point_in_map((961, 640)) is False
    assert session._point_in_map((960, 641)) is False
    assert session._point_in_map((-1, 0)) is False
    assert session._point_in_map((0, -1)) is False


def test_find_unit_at_prefers_last_unit_when_bounds_overlap() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
        UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    clicked = session._find_unit_at((100, 100))

    assert clicked is not None
    assert clicked.unit_id == "u2"


def test_find_unit_at_returns_none_for_position_outside_all_units() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    assert session._find_unit_at((300, 300)) is None


def test_unit_bounds_are_computed_from_center_and_marker_size() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(100.8, 100.2))

    bounds = session._unit_bounds(unit)

    assert bounds == (90, 90, 110, 110)


def test_clamp_point_to_map_returns_float_input_when_map_size_invalid() -> None:
    session = create_default_game_session()
    session._map_size = (0, 0)

    clamped = session._clamp_point_to_map((12, 34), unit_type_id="infantry_squad")

    assert clamped == (12.0, 34.0)


def test_clamp_point_to_map_clamps_below_and_above_bounds() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)

    clamped_low = session._clamp_point_to_map((-100, -50), unit_type_id="mechanized_squad")
    clamped_high = session._clamp_point_to_map((999, 999), unit_type_id="mechanized_squad")
    half_size = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2

    assert clamped_low == (half_size, half_size)
    assert clamped_high == (120 - half_size, 90 - half_size)


def test_get_selected_unit_returns_unit_and_keeps_selection_when_found() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "u1"

    selected = session._get_selected_unit()

    assert selected is not None
    assert selected.unit_id == "u1"
    assert session._selected_unit_id == "u1"


def test_get_selected_unit_returns_none_and_clears_invalid_selection() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "missing"

    selected = session._get_selected_unit()

    assert selected is None
    assert session._selected_unit_id is None


def test_store_resources_breaks_when_capacity_is_full_and_transport_position_handles_unloading() -> None:
    session = create_default_game_session()

    stored = session._store_resources(
        {"fuel": 3, "mre": 1, "ammo": 0},
        {"fuel": 4, "mre": 2, "ammo": 1},
        4,
    )
    assert stored == {"fuel": 0, "mre": 0, "ammo": 0}

    active_transport = SupplyTransportState(
        transport_id="t1",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="unloading",
        position=(10.0, 10.0),
        seconds_remaining=5.0,
        total_phase_seconds=14.0,
        origin_position=(0.0, 0.0),
        destination_position=(30.0, 40.0),
    )

    assert session._transport_position_for_progress(active_transport) == (30.0, 40.0)


def test_handle_supply_route_replaces_existing_route_resets_cargo_and_targets_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None

    session._selected_unit_id = motorized.unit_id
    motorized.target = (10.0, 20.0)
    motorized.carried_resources = {"fuel": 4, "mre": 3, "ammo": 2}
    session._supply_routes = {
        "old-route": SupplyRouteState(
            route_id="old-route",
            unit_id=motorized.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_dropoff",
        ),
    }

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert tuple(session._supply_routes) == ("bravo_mechanized:landing_pad->hq",)
    assert motorized.carried_resources == {"fuel": 0, "mre": 0, "ammo": 0}
    assert motorized.target == session._object_target_point("landing_pad", motorized.unit_type_id)


def test_bases_snapshot_projects_sorted_resources_and_totals() -> None:
    session = create_default_game_session()
    session._bases = {
        "zeta": BaseState(
            object_id="zeta",
            capacity=7,
            resources={"fuel": 2, "mre": 1, "ammo": 3},
        ),
        "alpha": BaseState(
            object_id="alpha",
            capacity=9,
            resources={"fuel": 1, "mre": 4, "ammo": 0},
        ),
    }

    assert session.bases_snapshot() == (
        BaseSnapshot(
            object_id="alpha",
            capacity=9,
            total_stored=5,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=1),
                LandingPadResourceSnapshot(resource_id="mre", amount=4),
                LandingPadResourceSnapshot(resource_id="ammo", amount=0),
            ),
        ),
        BaseSnapshot(
            object_id="zeta",
            capacity=7,
            total_stored=6,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=2),
                LandingPadResourceSnapshot(resource_id="mre", amount=1),
                LandingPadResourceSnapshot(resource_id="ammo", amount=3),
            ),
        ),
    )


def test_landing_pad_and_transport_snapshots_include_transport_state_and_skip_empty_pads() -> None:
    session = create_default_game_session()
    session._objective_status["motorized_to_landing_pad"] = True
    active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(100.0, 200.0),
        seconds_remaining=5.2,
        total_phase_seconds=6.0,
        origin_position=(120.0, 180.0),
        destination_position=(80.0, 220.0),
    )
    session._landing_pads = {
        "zeta": LandingPadState(
            object_id="zeta",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
        ),
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="large",
            capacity=180,
            secured_by_objective_id="motorized_to_landing_pad",
            resources={"fuel": 3, "mre": 4, "ammo": 5},
            next_transport_eta_seconds=2.2,
            active_transport=active_transport,
        ),
    }

    assert session.landing_pads_snapshot() == (
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="large",
            is_secured=True,
            capacity=180,
            total_stored=12,
            next_transport_seconds=3,
            active_transport_type_id="light_supply_helicopter",
            active_transport_phase="inbound",
            active_transport_seconds_remaining=6,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=3),
                LandingPadResourceSnapshot(resource_id="mre", amount=4),
                LandingPadResourceSnapshot(resource_id="ammo", amount=5),
            ),
        ),
        LandingPadSnapshot(
            object_id="zeta",
            pad_size="small",
            is_secured=True,
            capacity=90,
            total_stored=0,
            next_transport_seconds=None,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=0),
                LandingPadResourceSnapshot(resource_id="mre", amount=0),
                LandingPadResourceSnapshot(resource_id="ammo", amount=0),
            ),
        ),
    )
    assert session.supply_transports_snapshot() == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=(100.0, 200.0),
            target_object_id="landing_pad",
        ),
    )


def test_supply_routes_snapshot_skips_missing_unit_and_uses_carried_total_and_capacity() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(10.0, 20.0),
            carried_resources={"fuel": 3, "mre": 2, "ammo": 1},
        ),
    ]
    session._supply_routes = {
        "missing": SupplyRouteState(
            route_id="missing",
            unit_id="ghost",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
        "u1-route": SupplyRouteState(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
        ),
    }

    assert session.supply_routes_snapshot() == (
        SupplyRouteSnapshot(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
            carried_total=6,
            capacity=24,
        ),
    )


def test_snapshot_includes_supply_related_subsnapshots() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["motorized_to_landing_pad"] = True
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None
    motorized.carried_resources = {"fuel": 2, "mre": 1, "ammo": 0}
    session._selected_unit_id = motorized.unit_id
    session._supply_routes = {
        "route": SupplyRouteState(
            route_id="route",
            unit_id=motorized.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_dropoff",
        ),
    }
    session._landing_pads["landing_pad"].next_transport_eta_seconds = 4.1
    session._landing_pads["landing_pad"].active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="unloading",
        position=(1.0, 2.0),
        seconds_remaining=3.1,
        total_phase_seconds=14.0,
        origin_position=(0.0, 0.0),
        destination_position=(1.0, 2.0),
    )
    session._bases["hq"].resources = {"fuel": 1, "mre": 2, "ammo": 3}

    snapshot = session.snapshot()

    assert snapshot.selected_unit_id == motorized.unit_id
    assert snapshot.supply_routes[0].carried_total == 3
    assert snapshot.supply_transports[0].phase == "unloading"
    assert snapshot.landing_pads[0].next_transport_seconds == 5
    assert snapshot.bases[0].total_stored == 6


def test_sync_bases_to_map_objects_trims_existing_resources_and_ignores_non_storage_objects() -> None:
    session = create_default_game_session()
    session._map_objects = [
        {"id": "landing_pad", "bounds": (1, 2, 3, 4), "pad_size": "small"},
        {"id": "hq", "bounds": (10, 20, 30, 40), "storage_capacity": 5},
    ]
    session._bases = {
        "hq": BaseState(
            object_id="hq",
            capacity=120,
            resources={"fuel": 3, "mre": 3, "ammo": 3},
        ),
        "stale": BaseState(
            object_id="stale",
            capacity=10,
            resources={"fuel": 9, "mre": 0, "ammo": 0},
        ),
    }

    session._sync_bases_to_map_objects()

    assert session._bases == {
        "hq": BaseState(
            object_id="hq",
            capacity=5,
            resources={"fuel": 3, "mre": 2, "ammo": 0},
        ),
    }


def test_sync_landing_pads_to_map_objects_preserves_runtime_state_trims_resources_and_refreshes_geometry() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [
        {"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": "large", "secured_by_objective_id": "x"},
        {"id": "hq", "bounds": (100, 100, 200, 200), "storage_capacity": 20},
    ]
    active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=3.0,
        total_phase_seconds=6.0,
        origin_position=(0.0, 0.0),
        destination_position=(0.0, 0.0),
    )
    session._landing_pads = {
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="old",
            resources={"fuel": 100, "mre": 60, "ammo": 40},
            next_transport_eta_seconds=9.5,
            active_transport=active_transport,
        ),
    }

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "large"
    assert landing_pad.capacity == 180
    assert landing_pad.secured_by_objective_id == "x"
    assert landing_pad.resources == {"fuel": 100, "mre": 60, "ammo": 20}
    assert landing_pad.next_transport_eta_seconds == 9.5
    assert landing_pad.active_transport is active_transport
    assert landing_pad.active_transport.destination_position == (756.0, 204.0)
    assert landing_pad.active_transport.origin_position == session._transport_origin_for_destination((756.0, 204.0))
    assert landing_pad.active_transport.position != (0.0, 0.0)


def test_consume_supply_elapsed_seconds_clamps_negative_elapsed_and_updates_timestamp() -> None:
    clock = _FakeClock(start=10.0)
    session = create_default_game_session(time_provider=clock.now)

    assert session._consume_supply_elapsed_seconds() == 0.0
    clock.current = 5.0
    assert session._consume_supply_elapsed_seconds() == 0.0
    assert session._last_supply_update_at == 5.0


def test_update_landing_pad_supply_clears_unsecured_transport_state() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="motorized_to_landing_pad",
        resources={"fuel": 1, "mre": 2, "ammo": 3},
        next_transport_eta_seconds=12.0,
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(1.0, 2.0),
            seconds_remaining=4.0,
            total_phase_seconds=6.0,
            origin_position=(0.0, 0.0),
            destination_position=(3.0, 4.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=5.0)

    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is None


def test_update_landing_pad_supply_counts_down_eta_and_starts_transport_once_interval_elapses() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    session._objective_status["motorized_to_landing_pad"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="motorized_to_landing_pad",
        next_transport_eta_seconds=10.0,
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=4.0)
    assert landing_pad.next_transport_eta_seconds == 6.0
    assert landing_pad.active_transport is None

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=6.0)
    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is not None
    assert landing_pad.active_transport.phase == "inbound"


def test_advance_transport_runs_full_lifecycle_and_schedules_next_eta_when_pad_not_full() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(90.0, 90.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)
    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.position == (60.0, 60.0)
    assert active_transport.seconds_remaining == 14.0

    session._advance_transport(landing_pad, elapsed_seconds=14.0)
    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert landing_pad.resources == {"fuel": 12, "mre": 8, "ammo": 10}
    assert active_transport.seconds_remaining == 6.0

    session._advance_transport(landing_pad, elapsed_seconds=6.0)
    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 45.0


def test_start_transport_for_landing_pad_uses_pad_spec_and_map_geometry() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="large",
        capacity=180,
        secured_by_objective_id="",
    )

    session._start_transport_for_landing_pad(landing_pad)

    assert landing_pad.active_transport is not None
    assert landing_pad.active_transport.transport_type_id == "heavy_supply_helicopter"
    assert landing_pad.active_transport.destination_position == (756.0, 204.0)
    assert landing_pad.active_transport.origin_position == (1056.0, 84.0)


def test_apply_transport_delivery_uses_fractional_distribution_without_exceeding_capacity() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=7,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )

    session._apply_transport_delivery(landing_pad, "heavy_supply_helicopter")

    assert landing_pad.resources == {"fuel": 3, "mre": 2, "ammo": 2}


def test_refresh_supply_route_targets_updates_pickup_and_delivery_targets_for_all_routes() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._landing_pads["landing_pad"].resources = {"fuel": 10, "mre": 0, "ammo": 0}
    session._bases["hq"].resources = {"fuel": 0, "mre": 0, "ammo": 0}
    pickup_unit = session._find_unit_by_id("bravo_mechanized")
    delivery_unit = UnitState(
        unit_id="delivery",
        unit_type_id="mechanized_squad",
        position=(10.0, 10.0),
        carried_resources={"fuel": 2, "mre": 0, "ammo": 0},
    )
    assert pickup_unit is not None
    session._units.append(delivery_unit)
    session._supply_routes = {
        "pickup": SupplyRouteState(
            route_id="pickup",
            unit_id=pickup_unit.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_supply",
        ),
        "delivery": SupplyRouteState(
            route_id="delivery",
            unit_id="delivery",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
        ),
    }

    session._refresh_supply_route_targets()

    assert pickup_unit.target == session._object_target_point("landing_pad", pickup_unit.unit_type_id)
    assert delivery_unit.target == session._object_target_point("hq", delivery_unit.unit_type_id)
    assert session._supply_routes["pickup"].phase == "to_pickup"
    assert session._supply_routes["delivery"].phase == "to_dropoff"


def test_refresh_route_pickup_transfers_minimum_of_source_destination_and_unit_capacity() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._units = [unit]
    session._landing_pads["landing_pad"].resources = {"fuel": 3, "mre": 4, "ammo": 10}
    session._bases["hq"].resources = {"fuel": 118, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)

    assert unit.carried_resources == {"fuel": 2, "mre": 0, "ammo": 0}
    assert session._landing_pads["landing_pad"].resources == {"fuel": 1, "mre": 4, "ammo": 10}
    assert unit.target == session._object_target_point("hq", "mechanized_squad")
    assert route.phase == "to_dropoff"


def test_refresh_route_delivery_drops_all_cargo_and_returns_unit_to_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("hq", "mechanized_squad"),
        carried_resources={"fuel": 2, "mre": 3, "ammo": 4},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    session._bases["hq"].resources = {"fuel": 1, "mre": 1, "ammo": 1}

    session._refresh_route_delivery(route, unit)

    assert session._bases["hq"].resources == {"fuel": 3, "mre": 4, "ammo": 5}
    assert unit.carried_resources == {"fuel": 0, "mre": 0, "ammo": 0}
    assert unit.target == session._object_target_point("landing_pad", "mechanized_squad")
    assert route.phase == "to_pickup"


def test_resource_helpers_trim_take_and_store_in_resource_order() -> None:
    session = create_default_game_session()

    trimmed = session._trim_resources_to_capacity({"fuel": 5, "mre": 5, "ammo": 5}, 7)
    assert trimmed == {"fuel": 5, "mre": 2, "ammo": 0}

    storage = {"fuel": 3, "mre": 4, "ammo": 5}
    taken = session._take_resources(storage, 6)
    assert taken == {"fuel": 3, "mre": 3, "ammo": 0}
    assert storage == {"fuel": 0, "mre": 1, "ammo": 5}

    base_storage = {"fuel": 1, "mre": 0, "ammo": 0}
    stored = session._store_resources(
        base_storage,
        {"fuel": 5, "mre": 4, "ammo": 3},
        6,
    )
    assert stored == {"fuel": 5, "mre": 0, "ammo": 0}
    assert base_storage == {"fuel": 6, "mre": 0, "ammo": 0}


def test_take_resources_with_non_positive_amount_is_noop() -> None:
    session = create_default_game_session()
    storage = {"fuel": 3, "mre": 4, "ammo": 5}

    assert session._take_resources(storage, 0) == {"fuel": 0, "mre": 0, "ammo": 0}
    assert storage == {"fuel": 3, "mre": 4, "ammo": 5}


def test_store_resources_spills_into_next_resource_until_capacity_is_reached() -> None:
    session = create_default_game_session()
    storage = {"fuel": 0, "mre": 1, "ammo": 0}

    stored = session._store_resources(
        storage,
        {"fuel": 2, "mre": 5, "ammo": 7},
        5,
    )

    assert stored == {"fuel": 2, "mre": 2, "ammo": 0}
    assert storage == {"fuel": 2, "mre": 3, "ammo": 0}


def test_landing_pad_security_center_target_and_tolerance_helpers_cover_edge_cases() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)
    session._map_objects = [{"id": "landing_pad", "bounds": (10, 20, 50, 60)}]
    secured_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="motorized_to_landing_pad",
    )
    always_secured_pad = LandingPadState(
        object_id="other",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
    )

    assert session._is_landing_pad_secured(secured_pad) is False
    assert session._is_landing_pad_secured(always_secured_pad) is True
    session._objective_status["motorized_to_landing_pad"] = True
    assert session._is_landing_pad_secured(secured_pad) is True
    assert session._map_object_center("landing_pad") == (30.0, 40.0)
    assert session._object_target_point("landing_pad", "mechanized_squad") == (30.0, 40.0)
    assert session._positions_match((10.0, 10.0), (10.3, 10.3)) is True
    assert session._positions_match((10.0, 10.0), (10.4, 10.4)) is False


def test_clamp_point_to_map_keeps_points_inside_bounds_unchanged() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)

    assert session._clamp_point_to_map((30, 40), unit_type_id="infantry_squad") == (30.0, 40.0)


def test_clamp_point_to_map_returns_original_point_when_either_dimension_is_invalid() -> None:
    session = create_default_game_session()

    session._map_size = (0, 90)
    assert session._clamp_point_to_map((12, 34), unit_type_id="infantry_squad") == (12.0, 34.0)

    session._map_size = (120, 0)
    assert session._clamp_point_to_map((56, 78), unit_type_id="mechanized_squad") == (56.0, 78.0)


def test_find_unit_at_includes_edges_of_unit_bounds() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0))
    session._units = [unit]
    left, top, right, bottom = session._unit_bounds(unit)

    assert session._find_unit_at((left, top)) is unit
    assert session._find_unit_at((right, bottom)) is unit


def test_refresh_route_pickup_moves_unit_towards_source_when_not_yet_at_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(10.0, 10.0))
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="awaiting_supply",
    )

    session._refresh_route_pickup(route, unit)

    assert route.phase == "to_pickup"
    assert unit.target == session._object_target_point("landing_pad", "mechanized_squad")


def test_refresh_route_delivery_moves_unit_towards_destination_when_not_yet_at_dropoff() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(10.0, 10.0),
        carried_resources={"fuel": 3, "mre": 0, "ammo": 0},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="awaiting_capacity",
    )

    session._refresh_route_delivery(route, unit)

    assert route.phase == "to_dropoff"


def test_sync_landing_pads_to_map_objects_defaults_missing_pad_size_to_small() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": None}]

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "small"
    assert landing_pad.capacity == 90


def test_update_landing_pad_supply_refreshes_transport_geometry_even_when_elapsed_is_zero() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    session._objective_status["motorized_to_landing_pad"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="motorized_to_landing_pad",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(1.0, 2.0),
            seconds_remaining=6.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=0.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.destination_position == (756.0, 204.0)
    assert active_transport.origin_position == session._transport_origin_for_destination((756.0, 204.0))
    assert active_transport.position != (1.0, 2.0)


def test_advance_transport_updates_inbound_position_before_arrival() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(0.0, 0.0),
            seconds_remaining=5.0,
            total_phase_seconds=10.0,
            origin_position=(0.0, 0.0),
            destination_position=(10.0, 0.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=2.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "inbound"
    assert active_transport.seconds_remaining == 3.0
    assert active_transport.position == (7.0, 0.0)


def test_display_seconds_rounds_up_and_clamps_negative_values() -> None:
    session = create_default_game_session()

    assert session._display_seconds(0.1) == 1
    assert session._display_seconds(-0.1) == 0
    assert session._display_seconds(None) is None


def test_transport_origin_interpolation_and_progress_cover_clamping_and_outbound_paths() -> None:
    session = create_default_game_session()
    session._map_size = (100, 80)

    assert session._transport_origin_for_destination((10.0, 10.0)) == (196.0, 24.0)
    assert session._transport_origin_for_destination((300.0, 90.0)) == (396.0, 24.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), -1.0) == (0.0, 10.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), 0.25) == (25.0, 15.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), 2.0) == (100.0, 30.0)

    inbound = SupplyTransportState(
        transport_id="t1",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=5.0,
        total_phase_seconds=10.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )
    outbound = SupplyTransportState(
        transport_id="t2",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="outbound",
        position=(0.0, 0.0),
        seconds_remaining=5.0,
        total_phase_seconds=10.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )
    instant = SupplyTransportState(
        transport_id="t3",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=3.0,
        total_phase_seconds=0.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )

    assert session._transport_position_for_progress(inbound) == (60.0, 70.0)
    assert session._transport_position_for_progress(outbound) == (60.0, 70.0)
    assert session._transport_position_for_progress(instant) == (20.0, 40.0)


def test_transport_origin_for_destination_uses_wider_x_and_clamps_y_to_bounds() -> None:
    session = create_default_game_session()
    session._map_size = (100, 300)

    assert session._transport_origin_for_destination((10.0, 10.0)) == (196.0, 24.0)
    assert session._transport_origin_for_destination((300.0, 90.0)) == (396.0, 24.0)
    assert session._transport_origin_for_destination((10.0, 500.0)) == (196.0, 276.0)
    assert session._transport_origin_for_destination((500.0, 500.0)) == (596.0, 276.0)


def test_refresh_transport_geometry_recomputes_positions_for_outbound_transport() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(0.0, 0.0),
            seconds_remaining=3.0,
            total_phase_seconds=6.0,
            origin_position=(0.0, 0.0),
            destination_position=(0.0, 0.0),
        ),
    )

    session._refresh_transport_geometry(landing_pad)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.destination_position == (756.0, 204.0)
    assert active_transport.origin_position == (1056.0, 84.0)
    assert active_transport.position == (906.0, 144.0)


def test_update_map_dimensions_accepts_minimum_positive_dimensions() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=1, height=1)

    assert session.map_objects_snapshot()
    assert session.units_snapshot()


def test_units_snapshot_exposes_active_supply_route_id_for_routed_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._selected_unit_id = "bravo_mechanized"

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    assert motorized["active_supply_route_id"] == "bravo_mechanized:landing_pad->hq"


def test_supply_transports_snapshot_skips_empty_pads_without_stopping_iteration() -> None:
    session = create_default_game_session()
    session._landing_pads = {
        "alpha_pad": LandingPadState(
            object_id="alpha_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
            active_transport=None,
        ),
        "bravo_pad": LandingPadState(
            object_id="bravo_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
            active_transport=SupplyTransportState(
                transport_id="t1",
                transport_type_id="light_supply_helicopter",
                target_object_id="bravo_pad",
                phase="inbound",
                position=(12.0, 34.0),
                seconds_remaining=5.0,
                total_phase_seconds=10.0,
                origin_position=(100.0, 40.0),
                destination_position=(20.0, 40.0),
            ),
        ),
    }

    assert session.supply_transports_snapshot() == (
        SupplyTransportSnapshot(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=(12.0, 34.0),
            target_object_id="bravo_pad",
        ),
    )


def test_snapshot_projects_current_bounds_positions_and_route_ids() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    map_objects = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    snapshot = session.snapshot()

    assert {obj.object_id: obj.bounds for obj in snapshot.map_objects} == map_objects
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").position == motorized["position"]
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").active_supply_route_id == (
        "bravo_mechanized:landing_pad->hq"
    )


def test_refresh_supply_route_removes_route_when_required_objects_disappear() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    route = next(iter(session._supply_routes.values()))

    session._landing_pads.pop("landing_pad")
    session._refresh_supply_route(route)

    assert session.supply_routes_snapshot() == ()


def test_is_valid_supply_route_pair_requires_both_source_and_destination() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)

    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="hq") is True
    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="missing") is False
    assert session._is_valid_supply_route_pair(source_object_id="missing", destination_object_id="hq") is False
