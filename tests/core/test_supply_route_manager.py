from __future__ import annotations

import math

from core.model.buildings import BaseState, LandingPadState, SupplyRouteState
from core.model.units import UnitState
from core.supply_route_manager import SupplyRouteManager


def _positions_match(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return math.hypot(first[0] - second[0], first[1] - second[1]) <= 0.5


def _set_unit_target(unit: UnitState, target: tuple[float, float]) -> None:
    unit.target = target
    unit.path = (target,)


def test_create_route_clears_previous_route_and_targets_pickup() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        target=(9.0, 9.0),
        path=((9.0, 9.0),),
        carried_resources={"fuel": 4, "mre": 2, "ammo": 1},
    )
    manager.routes = {
        "u1:old->route": SupplyRouteState(
            route_id="u1:old->route",
            unit_id="u1",
            source_object_id="old",
            destination_object_id="route",
            phase="to_dropoff",
        )
    }

    manager.create_route(
        selected_unit=unit,
        source_object_id="landing_pad",
        destination_object_id="hq",
        landing_pads={
            "landing_pad": LandingPadState(
                object_id="landing_pad",
                pad_size="small",
                capacity=20,
                secured_by_objective_id="",
            )
        },
        bases={"hq": BaseState(object_id="hq", capacity=20)},
        is_landing_pad_secured=lambda _landing_pad: True,
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
    )

    assert tuple(manager.routes) == ("u1:landing_pad->hq",)
    assert unit.carried_resources == {"fuel": 0, "mre": 0, "ammo": 0}
    assert unit.target == (5.0, 5.0)


def test_create_route_rejects_unit_type_without_convoy_permission() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="infantry_squad",
        position=(0.0, 0.0),
    )

    manager.create_route(
        selected_unit=unit,
        source_object_id="landing_pad",
        destination_object_id="hq",
        landing_pads={
            "landing_pad": LandingPadState(
                object_id="landing_pad",
                pad_size="small",
                capacity=20,
                secured_by_objective_id="",
            )
        },
        bases={"hq": BaseState(object_id="hq", capacity=20)},
        is_landing_pad_secured=lambda _landing_pad: True,
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
    )

    assert manager.routes == {}
    assert manager.can_unit_create_convoy(unit) is False
    assert manager.can_unit_type_create_convoy("infantry_squad") is False
    assert manager.can_unit_type_create_convoy("mechanized_squad") is True


def test_refresh_route_pickup_loads_supplies_and_sends_unit_to_dropoff() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(5.0, 5.0),
    )
    route = SupplyRouteState(
        route_id="u1:landing_pad->hq",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    manager.routes = {route.route_id: route}
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=20,
        secured_by_objective_id="",
        resources={"fuel": 4, "mre": 3, "ammo": 2},
    )
    base = BaseState(
        object_id="hq",
        capacity=5,
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )

    manager.refresh_route(
        route,
        elapsed_seconds=0.0,
        load_seconds=6.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={"landing_pad": landing_pad},
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "loading"
    assert route.service_seconds_remaining == 6.0
    assert unit.carried_resources == {}
    assert landing_pad.resources == {"fuel": 4, "mre": 3, "ammo": 2}
    assert unit.target is None

    manager.refresh_route(
        route,
        elapsed_seconds=6.0,
        load_seconds=6.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={"landing_pad": landing_pad},
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "to_dropoff"
    assert route.service_seconds_remaining == 0.0
    assert unit.carried_resources == {"fuel": 4, "mre": 1, "ammo": 0}
    assert landing_pad.resources == {"fuel": 0, "mre": 2, "ammo": 2}
    assert unit.target == (15.0, 15.0)


def test_refresh_route_delivery_unloads_partial_cargo_and_waits_for_capacity() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(15.0, 15.0),
        carried_resources={"fuel": 4, "mre": 2, "ammo": 1},
        target=(15.0, 15.0),
        path=((15.0, 15.0),),
    )
    route = SupplyRouteState(
        route_id="u1:landing_pad->hq",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    manager.routes = {route.route_id: route}
    base = BaseState(
        object_id="hq",
        capacity=6,
        resources={"fuel": 2, "mre": 1, "ammo": 0},
    )

    manager.refresh_route(
        route,
        elapsed_seconds=0.0,
        unload_seconds=6.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={
            "landing_pad": LandingPadState(
                object_id="landing_pad",
                pad_size="small",
                capacity=20,
                secured_by_objective_id="",
            )
        },
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "unloading"
    assert route.service_seconds_remaining == 6.0
    assert unit.carried_resources == {"fuel": 4, "mre": 2, "ammo": 1}
    assert unit.target is None
    assert unit.path == ()
    assert base.resources == {"fuel": 2, "mre": 1, "ammo": 0}

    manager.refresh_route(
        route,
        elapsed_seconds=6.0,
        unload_seconds=6.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={
            "landing_pad": LandingPadState(
                object_id="landing_pad",
                pad_size="small",
                capacity=20,
                secured_by_objective_id="",
            )
        },
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "awaiting_capacity"
    assert route.service_seconds_remaining == 0.0
    assert unit.carried_resources == {"fuel": 1, "mre": 2, "ammo": 1}
    assert unit.target is None
    assert unit.path == ()
    assert base.resources == {"fuel": 5, "mre": 1, "ammo": 0}


def test_refresh_route_loading_revalidates_pickup_position_before_taking_supplies() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(9.0, 9.0),
    )
    route = SupplyRouteState(
        route_id="u1:landing_pad->hq",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="loading",
        service_seconds_remaining=1.0,
    )
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=20,
        secured_by_objective_id="",
        resources={"fuel": 4, "mre": 3, "ammo": 2},
    )
    base = BaseState(object_id="hq", capacity=20)

    manager.refresh_route(
        route,
        elapsed_seconds=1.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={"landing_pad": landing_pad},
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "to_pickup"
    assert route.service_seconds_remaining == 0.0
    assert unit.carried_resources == {}
    assert landing_pad.resources == {"fuel": 4, "mre": 3, "ammo": 2}
    assert unit.target == (5.0, 5.0)


def test_refresh_route_unloading_revalidates_dropoff_position_before_storing_supplies() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"mechanized_squad"}),
    )
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(12.0, 12.0),
        carried_resources={"fuel": 4, "mre": 2, "ammo": 1},
    )
    route = SupplyRouteState(
        route_id="u1:landing_pad->hq",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="unloading",
        service_seconds_remaining=1.0,
    )
    base = BaseState(object_id="hq", capacity=20)

    manager.refresh_route(
        route,
        elapsed_seconds=1.0,
        find_unit_by_id=lambda unit_id: unit if unit_id == "u1" else None,
        landing_pads={
            "landing_pad": LandingPadState(
                object_id="landing_pad",
                pad_size="small",
                capacity=20,
                secured_by_objective_id="",
            )
        },
        bases={"hq": base},
        object_target_point=lambda object_id, _unit_type_id: {
            "landing_pad": (5.0, 5.0),
            "hq": (15.0, 15.0),
        }[object_id],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda _unit_type_id: 24,
    )

    assert route.phase == "to_dropoff"
    assert route.service_seconds_remaining == 0.0
    assert unit.carried_resources == {"fuel": 4, "mre": 2, "ammo": 1}
    assert base.resources == {"fuel": 0, "mre": 0, "ammo": 0}
    assert unit.target == (15.0, 15.0)


