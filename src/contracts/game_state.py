from __future__ import annotations

from dataclasses import dataclass

type Bounds = tuple[int, int, int, int]
type Position = tuple[float, float]


@dataclass(frozen=True)
class MapObjectSnapshot:
    object_id: str
    bounds: Bounds


@dataclass(frozen=True)
class UnitSnapshot:
    unit_id: str
    unit_type_id: str
    position: Position
    target: Position | None
    marker_size_px: int


@dataclass(frozen=True)
class MissionObjectiveDefinitionSnapshot:
    objective_id: str
    description_key: str


@dataclass(frozen=True)
class MissionObjectiveProgressSnapshot:
    objective_id: str
    completed: bool


@dataclass(frozen=True)
class GameStateSnapshot:
    map_objects: tuple[MapObjectSnapshot, ...]
    units: tuple[UnitSnapshot, ...]
    selected_unit_id: str | None
    objective_definitions: tuple[MissionObjectiveDefinitionSnapshot, ...]
    objective_progress: tuple[MissionObjectiveProgressSnapshot, ...]
