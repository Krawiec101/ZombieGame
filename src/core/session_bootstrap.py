from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.combat import ZombieGroupState
from core.model.units import (
    CommanderState,
    FormationLevel,
    ReinforcementTemplate,
    UnitEquipmentState,
    UnitOrganizationState,
    UnitState,
    VehicleAssignmentState,
)


def commander_state_from_config(config: Mapping[str, Any]) -> CommanderState:
    return CommanderState(
        name=str(config.get("name", "")),
        rank=str(config.get("rank", "")),
        experience_level=str(config.get("experience_level", "basic")),
    )


def equipment_state_from_config(config: Mapping[str, Any]) -> UnitEquipmentState:
    return UnitEquipmentState(
        primary_weapon_key=str(config.get("primary_weapon_key", "")),
        support_weapon_key=str(config.get("support_weapon_key", "")),
        vest_key=str(config.get("vest_key", "")),
    )


def vehicle_assignments_from_config(value: Any) -> tuple[VehicleAssignmentState, ...]:
    if not isinstance(value, list):
        return ()
    assignments: list[VehicleAssignmentState] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        assignments.append(
            VehicleAssignmentState(
                vehicle_type_id=str(item.get("vehicle_type_id", "")),
                count=int(item.get("count", 0)),
            )
        )
    return tuple(assignments)


def organization_state_from_config(config: Mapping[str, Any]) -> UnitOrganizationState:
    return UnitOrganizationState(
        formation_level=str(config.get("formation_level", FormationLevel.SQUAD)),
        parent_unit_id=(
            str(config["parent_unit_id"])
            if "parent_unit_id" in config and config.get("parent_unit_id") is not None
            else None
        ),
        subordinate_unit_ids=tuple(str(unit_id) for unit_id in config.get("subordinate_unit_ids", [])),
        max_subordinate_units=int(config.get("max_subordinate_units", 0)),
    )


def reinforcement_templates_from_config(
    reinforcements: Sequence[Mapping[str, Any]],
) -> tuple[ReinforcementTemplate, ...]:
    return tuple(
        ReinforcementTemplate(
            unit_id=str(template.get("unit_id", "")),
            unit_type_id=str(template.get("unit_type_id", "")),
            name=str(template.get("name", "")),
            commander=commander_state_from_config(dict(template.get("commander", {}))),
            experience_level=str(template.get("experience_level", "basic")),
            personnel=int(template.get("personnel", 0)),
            morale=int(template.get("morale", 0)),
            ammo=int(template.get("ammo", 0)),
            rations=int(template.get("rations", 0)),
            fuel=int(template.get("fuel", 0)),
            equipment=equipment_state_from_config(dict(template.get("equipment", {}))),
            vehicles=vehicle_assignments_from_config(template.get("vehicles")),
            organization=organization_state_from_config(dict(template.get("organization", {}))),
        )
        for template in reinforcements
    )


@dataclass
class SessionBootstrapState:
    units: list[UnitState]
    enemy_groups: list[ZombieGroupState]


MapObjectBoundsResolver = Callable[[str], tuple[int, int, int, int] | None]
MapObjectCenterResolver = Callable[[str], tuple[float, float]]
RoadAnchorResolver = Callable[[tuple[float, float]], tuple[float, float]]
UnitPointClamp = Callable[[tuple[float, float], str], tuple[float, float]]
EnemyPointClamp = Callable[[tuple[float, float]], tuple[float, float]]


@dataclass(frozen=True)
class SessionBootstrapper:
    def spawn_position_from_layout(
        self,
        layout: Mapping[str, Any],
        *,
        map_object_bounds: MapObjectBoundsResolver,
        map_object_center: MapObjectCenterResolver,
    ) -> tuple[float, float] | None:
        anchor_object_id = str(layout.get("anchor_object_id", ""))
        if not anchor_object_id:
            return None
        if map_object_bounds(anchor_object_id) is None:
            return None
        anchor_x, anchor_y = map_object_center(anchor_object_id)
        return (
            anchor_x + float(layout.get("offset_x", 0.0)),
            anchor_y + float(layout.get("offset_y", 0.0)),
        )

    def initialize_runtime_state(
        self,
        *,
        initial_unit_layout: Sequence[Mapping[str, Any]],
        initial_enemy_group_layout: Sequence[Mapping[str, Any]],
        map_object_bounds: MapObjectBoundsResolver,
        map_object_center: MapObjectCenterResolver,
        road_anchor_for_point: RoadAnchorResolver,
        clamp_unit_point: UnitPointClamp,
        clamp_enemy_point: EnemyPointClamp,
    ) -> SessionBootstrapState:
        units: list[UnitState] = []
        for unit_layout in initial_unit_layout:
            position = self.spawn_position_from_layout(
                unit_layout,
                map_object_bounds=map_object_bounds,
                map_object_center=map_object_center,
            )
            if position is None:
                continue
            if bool(unit_layout.get("snap_to_road", False)):
                position = road_anchor_for_point(position)

            commander_config = unit_layout.get("commander")
            equipment_config = unit_layout.get("equipment")
            organization_config = unit_layout.get("organization")
            unit_type_id = str(unit_layout.get("unit_type_id", ""))
            units.append(
                UnitState(
                    unit_id=str(unit_layout.get("unit_id", "")),
                    unit_type_id=unit_type_id,
                    position=clamp_unit_point(position, unit_type_id),
                    name=str(unit_layout.get("name", "")),
                    commander=commander_state_from_config(
                        dict(commander_config) if isinstance(commander_config, dict) else {}
                    ),
                    experience_level=str(unit_layout.get("experience_level", "basic")),
                    personnel=int(unit_layout.get("personnel", 0)),
                    morale=int(unit_layout.get("morale", 0)),
                    ammo=int(unit_layout.get("ammo", 0)),
                    rations=int(unit_layout.get("rations", 0)),
                    fuel=int(unit_layout.get("fuel", 0)),
                    equipment=equipment_state_from_config(
                        dict(equipment_config) if isinstance(equipment_config, dict) else {}
                    ),
                    vehicles=vehicle_assignments_from_config(unit_layout.get("vehicles")),
                    organization=organization_state_from_config(
                        dict(organization_config) if isinstance(organization_config, dict) else {}
                    ),
                )
            )

        enemy_groups: list[ZombieGroupState] = []
        for group_layout in initial_enemy_group_layout:
            position = self.spawn_position_from_layout(
                group_layout,
                map_object_bounds=map_object_bounds,
                map_object_center=map_object_center,
            )
            if position is None:
                continue
            enemy_groups.append(
                ZombieGroupState(
                    group_id=str(group_layout.get("group_id", "")),
                    position=clamp_enemy_point(position),
                    name=str(group_layout.get("name", "")),
                    personnel=int(group_layout.get("personnel", 0)),
                )
            )

        return SessionBootstrapState(units=units, enemy_groups=enemy_groups)

    def spawn_reinforcement(
        self,
        template: ReinforcementTemplate,
        *,
        site_id: str,
        map_object_center: MapObjectCenterResolver,
        clamp_unit_point: UnitPointClamp,
    ) -> UnitState:
        return UnitState(
            unit_id=template.unit_id,
            unit_type_id=template.unit_type_id,
            position=clamp_unit_point(map_object_center(site_id), template.unit_type_id),
            name=template.name,
            commander=template.commander,
            experience_level=template.experience_level,
            personnel=template.personnel,
            morale=template.morale,
            ammo=template.ammo,
            rations=template.rations,
            fuel=template.fuel,
            equipment=template.equipment,
            vehicles=template.vehicles,
            organization=template.organization,
        )