def test_refresh_route_uses_service_time_resolvers_per_unit_type() -> None:
    manager = SupplyRouteManager(
        resource_order=("fuel", "mre", "ammo"),
        convoy_unit_type_ids=frozenset({"truck", "jeep"}),
    )
    units = {
        "truck-1": UnitState(unit_id="truck-1", unit_type_id="truck", position=(5.0, 5.0)),
        "jeep-1": UnitState(
            unit_id="jeep-1",
            unit_type_id="jeep",
            position=(15.0, 15.0),
            carried_resources={"fuel": 2},
        ),
    }
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=20,
        secured_by_objective_id="",
        resources={"fuel": 4, "mre": 0, "ammo": 0},
    )
    base = BaseState(object_id="hq", capacity=20)
    route_to_pickup = SupplyRouteState(
        route_id="truck-1:landing_pad->hq",
        unit_id="truck-1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    route_to_dropoff = SupplyRouteState(
        route_id="jeep-1:landing_pad->hq",
        unit_id="jeep-1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    target_points = {
        ("landing_pad", "truck"): (5.0, 5.0),
        ("hq", "truck"): (15.0, 15.0),
        ("landing_pad", "jeep"): (5.0, 5.0),
        ("hq", "jeep"): (15.0, 15.0),
    }

    manager.refresh_route(
        route_to_pickup,
        find_unit_by_id=lambda unit_id: units.get(unit_id),
        landing_pads={"landing_pad": landing_pad},
        bases={"hq": base},
        object_target_point=lambda object_id, unit_type_id: target_points[(object_id, unit_type_id)],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda unit_type_id: {"truck": 24, "jeep": 12}[unit_type_id],
        unit_load_seconds=lambda unit_type_id: {"truck": 10.0, "jeep": 4.0}[unit_type_id],
        unit_unload_seconds=lambda unit_type_id: {"truck": 8.0, "jeep": 3.0}[unit_type_id],
    )
    manager.refresh_route(
        route_to_dropoff,
        find_unit_by_id=lambda unit_id: units.get(unit_id),
        landing_pads={"landing_pad": landing_pad},
        bases={"hq": base},
        object_target_point=lambda object_id, unit_type_id: target_points[(object_id, unit_type_id)],
        positions_match=_positions_match,
        set_unit_target=_set_unit_target,
        unit_supply_capacity=lambda unit_type_id: {"truck": 24, "jeep": 12}[unit_type_id],
        unit_load_seconds=lambda unit_type_id: {"truck": 10.0, "jeep": 4.0}[unit_type_id],
        unit_unload_seconds=lambda unit_type_id: {"truck": 8.0, "jeep": 3.0}[unit_type_id],
    )

    assert route_to_pickup.phase == "loading"
    assert route_to_pickup.service_seconds_remaining == 10.0
    assert route_to_dropoff.phase == "unloading"
    assert route_to_dropoff.service_seconds_remaining == 3.0
