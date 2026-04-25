from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from contracts.game_state import (
    BaseSnapshot,
    CombatNotificationSnapshot,
    CombatSnapshot,
    GameStateSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    MissionReportSnapshot,
    RoadSnapshot,
    SupplyRouteEndpointSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    UnitCommanderSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)
from core.combat import CombatNotificationState, CombatState, ZombieGroupState
from core.model.buildings import BaseState, LandingPadState
from core.model.units import UnitState, UnitTypeSpec
from core.logistics.routes import SupplyRouteEndpoint

DisplaySeconds = Callable[[float | None], int | None]
UnitCombatLookup = Callable[[str], CombatState | None]
EnemyCombatLookup = Callable[[str], CombatState | None]
UnitFinder = Callable[[str], UnitState | None]
EnemyGroupFinder = Callable[[str], ZombieGroupState | None]
UnitStatResolver = Callable[[UnitState], int]
UnitArmamentResolver = Callable[[UnitState], str]
UnitSupplyCapacityResolver = Callable[[str], int]
UnitRouteIdResolver = Callable[[str], str | None]
CombatSecondsResolver = Callable[[str], float | None]


@dataclass(frozen=True)
class GameStateSnapshotBuilder:
    def map_objects_state(self, map_objects: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"id": obj["id"], "bounds": obj["bounds"]} for obj in map_objects]

    def enemy_groups_state(self, enemy_groups: Sequence[ZombieGroupState]) -> list[dict[str, Any]]:
        return [
            {
                "group_id": enemy_group.group_id,
                "position": enemy_group.position,
                "name": enemy_group.name,
                "personnel": enemy_group.personnel,
            }
            for enemy_group in enemy_groups
        ]

    def roads(self, roads: Sequence[dict[str, Any]]) -> tuple[RoadSnapshot, ...]:
        return tuple(
            RoadSnapshot(
                road_id=str(road["id"]),
                points=tuple(tuple(point) for point in road["points"]),
            )
            for road in roads
        )

    def units(
        self,
        units: Sequence[UnitState],
        *,
        unit_type_specs: Mapping[str, UnitTypeSpec],
        unit_armament_key: UnitArmamentResolver,
        unit_attack: UnitStatResolver,
        unit_defense: UnitStatResolver,
        resource_order: Sequence[str],
        supply_route_id_for_unit: UnitRouteIdResolver,
        combat_for_unit: UnitCombatLookup,
        combat_seconds_remaining_for_unit: CombatSecondsResolver,
        display_seconds: DisplaySeconds,
    ) -> list[dict[str, Any]]:
        return [
            {
                "unit_id": unit.unit_id,
                "unit_type_id": unit.unit_type_id,
                "position": unit.position,
                "target": unit.target,
                "marker_size_px": unit_type_specs[unit.unit_type_id].marker_size_px,
                "name": unit.name,
                "commander": {
                    "name": unit.commander.name,
                    "experience_level": unit.commander.experience_level,
                },
                "experience_level": unit.experience_level,
                "personnel": unit.personnel,
                "armament_key": unit_armament_key(unit),
                "attack": unit_attack(unit),
                "defense": unit_defense(unit),
                "morale": unit.morale,
                "ammo": unit.ammo,
                "rations": unit.rations,
                "fuel": unit.fuel,
                "can_transport_supplies": unit_type_specs[unit.unit_type_id].can_transport_supplies,
                "supply_capacity": unit_type_specs[unit.unit_type_id].supply_capacity,
                "carried_supply_total": unit.carried_supply_total(resource_order=resource_order),
                "active_supply_route_id": supply_route_id_for_unit(unit.unit_id),
                "is_in_combat": combat_for_unit(unit.unit_id) is not None,
                "combat_seconds_remaining": display_seconds(
                    combat_seconds_remaining_for_unit(unit.unit_id)
                ),
            }
            for unit in units
        ]

    def bases(
        self,
        bases: Mapping[str, BaseState],
        *,
        resource_order: Sequence[str],
    ) -> tuple[BaseSnapshot, ...]:
        snapshots: list[BaseSnapshot] = []
        for object_id in sorted(bases):
            base = bases[object_id]
            snapshots.append(
                BaseSnapshot(
                    object_id=base.object_id,
                    capacity=base.capacity,
                    total_stored=base.total_stored(resource_order=resource_order),
                    resources=tuple(
                        LandingPadResourceSnapshot(
                            resource_id=resource_id,
                            amount=int(base.resources.get(resource_id, 0)),
                        )
                        for resource_id in resource_order
                    ),
                )
            )
        return tuple(snapshots)

    def enemy_groups(
        self,
        enemy_groups: Sequence[ZombieGroupState],
        *,
        marker_size_px: int,
        combat_for_enemy_group: EnemyCombatLookup,
    ) -> tuple[ZombieGroupSnapshot, ...]:
        return tuple(
            ZombieGroupSnapshot(
                group_id=enemy_group.group_id,
                position=enemy_group.position,
                marker_size_px=marker_size_px,
                name=enemy_group.name,
                personnel=enemy_group.personnel,
                is_in_combat=combat_for_enemy_group(enemy_group.group_id) is not None,
            )
            for enemy_group in enemy_groups
        )

    def combats(
        self,
        combats: Mapping[str, CombatState],
        *,
        find_unit_by_id: UnitFinder,
        find_enemy_group_by_id: EnemyGroupFinder,
        display_seconds: DisplaySeconds,
    ) -> tuple[CombatSnapshot, ...]:
        snapshots: list[CombatSnapshot] = []
        for combat_id in sorted(combats):
            combat = combats[combat_id]
            unit = find_unit_by_id(combat.unit_id)
            enemy_group = find_enemy_group_by_id(combat.enemy_group_id)
            if unit is None or enemy_group is None:
                continue
            snapshots.append(
                CombatSnapshot(
                    combat_id=combat.combat_id,
                    unit_id=unit.unit_id,
                    unit_name=unit.name or unit.unit_id,
                    enemy_group_id=enemy_group.group_id,
                    enemy_group_name=enemy_group.name or enemy_group.group_id,
                    seconds_remaining=display_seconds(combat.seconds_remaining) or 0,
                )
            )
        return tuple(snapshots)

    def combat_notifications(
        self,
        notifications: Sequence[CombatNotificationState],
        *,
        display_seconds: DisplaySeconds,
    ) -> tuple[CombatNotificationSnapshot, ...]:
        return tuple(
            CombatNotificationSnapshot(
                notification_id=notification.notification_id,
                unit_name=notification.unit_name,
                enemy_group_name=notification.enemy_group_name,
                phase=notification.phase,
                seconds_remaining=display_seconds(notification.seconds_remaining) or 0,
            )
            for notification in reversed(notifications)
        )

    def landing_pads(
        self,
        landing_pads: Mapping[str, LandingPadState],
        *,
        objective_status: Mapping[str, bool],
        resource_order: Sequence[str],
        display_seconds: DisplaySeconds,
    ) -> tuple[LandingPadSnapshot, ...]:
        snapshots: list[LandingPadSnapshot] = []
        for object_id in sorted(landing_pads):
            landing_pad = landing_pads[object_id]
            active_transport = landing_pad.active_transport
            snapshots.append(
                LandingPadSnapshot(
                    object_id=landing_pad.object_id,
                    pad_size=landing_pad.pad_size,
                    is_secured=landing_pad.is_secured(objective_status),
                    capacity=landing_pad.capacity,
                    total_stored=landing_pad.total_stored(resource_order=resource_order),
                    next_transport_seconds=display_seconds(landing_pad.next_transport_eta_seconds),
                    active_transport_type_id=(
                        active_transport.transport_type_id if active_transport is not None else None
                    ),
                    active_transport_phase=active_transport.phase if active_transport is not None else None,
                    active_transport_seconds_remaining=(
                        display_seconds(active_transport.seconds_remaining)
                        if active_transport is not None
                        else None
                    ),
                    resources=tuple(
                        LandingPadResourceSnapshot(
                            resource_id=resource_id,
                            amount=int(landing_pad.resources.get(resource_id, 0)),
                        )
                        for resource_id in resource_order
                    ),
                )
            )
        return tuple(snapshots)

    def supply_transports(
        self,
        landing_pads: Mapping[str, LandingPadState],
    ) -> tuple[SupplyTransportSnapshot, ...]:
        snapshots: list[SupplyTransportSnapshot] = []
        for object_id in sorted(landing_pads):
            active_transport = landing_pads[object_id].active_transport
            if active_transport is None:
                continue
            snapshots.append(
                SupplyTransportSnapshot(
                    transport_id=active_transport.transport_id,
                    transport_type_id=active_transport.transport_type_id,
                    phase=active_transport.phase,
                    position=active_transport.position,
                    target_object_id=active_transport.target_object_id,
                )
            )
        return tuple(snapshots)

    def supply_route_endpoints(
        self,
        endpoints: Mapping[str, SupplyRouteEndpoint],
    ) -> tuple[SupplyRouteEndpointSnapshot, ...]:
        return tuple(
            SupplyRouteEndpointSnapshot(
                object_id=endpoint.object_id,
                location_type=endpoint.location_type,
                can_dispatch_supplies=endpoint.can_dispatch_supplies,
                can_receive_supplies=endpoint.can_receive_supplies,
                is_active=endpoint.is_active,
            )
            for endpoint in sorted(
                endpoints.values(),
                key=lambda endpoint: endpoint.object_id,
            )
        )

    def objective_progress(
        self,
        objective_status: Mapping[str, bool],
    ) -> tuple[MissionObjectiveProgressSnapshot, ...]:
        return tuple(
            MissionObjectiveProgressSnapshot(
                objective_id=objective_id,
                completed=completed,
            )
            for objective_id, completed in objective_status.items()
        )

    def game_state(
        self,
        *,
        map_objects: Sequence[dict[str, Any]],
        roads: tuple[RoadSnapshot, ...],
        units: Sequence[dict[str, Any]],
        enemy_groups: tuple[ZombieGroupSnapshot, ...],
        selected_unit_id: str | None,
        objective_definitions: Sequence[dict[str, str]],
        objective_progress: tuple[MissionObjectiveProgressSnapshot, ...],
        mission_reports: tuple[MissionReportSnapshot, ...],
        landing_pads: tuple[LandingPadSnapshot, ...],
        bases: tuple[BaseSnapshot, ...],
        supply_route_endpoints: tuple[SupplyRouteEndpointSnapshot, ...],
        supply_transports: tuple[SupplyTransportSnapshot, ...],
        supply_routes: tuple[SupplyRouteSnapshot, ...],
        combats: tuple[CombatSnapshot, ...],
        combat_notifications: tuple[CombatNotificationSnapshot, ...],
    ) -> GameStateSnapshot:
        return GameStateSnapshot(
            map_objects=tuple(
                MapObjectSnapshot(object_id=obj["id"], bounds=obj["bounds"])
                for obj in map_objects
            ),
            roads=roads,
            units=tuple(
                UnitSnapshot(
                    unit_id=unit["unit_id"],
                    unit_type_id=unit["unit_type_id"],
                    position=unit["position"],
                    target=unit["target"],
                    marker_size_px=unit["marker_size_px"],
                    name=unit["name"],
                    commander=UnitCommanderSnapshot(**unit["commander"]),
                    experience_level=unit["experience_level"],
                    personnel=unit["personnel"],
                    armament_key=unit["armament_key"],
                    attack=unit["attack"],
                    defense=unit["defense"],
                    morale=unit["morale"],
                    ammo=unit["ammo"],
                    rations=unit["rations"],
                    fuel=unit["fuel"],
                    can_transport_supplies=unit["can_transport_supplies"],
                    supply_capacity=unit["supply_capacity"],
                    carried_supply_total=unit["carried_supply_total"],
                    active_supply_route_id=unit["active_supply_route_id"],
                    is_in_combat=unit["is_in_combat"],
                    combat_seconds_remaining=unit["combat_seconds_remaining"],
                )
                for unit in units
            ),
            enemy_groups=enemy_groups,
            selected_unit_id=selected_unit_id,
            objective_definitions=tuple(
                MissionObjectiveDefinitionSnapshot(
                    objective_id=definition["objective_id"],
                    description_key=definition["description_key"],
                )
                for definition in objective_definitions
            ),
            objective_progress=objective_progress,
            mission_reports=mission_reports,
            landing_pads=landing_pads,
            bases=bases,
            supply_route_endpoints=supply_route_endpoints,
            supply_transports=supply_transports,
            supply_routes=supply_routes,
            combats=combats,
            combat_notifications=combat_notifications,
        )
