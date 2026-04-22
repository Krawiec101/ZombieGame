from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from contracts.game_state import MapObjectSnapshot, RoadSnapshot, SupplyRouteSnapshot


def map_object_center(map_objects: Sequence[MapObjectSnapshot], object_id: str) -> tuple[float, float]:
    map_object = next((item for item in map_objects if item.object_id == object_id), None)
    if map_object is None:
        return (0.0, 0.0)
    left, top, right, bottom = map_object.bounds
    return ((left + right) / 2.0, (top + bottom) / 2.0)


def supply_route_points(
    route: SupplyRouteSnapshot,
    *,
    map_objects: Sequence[MapObjectSnapshot],
    roads: Sequence[RoadSnapshot],
) -> tuple[tuple[float, float], ...]:
    start = map_object_center(map_objects, route.source_object_id)
    end = map_object_center(map_objects, route.destination_object_id)
    if not roads:
        return (start, end)

    road_points = roads[0].points
    if len(road_points) < 2:
        return (start, end)

    start_anchor = road_anchor_for_point(start, road_points)
    end_anchor = road_anchor_for_point(end, road_points)
    start_index = road_points.index(start_anchor)
    end_index = road_points.index(end_anchor)
    if start_index <= end_index:
        return road_points[start_index : end_index + 1]
    return tuple(reversed(road_points[end_index : start_index + 1]))


def road_anchor_for_point(
    point: tuple[float, float],
    road_points: Sequence[tuple[float, float]],
) -> tuple[float, float]:
    return min(
        road_points,
        key=lambda road_point: math.hypot(road_point[0] - point[0], road_point[1] - point[1]),
    )


def polyline_midpoint(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]

    segment_lengths = [
        math.hypot(end[0] - start[0], end[1] - start[1])
        for start, end in zip(points, points[1:], strict=False)
    ]
    total_length = sum(segment_lengths)
    if total_length <= 0:
        return points[len(points) // 2]

    halfway = total_length / 2.0
    traveled = 0.0
    for index, segment_length in enumerate(segment_lengths):
        if traveled + segment_length >= halfway:
            start = points[index]
            end = points[index + 1]
            progress = 0.0 if segment_length <= 0 else (halfway - traveled) / segment_length
            return (
                start[0] + (end[0] - start[0]) * progress,
                start[1] + (end[1] - start[1]) * progress,
            )
        traveled += segment_length

    return points[-1]


def point_in_bounds(position: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    x, y = position
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def first_map_object_at(
    position: tuple[int, int],
    map_objects: Iterable[MapObjectSnapshot],
) -> MapObjectSnapshot | None:
    return next((map_object for map_object in map_objects if point_in_bounds(position, map_object.bounds)), None)
