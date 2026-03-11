from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class MissionObjectiveRule:
    objective_id: str
    description_key: str
    required_unit_type_id: str
    target_object_id: str


DEFAULT_MISSION_OBJECTIVE_RULES: tuple[MissionObjectiveRule, ...] = (
    MissionObjectiveRule(
        objective_id="motorized_to_landing_pad",
        description_key="mission.objective.motorized_to_landing_pad",
        required_unit_type_id="motorized_infantry_squad",
        target_object_id="landing_pad",
    ),
)


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

    def evaluate(
        self,
        *,
        units: Sequence[dict[str, object]],
        map_objects: Sequence[dict[str, object]],
        current_status: Mapping[str, bool],
    ) -> dict[str, bool]:
        statuses = {rule.objective_id: bool(current_status.get(rule.objective_id, False)) for rule in self._rules}
        object_bounds_by_id = {
            str(map_object["id"]): tuple(map_object["bounds"]) for map_object in map_objects if "bounds" in map_object
        }

        for rule in self._rules:
            if statuses[rule.objective_id]:
                continue

            bounds = object_bounds_by_id.get(rule.target_object_id)
            if not bounds or len(bounds) != 4:
                continue

            left, top, right, bottom = (int(bounds[0]), int(bounds[1]), int(bounds[2]), int(bounds[3]))
            for unit in units:
                unit_type_id = str(unit.get("unit_type_id", ""))
                if unit_type_id != rule.required_unit_type_id:
                    continue

                position = unit.get("position")
                if not isinstance(position, (tuple, list)) or len(position) < 2:
                    continue
                x = float(position[0])
                y = float(position[1])
                if left <= x <= right and top <= y <= bottom:
                    statuses[rule.objective_id] = True
                    break

        return statuses


def create_default_mission_objectives_evaluator() -> MissionObjectivesEvaluator:
    return MissionObjectivesEvaluator(DEFAULT_MISSION_OBJECTIVE_RULES)
