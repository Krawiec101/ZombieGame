from core.navigation import RoadGeometryService


def test_build_roads_resolves_relative_and_object_center_points() -> None:
    service = RoadGeometryService(samples_per_segment=2)

    roads = service.build_roads(
        (
            {
                "id": 17,
                "control_points": (
                    {"anchor_x": 0.1, "anchor_y": 0.2},
                    {"point_type": "map_object_center", "object_id": "hq"},
                ),
            },
        ),
        map_objects=({"id": "hq", "bounds": (400, 100, 600, 150)},),
        map_size=(1200, 1100),
    )

    assert roads[0]["id"] == "17"
    assert roads[0]["points"][0] == (120.0, 220.0)
    assert roads[0]["points"][-1] == (500.0, 125.0)


def test_build_roads_skips_missing_object_and_incomplete_road() -> None:
    service = RoadGeometryService(samples_per_segment=2)
    layouts = (
        {
            "id": "missing",
            "control_points": (
                {"anchor_x": 0.0, "anchor_y": 0.0},
                {"point_type": "map_object_center", "object_id": "missing"},
            ),
        },
        {"id": "short", "control_points": ({"anchor_x": 0.1, "anchor_y": 0.2},)},
    )

    assert service.build_roads(layouts, map_objects=(), map_size=(100, 100)) == []


def test_build_roads_samples_multisegment_curve_and_deduplicates_points() -> None:
    service = RoadGeometryService(samples_per_segment=4)

    roads = service.build_roads(
        (
            {
                "id": "curve",
                "control_points": (
                    {"anchor_x": 0.0, "anchor_y": 0.0},
                    {"anchor_x": 0.0, "anchor_y": 0.0},
                    {"anchor_x": 0.5, "anchor_y": 1.0},
                    {"anchor_x": 1.0, "anchor_y": 0.0},
                ),
            },
        ),
        map_objects=(),
        map_size=(100, 100),
    )

    points = roads[0]["points"]
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (100.0, 0.0)
    assert len(points) < 13
    assert all(0.0 <= x <= 100.0 and 0.0 <= y <= 100.0 for x, y in points)


def test_build_roads_does_not_clamp_curve_for_invalid_map_size() -> None:
    service = RoadGeometryService(samples_per_segment=2)

    roads = service.build_roads(
        (
            {
                "id": "road",
                "control_points": (
                    {"anchor_x": 1.0, "anchor_y": 1.0},
                    {"anchor_x": 2.0, "anchor_y": 2.0},
                ),
            },
        ),
        map_objects=(),
        map_size=(0, 0),
    )

    assert roads[0]["points"] == ((0.0, 0.0),)
