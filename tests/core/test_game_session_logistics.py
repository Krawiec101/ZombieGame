# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_snapshot_preserves_unit_supply_fields_without_default_fallbacks() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
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

    snapshot = session.snapshot()
    units_by_id = {unit.unit_id: unit for unit in snapshot.units}

    assert isinstance(units_by_id["alpha_infantry"], UnitSnapshot)
    assert units_by_id["alpha_infantry"].can_transport_supplies is False
    assert units_by_id["alpha_infantry"].supply_capacity == 0
    assert units_by_id["alpha_infantry"].carried_supply_total == 0
    assert units_by_id["alpha_infantry"].active_supply_route_id is None
    assert units_by_id["bravo_mechanized"].can_transport_supplies is True
    assert units_by_id["bravo_mechanized"].supply_capacity == 24
    assert units_by_id["bravo_mechanized"].carried_supply_total == 3
    assert units_by_id["bravo_mechanized"].active_supply_route_id == "route"

def test_roads_snapshot_contains_naturally_curved_supply_road() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=1000, height=500)
    road = _road_snapshot(session)

    assert road.road_id == "main_supply_road"
    assert len(road.points) > 20

    start = road.points[0]
    end = road.points[-1]
    max_deviation = 0.0
    for point in road.points[1:-1]:
        progress = (point[0] - start[0]) / (end[0] - start[0]) if end[0] != start[0] else 0.0
        straight_y = start[1] + (end[1] - start[1]) * progress
        max_deviation = max(max_deviation, abs(point[1] - straight_y))

    assert max_deviation > 12.0

def test_landing_pad_supply_schedule_starts_after_objective_secured() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    initial_landing_pad = _landing_pad_snapshot(session)
    assert initial_landing_pad.is_secured is False
    assert initial_landing_pad.next_transport_seconds is None

    session._objective_status["landing_pad_cleared"] = True
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
    session._objective_status["landing_pad_cleared"] = True
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
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 40, "mre": 20, "ammo": 30}

    session.tick()
    landing_pad = _landing_pad_snapshot(session)

    assert landing_pad.total_stored == landing_pad.capacity
    assert landing_pad.next_transport_seconds is None
    assert landing_pad.active_transport_phase is None
    assert session.supply_transports_snapshot() == ()

def test_supply_route_can_be_created_only_for_transport_capable_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert session.supply_routes_snapshot() == ()

def test_handle_supply_route_accepts_transport_capable_unit_outside_legacy_convoy_allowlist() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    original_infantry_spec = UNIT_TYPE_SPECS["infantry_squad"]
    UNIT_TYPE_SPECS["cargo_truck"] = original_infantry_spec.__class__(
        type_id="cargo_truck",
        speed_kmph=12.0,
        marker_size_px=original_infantry_spec.marker_size_px,
        armament_key=original_infantry_spec.armament_key,
        attack=original_infantry_spec.attack,
        defense=original_infantry_spec.defense,
        can_transport_supplies=True,
        supply_capacity=18,
    )
    alpha_infantry = session._find_unit_by_id("alpha_infantry")
    assert alpha_infantry is not None
    try:
        alpha_infantry.unit_type_id = "cargo_truck"
        session._selected_unit_id = alpha_infantry.unit_id

        session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    finally:
        UNIT_TYPE_SPECS.pop("cargo_truck", None)
        alpha_infantry.unit_type_id = "infantry_squad"

    assert tuple(session._supply_routes) == ("alpha_infantry:landing_pad->hq",)

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

def test_supply_route_requires_landing_pad_to_be_cleared_first() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert session.supply_routes_snapshot() == ()

def test_supply_route_moves_motorized_unit_and_transfers_supply_to_hq() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session.tick()

    clock.advance(45)
    session.tick()
    clock.advance(6)
    session.tick()
    clock.advance(14)
    session.tick()
    clock.advance(6)
    session.tick()

    session._enemy_groups = []
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
        clock.advance(1)
        session.tick()
        route = session.supply_routes_snapshot()[0]
        if route.phase == "to_pickup" and route.carried_total == 0 and session.bases_snapshot()[0].total_stored > 0:
            break

    assert session.bases_snapshot()[0].total_stored == 24
    assert session.supply_routes_snapshot()[0].phase == "to_pickup"

def test_supply_route_plans_path_along_road_points_only() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 12, "mre": 8, "ammo": 4}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    active_unit = session._find_unit_by_id("bravo_mechanized")
    road_points = set(_road_snapshot(session).points)

    assert active_unit is not None
    assert active_unit.target == session._object_target_point("landing_pad", "mechanized_squad")
    assert active_unit.path
    assert set(active_unit.path).issubset(road_points)

