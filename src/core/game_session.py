from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from contracts.game_state import (
    GameStateSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    UnitSnapshot,
)
from core.mission_objectives import (
    MissionObjectivesEvaluator,
    create_default_mission_objectives_evaluator,
)

_MAP_WIDTH_KM = 20.0
_SIMULATION_SECONDS_PER_TICK = 8.0

_MAP_OBJECT_LAYOUT = (
    {"id": "hq", "anchor_x": 0.22, "anchor_y": 0.58, "width": 84, "height": 56},
    {"id": "landing_pad", "anchor_x": 0.78, "anchor_y": 0.34, "width": 72, "height": 48},
)


@dataclass(frozen=True)
class UnitTypeSpec:
    type_id: str
    speed_kmph: float
    marker_size_px: int


@dataclass
class UnitState:
    unit_id: str
    unit_type_id: str
    position: tuple[float, float]
    target: tuple[float, float] | None = None


UNIT_TYPE_SPECS: dict[str, UnitTypeSpec] = {
    "infantry_squad": UnitTypeSpec(
        type_id="infantry_squad",
        speed_kmph=4.2,
        marker_size_px=18,
    ),
    "motorized_infantry_squad": UnitTypeSpec(
        type_id="motorized_infantry_squad",
        speed_kmph=18.0,
        marker_size_px=20,
    ),
}


