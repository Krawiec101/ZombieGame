from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoadGeometryService:
    samples_per_segment: int

    def build_roads(
        self,
        road_layouts: Sequence[Mapping[str, Any]],
        *,
        map_objects: Sequence[Mapping[str, Any]],
        map_size: tuple[int, int],
    ) -> list[dict[str, Any]]:
        roads: list[dict[str, Any]] = []
        for road_layout in road_layouts:
            control_points: list[tuple[float, float]] = []
            for control_point in road_layout.get("control_points", []):
                resolved_point = self._resolve_control_point(
                    dict(control_point), map_objects=map_objects, map_size=map_size
                )
                if resolved_point is None:
                    control_points = []
                    break
                control_points.append(resolved_point)
            if len(control_points) < 2:
                continue
            roads.append(
                {
                    "id": str(road_layout.get("id", "")),
                    "points": self._sample_curve(tuple(control_points), map_size=map_size),
                }
            )
        return roads

    def _resolve_control_point(
        self,
        control_point: Mapping[str, Any],
        *,
        map_objects: Sequence[Mapping[str, Any]],
        map_size: tuple[int, int],
    ) -> tuple[float, float] | None:
        if str(control_point.get("point_type", "relative_map_point")) == "map_object_center":
            object_id = str(control_point.get("object_id", ""))
            map_object = next((item for item in map_objects if item.get("id") == object_id), None)
            if map_object is None:
                return None
            bounds = map_object.get("bounds")
            if not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
                return None
            left, top, right, bottom = bounds
            return ((float(left) + float(right)) / 2.0, (float(top) + float(bottom)) / 2.0)

        width, height = map_size
        return (
            width * float(control_point.get("anchor_x", 0.0)),
            height * float(control_point.get("anchor_y", 0.0)),
        )

    def _sample_curve(
        self,
        control_points: tuple[tuple[float, float], ...],
        *,
        map_size: tuple[int, int],
    ) -> tuple[tuple[float, float], ...]:
        if len(control_points) < 2:
            return control_points

        sampled_points: list[tuple[float, float]] = []
        for index in range(len(control_points) - 1):
            p0 = control_points[index - 1] if index > 0 else control_points[index]
            p1 = control_points[index]
            p2 = control_points[index + 1]
            p3 = control_points[index + 2] if index + 2 < len(control_points) else p2
            for sample_index in range(self.samples_per_segment):
                t = sample_index / float(self.samples_per_segment)
                sampled_points.append(self._catmull_rom_point(p0, p1, p2, p3, t, map_size=map_size))

        sampled_points.append(control_points[-1])
        return tuple(self._deduplicate_points(sampled_points))

    def _catmull_rom_point(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
        t: float,
        *,
        map_size: tuple[int, int],
    ) -> tuple[float, float]:
        t2 = t * t
        t3 = t2 * t
        x = 0.5 * (
            2.0 * p1[0]
            + (-p0[0] + p2[0]) * t
            + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
        )
        y = 0.5 * (
            2.0 * p1[1]
            + (-p0[1] + p2[1]) * t
            + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
        )
        return self._clamp_point((x, y), map_size=map_size)

    @staticmethod
    def _clamp_point(point: tuple[float, float], *, map_size: tuple[int, int]) -> tuple[float, float]:
        width, height = map_size
        if width <= 0 or height <= 0:
            return point
        return (
            min(max(float(point[0]), 0.0), float(width)),
            min(max(float(point[1]), 0.0), float(height)),
        )

    @staticmethod
    def _deduplicate_points(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
        deduplicated: list[tuple[float, float]] = []
        for point in points:
            if deduplicated:
                previous = deduplicated[-1]
                if ((previous[0] - point[0]) ** 2 + (previous[1] - point[1]) ** 2) ** 0.5 <= 0.1:
                    continue
            deduplicated.append(point)
        return deduplicated