def test_left_click_does_not_override_active_supply_route_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 12, "mre": 8, "ammo": 4}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    target_before = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"]

    session.handle_left_click((40, 40))

    assert _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] == target_before

def test_landing_pad_objective_completes_only_after_zombies_are_removed() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    assert session.objective_status_snapshot()["landing_pad_cleared"] is False

    session._enemy_groups = []
    session.tick()

    assert session.objective_status_snapshot()["landing_pad_cleared"] is True

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

def test_apply_transport_delivery_delivers_single_remaining_slot_and_defaults_missing_cargo_keys_to_zero() -> None:
    session = create_default_game_session()
    original_cargo = dict(SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo)
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update({"fuel": 1})
    try:
        landing_pad = LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=4,
            secured_by_objective_id="",
            resources={"fuel": 3, "mre": 0, "ammo": 0},
        )

        session._apply_transport_delivery(landing_pad, "light_supply_helicopter")

        assert landing_pad.resources == {"fuel": 4, "mre": 0, "ammo": 0}
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(original_cargo)

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

    session._update_supply_routes(elapsed_seconds=0.0)
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

    session._update_supply_routes(elapsed_seconds=0.0)

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

def test_refresh_route_pickup_transfers_single_available_resource_instead_of_waiting() -> None:
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
        phase="awaiting_supply",
    )
    session._units = [unit]
    session._landing_pads["landing_pad"].resources = {"fuel": 1, "mre": 0, "ammo": 0}
    session._bases["hq"].resources = {"fuel": 0, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)

    assert unit.carried_resources == {}
    assert session._landing_pads["landing_pad"].resources == {"fuel": 1, "mre": 0, "ammo": 0}
    assert unit.target is None
    assert route.phase == "loading"
    assert route.service_seconds_remaining == 6.0

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

    assert route.phase == "unloading"
    assert unit.target is None
    assert unit.carried_resources == {"fuel": 10, "mre": 8, "ammo": 6}
    assert route.service_seconds_remaining == 6.0

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
    session._objective_status["landing_pad_cleared"] = True
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

def test_handle_supply_route_initializes_new_route_with_to_pickup_phase_before_refresh() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    captured_phases: list[str | None] = []
    original_refresh = session._refresh_supply_route
    session._refresh_supply_route = lambda route: captured_phases.append(route.phase)  # type: ignore[method-assign]
    try:
        session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    finally:
        session._refresh_supply_route = original_refresh  # type: ignore[method-assign]

    assert captured_phases == ["to_pickup"]

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
    session._objective_status["landing_pad_cleared"] = True
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
            secured_by_objective_id="landing_pad_cleared",
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
    session._objective_status["landing_pad_cleared"] = True
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

def test_sync_landing_pads_to_map_objects_defaults_missing_pad_metadata_and_resource_keys() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": None}]
    session._landing_pads = {
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="large",
            capacity=180,
            secured_by_objective_id="old-objective",
            resources={"fuel": 4},
            next_transport_eta_seconds=12.5,
        ),
    }

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "small"
    assert landing_pad.capacity == 90
    assert landing_pad.secured_by_objective_id == ""
    assert landing_pad.resources == {"fuel": 4, "mre": 0, "ammo": 0}
    assert landing_pad.next_transport_eta_seconds == 12.5

def test_sync_landing_pads_to_map_objects_initializes_missing_runtime_state_for_new_pad() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": "small"}]

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is None

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
        secured_by_objective_id="landing_pad_cleared",
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
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
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

def test_apply_transport_delivery_preserves_existing_amounts_and_initializes_missing_keys(monkeypatch) -> None:
    session = create_default_game_session()
    transport_type_id = "test_sparse_transport"
    monkeypatch.setitem(
        SUPPLY_TRANSPORT_TYPE_SPECS,
        transport_type_id,
        SupplyTransportTypeSpec(
            type_id=transport_type_id,
            cargo={"fuel": 1, "mre": 1, "ammo": 1},
        ),
    )
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=20,
        secured_by_objective_id="",
        resources={"fuel": 5},
    )

    session._apply_transport_delivery(landing_pad, transport_type_id)

    assert landing_pad.resources == {"fuel": 6, "mre": 1, "ammo": 1}

def test_apply_transport_delivery_uses_each_remaining_slot_once() -> None:
    session = create_default_game_session()
    original_transport = SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"]
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"] = SupplyTransportTypeSpec(
        type_id="light_supply_helicopter",
        cargo={"fuel": 2, "mre": 2, "ammo": 2},
    )
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=2,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )

    try:
        session._apply_transport_delivery(landing_pad, "light_supply_helicopter")
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"] = original_transport

    assert landing_pad.resources == {"fuel": 1, "mre": 1, "ammo": 0}

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

    assert unit.carried_resources == {}
    assert session._landing_pads["landing_pad"].resources == {"fuel": 3, "mre": 4, "ammo": 10}
    assert unit.target is None
    assert route.phase == "loading"
    assert route.service_seconds_remaining == 6.0

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

    assert session._bases["hq"].resources == {"fuel": 1, "mre": 1, "ammo": 1}
    assert unit.carried_resources == {"fuel": 2, "mre": 3, "ammo": 4}
    assert unit.target is None
    assert route.phase == "unloading"
    assert route.service_seconds_remaining == 6.0

