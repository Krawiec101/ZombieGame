from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.model.units import UnitState

PositionsMatch = Callable[..., bool]
PointClamp = Callable[[tuple[float, float] | tuple[int, int], str], tuple[float, float]]
Roads = Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class NavigationService:
    simulation_seconds_per_tick: float
    map_width_km: float

    def road_mode_for_unit(
        self,
        unit_type_id: str,
        *,
        can_unit_type_create_convoy: Callable[[str], bool],
    ) -> str:
        if can_unit_type_create_convoy(unit_type_id):  # pragma: no mutate
            return "prefer"  # pragma: no mutate
        return "off"  # pragma: no mutate

    def primary_road_points(self, roads: Roads) -> tuple[tuple[float, float], ...]:
        if not roads:  # pragma: no mutate
            return ()  # pragma: no mutate
        return tuple(roads[0].get("points", ()))  # pragma: no mutate

    def road_anchor_for_point(
        self,
        point: tuple[float, float],
        *,
        roads: Roads,
    ) -> tuple[float, float]:
        road_points = self.primary_road_points(roads)  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return point  # pragma: no mutate
        return min(
            road_points,
            key=lambda road_point: math.hypot(road_point[0] - point[0], road_point[1] - point[1]),
        )

    def road_points_between(
        self,
        start_anchor: tuple[float, float],
        destination_anchor: tuple[float, float],
        *,
        roads: Roads,
    ) -> list[tuple[float, float]]:
        road_points = self.primary_road_points(roads)  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return []  # pragma: no mutate

        start_index = road_points.index(start_anchor)  # pragma: no mutate
        destination_index = road_points.index(destination_anchor)  # pragma: no mutate
        if start_index <= destination_index:  # pragma: no mutate
            return list(road_points[start_index : destination_index + 1])  # pragma: no mutate
        return list(reversed(road_points[destination_index : start_index + 1]))  # pragma: no mutate

    def plan_unit_path(
        self,
        start: tuple[float, float],
        destination: tuple[float, float],
        *,
        road_mode: str,
        roads: Roads,
        positions_match: PositionsMatch,
        deduplicate_points: Callable[[Sequence[tuple[float, float]]], Sequence[tuple[float, float]]],
    ) -> list[tuple[float, float]]:
        if road_mode == "off" or not roads:  # pragma: no mutate
            return [destination]  # pragma: no mutate

        road_points = self.primary_road_points(roads)  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return [destination]  # pragma: no mutate

        start_anchor = self.road_anchor_for_point(start, roads=roads)  # pragma: no mutate
        destination_anchor = self.road_anchor_for_point(destination, roads=roads)  # pragma: no mutate
        path: list[tuple[float, float]] = []  # pragma: no mutate

        if road_mode == "prefer" and not positions_match(start, start_anchor, tolerance=2.0):
            path.append(start_anchor)  # pragma: no mutate

        path.extend(self.road_points_between(start_anchor, destination_anchor, roads=roads))  # pragma: no mutate

        if not path or not positions_match(path[-1], destination_anchor, tolerance=2.0):
            path.append(destination_anchor)  # pragma: no mutate

        if not positions_match(path[-1], destination, tolerance=2.0):
            path.append(destination)  # pragma: no mutate

        return list(deduplicate_points(path))  # pragma: no mutate

    def set_unit_target(
        self,
        unit: UnitState,
        destination: tuple[float, float] | tuple[int, int],
        *,
        road_mode: str,
        roads: Roads,
        clamp_point_to_map: PointClamp,
        positions_match: Callable[..., bool],
        deduplicate_points: Callable[[Sequence[tuple[float, float]]], Sequence[tuple[float, float]]],
    ) -> None:
        final_target = clamp_point_to_map(destination, unit.unit_type_id)
        path = self.plan_unit_path(
            unit.position,
            final_target,
            road_mode=road_mode,
            roads=roads,
            positions_match=positions_match,
            deduplicate_points=deduplicate_points,
        )
        unit.set_movement_target(
            final_target,
            path=path,
            positions_match=positions_match,
        )

    def pixels_per_tick_from_speed_kmph(
        self,
        speed_kmph: float,
        *,
        map_width_px: int,
    ) -> float:
        if map_width_px <= 0:
            return 0.0
        km_per_tick = (speed_kmph / 3600.0) * self.simulation_seconds_per_tick
        km_per_pixel = self.map_width_km / float(map_width_px)
        if km_per_pixel <= 0:
            return 0.0
        return km_per_tick / km_per_pixel

    def movement_pixels_per_tick(
        self,
        unit_type_id: str,
        *,
        map_width_px: int,
        base_speed_kmph: Callable[[str], float],
    ) -> float:
        return self.pixels_per_tick_from_speed_kmph(
            base_speed_kmph(unit_type_id),
            map_width_px=map_width_px,
        )

    def unit_movement_pixels_per_tick(
        self,
        unit: UnitState,
        *,
        map_width_px: int,
        unit_speed_kmph: Callable[[UnitState], float],
    ) -> float:
        return self.pixels_per_tick_from_speed_kmph(
            unit_speed_kmph(unit),
            map_width_px=map_width_px,
        )
