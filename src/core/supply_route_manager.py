from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from contracts.game_state import SupplyRouteSnapshot
from core.model.buildings import BaseState, LandingPadState, SUPPLY_RESOURCE_ORDER, SupplyRouteState
from core.model.units import UnitState

DEFAULT_SUPPLY_CONVOY_UNIT_TYPE_IDS = frozenset({"mechanized_squad"})

UnitFinder = Callable[[str], UnitState | None]
ObjectTargetPointResolver = Callable[[str, str], tuple[float, float]]
PositionsMatch = Callable[[tuple[float, float], tuple[float, float]], bool]
UnitTargetSetter = Callable[[UnitState, tuple[float, float]], None]
UnitSupplyCapacityResolver = Callable[[str], int]
LandingPadSecurityChecker = Callable[[LandingPadState], bool]
RouteRefresher = Callable[[SupplyRouteState], None]


@dataclass
class SupplyRouteManager:
    resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER
    convoy_unit_type_ids: frozenset[str] = DEFAULT_SUPPLY_CONVOY_UNIT_TYPE_IDS
    routes: dict[str, SupplyRouteState] = field(default_factory=dict)

    def clear(self) -> None:
        self.routes = {}

    def can_unit_create_convoy(self, unit: UnitState | None) -> bool:
        if unit is None:
            return False
        return self.can_unit_type_create_convoy(unit.unit_type_id)

    def can_unit_type_create_convoy(self, unit_type_id: str) -> bool:
        return unit_type_id in self.convoy_unit_type_ids

    def create_route(
        self,
        *,
        selected_unit: UnitState | None,
        source_object_id: str,
        destination_object_id: str,
        landing_pads: Mapping[str, LandingPadState],
        bases: Mapping[str, BaseState],
        is_landing_pad_secured: LandingPadSecurityChecker,
        object_target_point: ObjectTargetPointResolver,
        positions_match: PositionsMatch,
        set_unit_target: UnitTargetSetter,
        unit_supply_capacity: UnitSupplyCapacityResolver,
        find_unit_by_id: UnitFinder,
        refresh_route: RouteRefresher | None = None,
    ) -> None:
        if not self.can_unit_create_convoy(selected_unit):
            return

        assert selected_unit is not None

        if not self.is_valid_route_pair(
            source_object_id=source_object_id,
            destination_object_id=destination_object_id,
            landing_pads=landing_pads,
            bases=bases,
            is_landing_pad_secured=is_landing_pad_secured,
        ):
            return

        self.clear_route_for_unit(selected_unit.unit_id)
        selected_unit.clear_movement()
        selected_unit.clear_supplies(resource_order=self.resource_order)

        route = SupplyRouteState(
            route_id=f"{selected_unit.unit_id}:{source_object_id}->{destination_object_id}",
            unit_id=selected_unit.unit_id,
            source_object_id=source_object_id,
            destination_object_id=destination_object_id,
            phase="to_pickup",
        )
        self.routes[route.route_id] = route
        if refresh_route is not None:
            refresh_route(route)
            return

        self.refresh_route(
            route,
            find_unit_by_id=find_unit_by_id,
            landing_pads=landing_pads,
            bases=bases,
            object_target_point=object_target_point,
            positions_match=positions_match,
            set_unit_target=set_unit_target,
            unit_supply_capacity=unit_supply_capacity,
        )

    def supply_routes_snapshot(
        self,
        *,
        find_unit_by_id: UnitFinder,
        unit_supply_capacity: UnitSupplyCapacityResolver,
    ) -> tuple[SupplyRouteSnapshot, ...]:
        snapshots: list[SupplyRouteSnapshot] = []
        for route_id in sorted(self.routes):
            route = self.routes[route_id]
            unit = find_unit_by_id(route.unit_id)
            if unit is None:
                continue
            snapshots.append(
                SupplyRouteSnapshot(
                    route_id=route.route_id,
                    unit_id=route.unit_id,
                    source_object_id=route.source_object_id,
                    destination_object_id=route.destination_object_id,
                    phase=route.phase,
                    carried_total=unit.carried_supply_total(resource_order=self.resource_order),
                    capacity=unit_supply_capacity(unit.unit_type_id),
                )
            )
        return tuple(snapshots)

    def supply_routes_state_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "route_id": route.route_id,
                "unit_id": route.unit_id,
                "source_object_id": route.source_object_id,
                "destination_object_id": route.destination_object_id,
                "phase": route.phase,
            }
            for route in self.routes.values()
        ]

    def route_id_for_unit(self, unit_id: str) -> str | None:
        for route in self.routes.values():
            if route.unit_id == unit_id:
                return route.route_id
        return None

    def unit_has_route(self, unit_id: str) -> bool:
        return self.route_id_for_unit(unit_id) is not None

    def clear_route_for_unit(self, unit_id: str) -> None:
        route_id = self.route_id_for_unit(unit_id)
        if route_id is not None:
            self.routes.pop(route_id, None)

    def is_valid_route_pair(
        self,
        *,
        source_object_id: str,
        destination_object_id: str,
        landing_pads: Mapping[str, LandingPadState],
        bases: Mapping[str, BaseState],
        is_landing_pad_secured: LandingPadSecurityChecker,
    ) -> bool:
        if source_object_id not in landing_pads or destination_object_id not in bases:
            return False
        return is_landing_pad_secured(landing_pads[source_object_id])

    def refresh_route(
        self,
        route: SupplyRouteState,
        *,
        find_unit_by_id: UnitFinder,
        landing_pads: Mapping[str, LandingPadState],
        bases: Mapping[str, BaseState],
        object_target_point: ObjectTargetPointResolver,
        positions_match: PositionsMatch,
        set_unit_target: UnitTargetSetter,
        unit_supply_capacity: UnitSupplyCapacityResolver,
    ) -> None:
        unit = find_unit_by_id(route.unit_id)
        if unit is None:
            self.routes.pop(route.route_id, None)
            return

        if route.source_object_id not in landing_pads or route.destination_object_id not in bases:
            self.clear_route_for_unit(route.unit_id)
            return

        if unit.carried_supply_total(resource_order=self.resource_order) > 0:
            self.refresh_route_delivery(
                route,
                unit,
                bases=bases,
                object_target_point=object_target_point,
                positions_match=positions_match,
                set_unit_target=set_unit_target,
            )
            return

        self.refresh_route_pickup(
            route,
            unit,
            landing_pads=landing_pads,
            bases=bases,
            object_target_point=object_target_point,
            positions_match=positions_match,
            set_unit_target=set_unit_target,
            unit_supply_capacity=unit_supply_capacity,
        )

    def refresh_route_pickup(
        self,
        route: SupplyRouteState,
        unit: UnitState,
        *,
        landing_pads: Mapping[str, LandingPadState],
        bases: Mapping[str, BaseState],
        object_target_point: ObjectTargetPointResolver,
        positions_match: PositionsMatch,
        set_unit_target: UnitTargetSetter,
        unit_supply_capacity: UnitSupplyCapacityResolver,
    ) -> None:
        pickup_target = object_target_point(route.source_object_id, unit.unit_type_id)
        if not positions_match(unit.position, pickup_target):
            if unit.target is None or not positions_match(unit.target, pickup_target):
                set_unit_target(unit, pickup_target)
            route.phase = "to_pickup"
            return

        source = landing_pads[route.source_object_id]
        destination = bases[route.destination_object_id]
        available_at_source = source.total_stored(resource_order=self.resource_order)
        free_at_destination = destination.free_capacity(resource_order=self.resource_order)
        unit_capacity = unit_supply_capacity(unit.unit_type_id)
        transfer_total = min(unit_capacity, available_at_source, free_at_destination)

        if transfer_total <= 0:
            unit.clear_movement()
            route.phase = "awaiting_supply" if available_at_source <= 0 else "awaiting_capacity"
            return

        picked_up_resources = source.take_resources(transfer_total, resource_order=self.resource_order)
        unit.load_supplies(
            picked_up_resources,
            capacity=unit_capacity,
            resource_order=self.resource_order,
        )
        set_unit_target(unit, object_target_point(route.destination_object_id, unit.unit_type_id))
        route.phase = "to_dropoff"

    def refresh_route_delivery(
        self,
        route: SupplyRouteState,
        unit: UnitState,
        *,
        bases: Mapping[str, BaseState],
        object_target_point: ObjectTargetPointResolver,
        positions_match: PositionsMatch,
        set_unit_target: UnitTargetSetter,
    ) -> None:
        dropoff_target = object_target_point(route.destination_object_id, unit.unit_type_id)
        if not positions_match(unit.position, dropoff_target):
            if unit.target is None or not positions_match(unit.target, dropoff_target):
                set_unit_target(unit, dropoff_target)
            route.phase = "to_dropoff"
            return

        destination = bases[route.destination_object_id]
        delivered_resources = destination.store_resources(
            unit.carried_resources,
            resource_order=self.resource_order,
        )
        carried_total = unit.carried_supply_total(resource_order=self.resource_order)
        unloaded_resources = unit.unload_supplies(
            delivered_resources,
            resource_order=self.resource_order,
        )
        unloaded_total = sum(int(unloaded_resources.get(resource_id, 0)) for resource_id in self.resource_order)
        if unloaded_total < carried_total:
            unit.clear_movement()
            route.phase = "awaiting_capacity"
            return

        set_unit_target(unit, object_target_point(route.source_object_id, unit.unit_type_id))
        route.phase = "to_pickup"
