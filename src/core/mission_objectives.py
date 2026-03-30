from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from core.scenario_config import load_default_scenario_config


@dataclass(frozen=True)
class MissionObjectiveRule:
    objective_id: str
    description_key: str
    required_unit_type_id: str = ""
    target_object_id: str = ""
    objective_type: str = "unit_on_object"
    source_object_id: str = ""
    destination_object_id: str = ""
    required_reinforcements_found: int = 0


def _load_default_mission_objective_rules() -> tuple[MissionObjectiveRule, ...]:
    scenario = load_default_scenario_config()
    return tuple(
        MissionObjectiveRule(
            objective_id=str(rule.get("objective_id", "")),
            description_key=str(rule.get("description_key", "")),
            required_unit_type_id=str(rule.get("required_unit_type_id", "")),
            target_object_id=str(rule.get("target_object_id", "")),
            objective_type=str(rule.get("objective_type", "unit_on_object")),
            source_object_id=str(rule.get("source_object_id", "")),
            destination_object_id=str(rule.get("destination_object_id", "")),
            required_reinforcements_found=int(rule.get("required_reinforcements_found", 0)),
        )
        for rule in scenario.mission_objectives
    )


DEFAULT_MISSION_OBJECTIVE_RULES: tuple[MissionObjectiveRule, ...] = _load_default_mission_objective_rules()


class MissionObjectivesEvaluator:
    def __init__(self, rules: Sequence[MissionObjectiveRule]) -> None:
        self._rules = tuple(rules)

    def objectives(self) -> tuple[dict[str, str], ...]:
        return tuple(
            {
                "objective_id": rule.objective_id,
                "description_key": rule.description_key,
            }
            for rule in self._rules
        )

    def evaluate(  # pragma: no mutate
        self,
        *,
        units: Sequence[dict[str, object]],
        map_objects: Sequence[dict[str, object]],
        current_status: Mapping[str, bool],
        supply_routes: Sequence[dict[str, object]] = (),
        enemy_groups: Sequence[dict[str, object]] = (),
        discovered_reinforcements_count: int = 0,
    ) -> dict[str, bool]:
        statuses = {  # pragma: no mutate
            rule.objective_id: bool(current_status.get(rule.objective_id, False))
            for rule in self._rules
        }
        object_bounds_by_id = {  # pragma: no mutate
            str(map_object["id"]): tuple(map_object["bounds"]) for map_object in map_objects if "bounds" in map_object
        }

        for rule in self._rules:
            if statuses[rule.objective_id]:
                continue

            if rule.objective_type == "enemy_absent_from_object":
                statuses[rule.objective_id] = self._enemy_absent_from_object(
                    target_object_id=rule.target_object_id,
                    enemy_groups=enemy_groups,
                    object_bounds_by_id=object_bounds_by_id,
                )
                continue

            if rule.objective_type == "supply_route_established":
                statuses[rule.objective_id] = self._supply_route_established(
                    supply_routes=supply_routes,
                    source_object_id=rule.source_object_id,
                    destination_object_id=rule.destination_object_id,
                )
                continue

            if rule.objective_type == "reinforcements_found":
                statuses[rule.objective_id] = (
                    int(discovered_reinforcements_count) >= int(rule.required_reinforcements_found)
                )
                continue

            statuses[rule.objective_id] = self._unit_on_object(
                units=units,
                required_unit_type_id=rule.required_unit_type_id,
                target_object_id=rule.target_object_id,
                object_bounds_by_id=object_bounds_by_id,
            )

        return statuses

    def _unit_on_object(
        self,
        *,
        units: Sequence[dict[str, object]],
        required_unit_type_id: str,
        target_object_id: str,
        object_bounds_by_id: Mapping[str, tuple[object, ...]],
    ) -> bool:
        bounds = object_bounds_by_id.get(target_object_id)
        if not bounds or len(bounds) != 4:
            return False

        left, top, right, bottom = (int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
        for unit in units:
            unit_type_id = str(unit.get("unit_type_id", ""))
            if unit_type_id != required_unit_type_id:
                continue

            position = unit.get("position")
            if not isinstance(position, (tuple, list)) or len(position) < 2:
                continue
            x = float(position[0])
            y = float(position[1])
            if left <= x <= right and top <= y <= bottom:  # pragma: no mutate
                return True

        return False

    def _enemy_absent_from_object(
        self,
        *,
        target_object_id: str,
        enemy_groups: Sequence[dict[str, object]],
        object_bounds_by_id: Mapping[str, tuple[object, ...]],
    ) -> bool:
        bounds = object_bounds_by_id.get(target_object_id)
        if not bounds or len(bounds) != 4:
            return False

        left, top, right, bottom = (int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
        for enemy_group in enemy_groups:
            position = enemy_group.get("position")
            if not isinstance(position, (tuple, list)) or len(position) < 2:
                continue
            x = float(position[0])
            y = float(position[1])
            if left <= x <= right and top <= y <= bottom:
                return False

        return True

    def _supply_route_established(
        self,
        *,
        supply_routes: Sequence[dict[str, object]],
        source_object_id: str,
        destination_object_id: str,
    ) -> bool:
        for supply_route in supply_routes:
            if str(supply_route.get("source_object_id", "")) != source_object_id:
                continue
            if str(supply_route.get("destination_object_id", "")) != destination_object_id:
                continue
            return True
        return False


def create_default_mission_objectives_evaluator() -> MissionObjectivesEvaluator:
    return MissionObjectivesEvaluator(DEFAULT_MISSION_OBJECTIVE_RULES)