def test_refresh_supply_route_uses_unit_type_service_times_from_specs(monkeypatch) -> None:
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
    session._landing_pads["landing_pad"].resources = {"fuel": 4, "mre": 0, "ammo": 0}
    monkeypatch.setitem(
        UNIT_TYPE_SPECS,
        "mechanized_squad",
        replace(UNIT_TYPE_SPECS["mechanized_squad"], supply_load_seconds=9.0, supply_unload_seconds=11.0),
    )

    session._refresh_supply_route(route)

    assert route.phase == "loading"
    assert route.service_seconds_remaining == 9.0

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
            secured_by_objective_id="landing_pad_cleared",
    )
    always_secured_pad = LandingPadState(
        object_id="other",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
    )

    assert session._is_landing_pad_secured(secured_pad) is False
    assert session._is_landing_pad_secured(always_secured_pad) is True
    session._objective_status["landing_pad_cleared"] = True
    assert session._is_landing_pad_secured(secured_pad) is True
    assert session._map_object_center("landing_pad") == (30.0, 40.0)
    assert session._object_target_point("landing_pad", "mechanized_squad") == (30.0, 40.0)
    assert session._positions_match((10.0, 10.0), (10.3, 10.3)) is True
    assert session._positions_match((10.0, 10.0), (10.4, 10.4)) is False

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
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
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

def test_update_landing_pad_supply_returns_after_exactly_consuming_elapsed_transport_time() -> None:
    session = create_default_game_session()
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    def finish_transport(pad: LandingPadState, elapsed_seconds: float) -> None:
        assert elapsed_seconds == 1.0
        pad.active_transport = None

    session._advance_transport = finish_transport  # type: ignore[method-assign]

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=1.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds is None