class GameSession:
    def __init__(self, *, mission_objectives_evaluator: MissionObjectivesEvaluator) -> None:
        self._mission_objectives_evaluator = mission_objectives_evaluator
        self._objective_definitions = tuple(self._mission_objectives_evaluator.objectives())
        self._objective_status = {
            definition["objective_id"]: False for definition in self._objective_definitions
        }

        self._map_size: tuple[int, int] = (0, 0)
        self._map_objects: list[dict[str, Any]] = []
        self._units: list[UnitState] = []
        self._selected_unit_id: str | None = None
        self._units_initialized = False

    def reset(self) -> None:
        self._units = []
        self._selected_unit_id = None
        self._units_initialized = False
        self._objective_status = {
            definition["objective_id"]: False for definition in self._objective_definitions
        }

    def update_map_dimensions(self, *, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return

        new_size = (int(width), int(height))
        map_size_changed = new_size != self._map_size
        self._map_size = new_size
        if map_size_changed or not self._map_objects:
            self._map_objects = self._build_map_objects(*self._map_size)

        if not self._units_initialized:
            self._initialize_units()
        elif map_size_changed:
            for unit in self._units:
                unit.position = self._clamp_point_to_map(unit.position, unit_type_id=unit.unit_type_id)
                if unit.target is not None:
                    unit.target = self._clamp_point_to_map(unit.target, unit_type_id=unit.unit_type_id)

    def tick(self) -> None:
        self._update_units_position()
        self._objective_status = self._mission_objectives_evaluator.evaluate(
            units=self.units_snapshot(),
            map_objects=self.map_objects_snapshot(),
            current_status=self._objective_status,
        )

    def sync_state(self, *, width: int, height: int) -> GameStateSnapshot:
        self.update_map_dimensions(width=width, height=height)
        self.tick()
        return self.snapshot()

    def handle_left_click(self, position: tuple[int, int]) -> None:
        if not self._point_in_map(position):
            return

        clicked_unit = self._find_unit_at(position)
        if clicked_unit is not None:
            self._selected_unit_id = clicked_unit.unit_id
            return

        selected_unit = self._get_selected_unit()
        if selected_unit is None:
            return

        selected_unit.target = self._clamp_point_to_map(position, unit_type_id=selected_unit.unit_type_id)

    def handle_right_click(self, _position: tuple[int, int]) -> None:
        if self._get_selected_unit() is None:
            return
        self._selected_unit_id = None

    def map_objects_snapshot(self) -> list[dict[str, Any]]:
        return [{"id": obj["id"], "bounds": obj["bounds"]} for obj in self._map_objects]

    def units_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "unit_id": unit.unit_id,
                "unit_type_id": unit.unit_type_id,
                "position": unit.position,
                "target": unit.target,
                "marker_size_px": UNIT_TYPE_SPECS[unit.unit_type_id].marker_size_px,
            }
            for unit in self._units
        ]

    def objective_status_snapshot(self) -> dict[str, bool]:
        return dict(self._objective_status)

    def objective_definitions_snapshot(self) -> tuple[dict[str, str], ...]:
        return self._objective_definitions

    def objective_progress_snapshot(self) -> tuple[MissionObjectiveProgressSnapshot, ...]:
        return tuple(
            MissionObjectiveProgressSnapshot(
                objective_id=objective_id,
                completed=completed,
            )
            for objective_id, completed in self._objective_status.items()
        )

    def selected_unit_id(self) -> str | None:
        return self._selected_unit_id

    def snapshot(self) -> GameStateSnapshot:
        return GameStateSnapshot(
            map_objects=tuple(
                MapObjectSnapshot(object_id=obj["id"], bounds=obj["bounds"])
                for obj in self.map_objects_snapshot()
            ),
            units=tuple(
                UnitSnapshot(
                    unit_id=unit["unit_id"],
                    unit_type_id=unit["unit_type_id"],
                    position=unit["position"],
                    target=unit["target"],
                    marker_size_px=unit["marker_size_px"],
                )
                for unit in self.units_snapshot()
            ),
            selected_unit_id=self.selected_unit_id(),
            objective_definitions=tuple(
                MissionObjectiveDefinitionSnapshot(
                    objective_id=definition["objective_id"],
                    description_key=definition["description_key"],
                )
                for definition in self.objective_definitions_snapshot()
            ),
            objective_progress=self.objective_progress_snapshot(),
        )

    def _build_map_objects(self, width: int, height: int) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        for layout in _MAP_OBJECT_LAYOUT:
            center_x = int(width * layout["anchor_x"])
            center_y = int(height * layout["anchor_y"])
            half_width = layout["width"] // 2
            half_height = layout["height"] // 2
            left = center_x - half_width
            top = center_y - half_height
            right = left + layout["width"]
            bottom = top + layout["height"]
            objects.append({"id": layout["id"], "bounds": (left, top, right, bottom)})
        return objects

    def _initialize_units(self) -> None:
        hq = next((obj for obj in self._map_objects if obj["id"] == "hq"), None)
        if hq is None:
            return

        hq_left, hq_top, hq_right, hq_bottom = hq["bounds"]
        hq_center = ((hq_left + hq_right) / 2.0, (hq_top + hq_bottom) / 2.0)
        self._units = [
            UnitState(
                unit_id="alpha_infantry",
                unit_type_id="infantry_squad",
                position=(hq_center[0] - 22.0, hq_center[1] + 8.0),
            ),
            UnitState(
                unit_id="bravo_motorized",
                unit_type_id="motorized_infantry_squad",
                position=(hq_center[0] + 26.0, hq_center[1] + 8.0),
            ),
        ]
        for unit in self._units:
            unit.position = self._clamp_point_to_map(unit.position, unit_type_id=unit.unit_type_id)
        self._units_initialized = True

    def _update_units_position(self) -> None:
        for unit in self._units:
            if unit.target is None:
                continue

            speed_px_per_tick = self._movement_pixels_per_tick(unit.unit_type_id)
            if speed_px_per_tick <= 0:
                continue

            current_x, current_y = unit.position
            target_x, target_y = unit.target
            delta_x = target_x - current_x
            delta_y = target_y - current_y
            distance = math.hypot(delta_x, delta_y)

            if distance <= speed_px_per_tick:
                unit.position = unit.target
                unit.target = None
                continue

            step = speed_px_per_tick / distance
            moved_x = current_x + delta_x * step
            moved_y = current_y + delta_y * step
            unit.position = self._clamp_point_to_map((moved_x, moved_y), unit_type_id=unit.unit_type_id)

    def _movement_pixels_per_tick(self, unit_type_id: str) -> float:
        width, _height = self._map_size
        if width <= 0:
            return 0.0
        speed_kmph = UNIT_TYPE_SPECS[unit_type_id].speed_kmph
        km_per_tick = (speed_kmph / 3600.0) * _SIMULATION_SECONDS_PER_TICK
        km_per_pixel = _MAP_WIDTH_KM / float(width)
        if km_per_pixel <= 0:
            return 0.0
        return km_per_tick / km_per_pixel

    def _point_in_map(self, position: tuple[int, int]) -> bool:
        width, height = self._map_size
        x, y = position
        return 0 <= x <= width and 0 <= y <= height

    def _find_unit_at(self, position: tuple[int, int]) -> UnitState | None:
        x, y = position
        for unit in reversed(self._units):
            left, top, right, bottom = self._unit_bounds(unit)
            if left <= x <= right and top <= y <= bottom:
                return unit
        return None

    def _unit_bounds(self, unit: UnitState) -> tuple[int, int, int, int]:
        size = UNIT_TYPE_SPECS[unit.unit_type_id].marker_size_px
        left = int(unit.position[0] - size / 2)
        top = int(unit.position[1] - size / 2)
        right = left + size
        bottom = top + size
        return (left, top, right, bottom)

    def _clamp_point_to_map(
        self,
        position: tuple[float, float] | tuple[int, int],
        *,
        unit_type_id: str,
    ) -> tuple[float, float]:
        width, height = self._map_size
        if width <= 0 or height <= 0:
            return (float(position[0]), float(position[1]))

        half_size = UNIT_TYPE_SPECS[unit_type_id].marker_size_px / 2
        min_x = half_size
        max_x = width - half_size
        min_y = half_size
        max_y = height - half_size
        clamped_x = min(max(float(position[0]), min_x), max_x)
        clamped_y = min(max(float(position[1]), min_y), max_y)
        return (clamped_x, clamped_y)

    def _get_selected_unit(self) -> UnitState | None:
        if self._selected_unit_id is None:
            return None
        for unit in self._units:
            if unit.unit_id == self._selected_unit_id:
                return unit
        self._selected_unit_id = None
        return None


def create_default_game_session() -> GameSession:
    return GameSession(mission_objectives_evaluator=create_default_mission_objectives_evaluator())
