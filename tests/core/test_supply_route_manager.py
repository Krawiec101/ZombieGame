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
    assert unit.carried_resources == {"fuel": 1, "mre": 2, "ammo": 1}
    assert unit.target is None
    assert unit.path == ()
    assert base.resources == {"fuel": 5, "mre": 1, "ammo": 0}