def test_update_landing_pad_supply_advances_exactly_one_second_of_active_transport() -> None:
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
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(12.0, 18.0),
            destination_position=(30.0, 42.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.seconds_remaining == 14.0
    assert active_transport.position == (30.0, 42.0)

def test_update_landing_pad_supply_consumes_one_second_of_leftover_eta_after_transport_finishes() -> None:
    session = create_default_game_session()
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    def finish_transport(pad: LandingPadState, elapsed_seconds: float) -> None:
        assert elapsed_seconds == 1.0
        pad.active_transport = None

    session._advance_transport = finish_transport  # type: ignore[method-assign]

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=2.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 44.0

def test_update_landing_pad_supply_uses_leftover_elapsed_time_to_start_next_eta_countdown() -> None:
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
            phase="outbound",
            position=(90.0, 90.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=2.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 44.0

def test_advance_transport_keeps_inbound_phase_while_one_second_remains() -> None:
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
            seconds_remaining=2.0,
            total_phase_seconds=10.0,
            origin_position=(0.0, 0.0),
            destination_position=(10.0, 0.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "inbound"
    assert active_transport.seconds_remaining == 1.0
    assert active_transport.position == (9.0, 0.0)

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

def test_advance_transport_transitions_from_inbound_to_unloading_on_exact_arrival() -> None:
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
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(12.0, 18.0),
            destination_position=(30.0, 42.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.seconds_remaining == 14.0
    assert active_transport.total_phase_seconds == 14.0
    assert active_transport.position == (30.0, 42.0)

def test_advance_transport_keeps_destination_position_while_unloading_and_sets_outbound_position() -> None:
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
            phase="unloading",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=14.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert active_transport.seconds_remaining == 6.0
    assert active_transport.total_phase_seconds == 6.0
    assert active_transport.position == (60.0, 60.0)

def test_advance_transport_updates_outbound_position_before_departure_finishes() -> None:
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
            phase="outbound",
            position=(0.0, 0.0),
            seconds_remaining=2.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert active_transport.position == (110.0, 110.0)

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

def test_units_snapshot_exposes_active_supply_route_id_for_routed_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True
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
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    map_objects = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    snapshot = session.snapshot()

    assert {obj.object_id: obj.bounds for obj in snapshot.map_objects} == map_objects
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").position == motorized["position"]
    assert snapshot.enemy_groups[0].group_id == "zulu_zombies"
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").active_supply_route_id == (
        "bravo_mechanized:landing_pad->hq"
    )

def test_refresh_supply_route_removes_route_when_required_objects_disappear() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    route = next(iter(session._supply_routes.values()))

    session._landing_pads.pop("landing_pad")
    session._refresh_supply_route(route)

    assert session.supply_routes_snapshot() == ()

def test_refresh_supply_route_removes_route_when_unit_disappears() -> None:
    session = create_default_game_session()
    route = SupplyRouteState(
        route_id="missing-unit-route",
        unit_id="ghost_unit",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._supply_routes = {route.route_id: route}

    session._refresh_supply_route(route)

    assert session._supply_routes == {}

def test_update_supply_routes_continues_after_removing_missing_unit_route() -> None:
    session = create_default_game_session()
    session._units = [UnitState(unit_id="u2", unit_type_id="mechanized_squad", position=(10.0, 10.0))]
    handled_route_ids: list[str] = []
    session._refresh_supply_route = (  # type: ignore[method-assign]
        lambda route, *, elapsed_seconds=0.0: handled_route_ids.append(route.route_id)
    )
    session._supply_routes = {
        "a-missing": SupplyRouteState(
            route_id="a-missing",
            unit_id="ghost_unit",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
        "z-present": SupplyRouteState(
            route_id="z-present",
            unit_id="u2",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes(elapsed_seconds=0.0)

    assert "a-missing" not in session._supply_routes
    assert handled_route_ids == ["z-present"]

def test_is_valid_supply_route_pair_requires_both_source_and_destination() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True

    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="hq") is True
    assert session._is_valid_supply_route_pair(source_object_id="hq", destination_object_id="landing_pad") is True
    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="missing") is False
    assert session._is_valid_supply_route_pair(source_object_id="missing", destination_object_id="hq") is False

def test_supply_route_endpoints_snapshot_exposes_generic_capabilities() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)

    inactive_before_secured = {endpoint.object_id: endpoint for endpoint in session.supply_route_endpoints_snapshot()}
    session._objective_status["landing_pad_cleared"] = True
    active_after_secured = {endpoint.object_id: endpoint for endpoint in session.supply_route_endpoints_snapshot()}

    assert inactive_before_secured["landing_pad"].location_type == "landing_pad"
    assert inactive_before_secured["landing_pad"].can_dispatch_supplies is True
    assert inactive_before_secured["landing_pad"].can_receive_supplies is False
    assert inactive_before_secured["landing_pad"].is_active is False

    assert active_after_secured["hq"].location_type == "base"
    assert active_after_secured["hq"].can_dispatch_supplies is False
    assert active_after_secured["hq"].can_receive_supplies is True
    assert active_after_secured["hq"].is_active is True
    assert active_after_secured["landing_pad"].is_active is True

def test_supply_routes_state_snapshot_exposes_route_id_and_exact_keys() -> None:
    session = create_default_game_session()
    session._supply_routes = {
        "route-1": SupplyRouteState(
            route_id="route-1",
            unit_id="bravo_mechanized",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        )
    }

    assert session.supply_routes_state_snapshot() == [
        {
            "route_id": "route-1",
            "unit_id": "bravo_mechanized",
            "source_object_id": "landing_pad",
            "destination_object_id": "hq",
            "phase": "to_pickup",
        }
    ]

def test_update_map_dimensions_retargets_units_with_supply_route_aware_road_mode_after_resize() -> None:
    session = create_default_game_session()
    session._map_size = (100, 100)
    session._map_objects = [{"id": "hq", "bounds": (0, 0, 10, 10)}]
    session._roads = [{"id": "road", "points": ((0.0, 0.0), (10.0, 10.0))}]
    session._units_initialized = True
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(25.0, 25.0),
            target=(75.0, 75.0),
        )
    ]

    recorded_road_modes: list[str | None] = []
    session._build_map_objects = lambda width, height: session._map_objects  # type: ignore[method-assign]
    session._build_roads = lambda: session._roads  # type: ignore[method-assign]
    session._sync_bases_to_map_objects = lambda: None  # type: ignore[method-assign]
    session._sync_landing_pads_to_map_objects = lambda: None  # type: ignore[method-assign]
    session._clamp_point_to_map = lambda position, *, unit_type_id: position  # type: ignore[method-assign]
    session._unit_has_supply_route = lambda unit_id: unit_id == "u1"  # type: ignore[method-assign]
    session._road_mode_for_unit = lambda unit_type_id: "off"  # type: ignore[method-assign]
    session._set_unit_target = (  # type: ignore[method-assign]
        lambda unit, target, *, road_mode: recorded_road_modes.append(road_mode)
    )
    session._clamp_enemy_groups_to_map = lambda: None  # type: ignore[method-assign]
    session._refresh_supply_route_targets = lambda: None  # type: ignore[method-assign]

    session.update_map_dimensions(width=120, height=120)

    assert recorded_road_modes == ["only"]

