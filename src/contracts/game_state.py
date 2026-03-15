from __future__ import annotations

from dataclasses import dataclass

type Bounds = tuple[int, int, int, int]
type Position = tuple[float, float]


@dataclass(frozen=True)
class MapObjectSnapshot:
    object_id: str
    bounds: Bounds


@dataclass(frozen=True)
class RoadSnapshot:
    road_id: str
    points: tuple[Position, ...]


@dataclass(frozen=True)
class UnitSnapshot:
    unit_id: str
    unit_type_id: str
    position: Position
    target: Position | None
    marker_size_px: int
    can_transport_supplies: bool = False
    supply_capacity: int = 0
    carried_supply_total: int = 0
    active_supply_route_id: str | None = None


@dataclass(frozen=True)
class MissionObjectiveDefinitionSnapshot:
    objective_id: str
    description_key: str


@dataclass(frozen=True)
class MissionObjectiveProgressSnapshot:
    objective_id: str
    completed: bool


@dataclass(frozen=True)
class LandingPadResourceSnapshot:
    resource_id: str
    amount: int


@dataclass(frozen=True)
class LandingPadSnapshot:
    object_id: str
    pad_size: str
    is_secured: bool
    capacity: int
    total_stored: int
    next_transport_seconds: int | None
    active_transport_type_id: str | None
    active_transport_phase: str | None
    active_transport_seconds_remaining: int | None
    resources: tuple[LandingPadResourceSnapshot, ...]


@dataclass(frozen=True)
class BaseSnapshot:
    object_id: str
    capacity: int
    total_stored: int
    resources: tuple[LandingPadResourceSnapshot, ...]


@dataclass(frozen=True)
class SupplyTransportSnapshot:
    transport_id: str
    transport_type_id: str
    phase: str
    position: Position
    target_object_id: str


@dataclass(frozen=True)
class SupplyRouteSnapshot:
    route_id: str
    unit_id: str
    source_object_id: str
    destination_object_id: str
    phase: str
    carried_total: int
    capacity: int


@dataclass(frozen=True)
class GameStateSnapshot:
    map_objects: tuple[MapObjectSnapshot, ...]
    units: tuple[UnitSnapshot, ...]
    selected_unit_id: str | None
    objective_definitions: tuple[MissionObjectiveDefinitionSnapshot, ...]
    objective_progress: tuple[MissionObjectiveProgressSnapshot, ...]
    roads: tuple[RoadSnapshot, ...] = ()
    landing_pads: tuple[LandingPadSnapshot, ...] = ()
    bases: tuple[BaseSnapshot, ...] = ()
    supply_transports: tuple[SupplyTransportSnapshot, ...] = ()
    supply_routes: tuple[SupplyRouteSnapshot, ...] = ()
