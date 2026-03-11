from __future__ import annotations

import math

from core.game_session import UNIT_TYPE_SPECS, UnitState, create_default_game_session


def _unit_by_id(units: list[dict[str, object]], unit_id: str) -> dict[str, object]:
    return next(unit for unit in units if unit["unit_id"] == unit_id)


def _unit_center(unit: dict[str, object]) -> tuple[int, int]:
    x, y = unit["position"]
    return (int(float(x)), int(float(y)))


def test_game_session_initializes_map_objects_and_units() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    map_object_ids = {obj["id"] for obj in session.map_objects_snapshot()}
    unit_type_ids = {unit["unit_type_id"] for unit in session.units_snapshot()}
    assert map_object_ids == {"hq", "landing_pad"}
    assert unit_type_ids == {"infantry_squad", "motorized_infantry_squad"}


def test_left_click_selects_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))

    assert session.selected_unit_id() == "alpha_infantry"


def test_left_click_on_map_issues_order_for_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    assert updated_infantry["target"] is not None


def test_left_click_without_selection_does_not_issue_order() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    initial_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click((840, 500))
    for _ in range(60):
        session.tick()

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert updated_infantry["target"] is None
    assert updated_infantry["position"] == initial_infantry["position"]


def test_right_click_deselects_without_clearing_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    target_before = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]

    session.handle_right_click((20, 20))

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert session.selected_unit_id() is None
    assert updated_infantry["target"] == target_before


def test_motorized_squad_moves_faster_than_foot_infantry() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    motorized = _unit_by_id(session.units_snapshot(), "bravo_motorized")

    target = (40, 40)
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click(target)
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(target)
    infantry_start = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_start = _unit_by_id(session.units_snapshot(), "bravo_motorized")["position"]

    for _ in range(120):
        session.tick()

    infantry_now = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_now = _unit_by_id(session.units_snapshot(), "bravo_motorized")["position"]
    infantry_distance = math.hypot(
        float(infantry_now[0]) - float(infantry_start[0]),
        float(infantry_now[1]) - float(infantry_start[1]),
    )
    motorized_distance = math.hypot(
        float(motorized_now[0]) - float(motorized_start[0]),
        float(motorized_now[1]) - float(motorized_start[1]),
    )

    assert (
        UNIT_TYPE_SPECS["motorized_infantry_squad"].speed_kmph
        > UNIT_TYPE_SPECS["infantry_squad"].speed_kmph
    )
    assert motorized_distance > infantry_distance * 2


def test_objective_completed_only_by_motorized_squad_on_landing_pad() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]
    center = ((left + right) // 2, (top + bottom) // 2)
    motorized_target = (min(right - 10, center[0] + 18), center[1])

    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click(center)
    for _ in range(3000):
        session.tick()
        if _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"] is None:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is False

    motorized = _unit_by_id(session.units_snapshot(), "bravo_motorized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(motorized_target)
    for _ in range(3000):
        session.tick()
        if _unit_by_id(session.units_snapshot(), "bravo_motorized")["target"] is None:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is True


def test_reset_clears_units_selection_and_objective_progress() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_motorized")
    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]
    center = ((left + right) // 2, (top + bottom) // 2)

    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(center)
    for _ in range(3000):
        session.tick()
        if session.objective_status_snapshot()["motorized_to_landing_pad"]:
            break
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is True

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.selected_unit_id() is None
    assert session.objective_status_snapshot()["motorized_to_landing_pad"] is False


def test_update_map_dimensions_ignores_non_positive_values() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=0, height=640)
    session.update_map_dimensions(width=960, height=0)
    session.update_map_dimensions(width=-1, height=100)

    assert session.map_objects_snapshot() == []
    assert session.units_snapshot() == []
    assert session.selected_unit_id() is None


def test_update_map_dimensions_builds_expected_map_layout_and_rebuilds_on_resize() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=1000, height=500)
    first_layout = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    assert first_layout["hq"] == (178, 262, 262, 318)
    assert first_layout["landing_pad"] == (744, 146, 816, 194)

    session.update_map_dimensions(width=2000, height=1000)
    resized_layout = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    assert resized_layout["hq"] == (398, 552, 482, 608)
    assert resized_layout["landing_pad"] == (1524, 316, 1596, 364)
    assert resized_layout != first_layout


def test_update_map_dimensions_clamps_unit_position_and_target_after_resize() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    motorized = _unit_by_id(session.units_snapshot(), "bravo_motorized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((955, 635))

    session.update_map_dimensions(width=120, height=90)
    motorized_after_resize = _unit_by_id(session.units_snapshot(), "bravo_motorized")

    min_x = UNIT_TYPE_SPECS["motorized_infantry_squad"].marker_size_px / 2
    max_x = 120 - min_x
    min_y = UNIT_TYPE_SPECS["motorized_infantry_squad"].marker_size_px / 2
    max_y = 90 - min_y

    x, y = motorized_after_resize["position"]
    assert min_x <= float(x) <= max_x
    assert min_y <= float(y) <= max_y

    assert motorized_after_resize["target"] is not None
    target_x, target_y = motorized_after_resize["target"]
    assert min_x <= float(target_x) <= max_x
    assert min_y <= float(target_y) <= max_y


def test_update_map_dimensions_same_size_does_not_reclamp_existing_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    target_before = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]
    assert target_before is not None

    session.update_map_dimensions(width=960, height=640)
    target_after = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]

    assert target_after == target_before


def test_units_snapshot_contains_expected_keys_marker_sizes_and_targets() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    units = session.units_snapshot()

    assert units
    for unit in units:
        assert set(unit.keys()) == {
            "unit_id",
            "unit_type_id",
            "position",
            "target",
            "marker_size_px",
        }
        assert unit["marker_size_px"] == UNIT_TYPE_SPECS[unit["unit_type_id"]].marker_size_px

    updated_infantry = _unit_by_id(units, "alpha_infantry")
    assert updated_infantry["target"] == (840.0, 500.0)


def test_reset_clears_runtime_state_but_keeps_map_layout() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    map_layout_before_reset = session.map_objects_snapshot()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_motorized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((840, 500))
    assert _unit_by_id(session.units_snapshot(), "bravo_motorized")["target"] is not None

    session.reset()

    assert session.units_snapshot() == []
    assert session.selected_unit_id() is None
    assert session.map_objects_snapshot() == map_layout_before_reset
    assert session.objective_status_snapshot() == {"motorized_to_landing_pad": False}


def test_reset_allows_reinitialization_without_resizing_map() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    assert session.units_snapshot()

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.units_snapshot()


def test_init_sets_expected_internal_defaults() -> None:
    session = create_default_game_session()

    assert session._map_size == (0, 0)
    assert session._map_objects == []
    assert session._units == []
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._objective_status == {"motorized_to_landing_pad": False}
    assert session._objective_definitions == (
        {
            "objective_id": "motorized_to_landing_pad",
            "description_key": "mission.objective.motorized_to_landing_pad",
        },
    )


def test_reset_restores_internal_runtime_state_to_defaults() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))

    session.reset()

    assert session._units == []
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._objective_status == {"motorized_to_landing_pad": False}


def test_update_map_dimensions_coerces_dimensions_to_ints() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=960.9, height=640.4)

    assert session._map_size == (960, 640)
    assert session.map_objects_snapshot()


def test_update_map_dimensions_rebuilds_map_when_objects_missing_even_without_size_change() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    first_layout = session.map_objects_snapshot()
    session._map_objects = []

    session.update_map_dimensions(width=960, height=640)

    assert session.map_objects_snapshot() == first_layout


def test_build_map_objects_preserves_configured_object_sizes() -> None:
    session = create_default_game_session()

    objects = session._build_map_objects(960, 640)
    layout_by_id = {obj["id"]: obj["bounds"] for obj in objects}

    hq_left, hq_top, hq_right, hq_bottom = layout_by_id["hq"]
    assert (hq_right - hq_left, hq_bottom - hq_top) == (84, 56)

    pad_left, pad_top, pad_right, pad_bottom = layout_by_id["landing_pad"]
    assert (pad_right - pad_left, pad_bottom - pad_top) == (72, 48)


def test_initialize_units_sets_expected_unit_ids_and_offsets_from_hq_center() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    hq = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "hq")
    left, top, right, bottom = hq["bounds"]
    center = ((left + right) / 2.0, (top + bottom) / 2.0)
    units = {unit["unit_id"]: unit for unit in session.units_snapshot()}

    assert set(units) == {"alpha_infantry", "bravo_motorized"}
    alpha_x, alpha_y = units["alpha_infantry"]["position"]
    bravo_x, bravo_y = units["bravo_motorized"]["position"]
    assert (alpha_x, alpha_y) == (center[0] - 22.0, center[1] + 8.0)
    assert (bravo_x, bravo_y) == (center[0] + 26.0, center[1] + 8.0)


def test_initialize_units_keeps_units_within_map_after_clamp_on_small_map() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=40, height=40)
    units = session.units_snapshot()
    assert units

    for unit in units:
        half_size = unit["marker_size_px"] / 2
        x, y = unit["position"]
        assert half_size <= float(x) <= 40 - half_size
        assert half_size <= float(y) <= 40 - half_size


def test_update_units_position_clears_target_when_distance_is_within_step() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="motorized_infantry_squad",
            position=(100.0, 100.0),
            target=(101.0, 100.0),
        ),
    ]

    session._update_units_position()

    assert session._units[0].position == (101.0, 100.0)
    assert session._units[0].target is None


def test_update_units_position_moves_unit_by_expected_step_towards_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(100.0, 100.0),
            target=(200.0, 100.0),
        ),
    ]
    expected_step = session._movement_pixels_per_tick("infantry_squad")

    session._update_units_position()

    moved_x, moved_y = session._units[0].position
    assert moved_y == 100.0
    assert moved_x == 100.0 + expected_step
    assert session._units[0].target == (200.0, 100.0)


def test_update_units_position_skips_movement_when_speed_is_zero() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(100.0, 100.0),
            target=(200.0, 100.0),
        ),
    ]
    session._movement_pixels_per_tick = lambda _unit_type_id: 0.0

    session._update_units_position()

    assert session._units[0].position == (100.0, 100.0)
    assert session._units[0].target == (200.0, 100.0)


def test_movement_pixels_per_tick_returns_zero_for_non_positive_width() -> None:
    session = create_default_game_session()
    session._map_size = (0, 640)

    assert session._movement_pixels_per_tick("infantry_squad") == 0.0


def test_movement_pixels_per_tick_matches_expected_formula() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)

    speed = UNIT_TYPE_SPECS["infantry_squad"].speed_kmph
    km_per_tick = (speed / 3600.0) * 8.0
    km_per_pixel = 20.0 / 960.0
    expected = km_per_tick / km_per_pixel

    assert session._movement_pixels_per_tick("infantry_squad") == expected


def test_point_in_map_boundaries_are_inclusive() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)

    assert session._point_in_map((0, 0)) is True
    assert session._point_in_map((960, 640)) is True
    assert session._point_in_map((961, 640)) is False
    assert session._point_in_map((960, 641)) is False
    assert session._point_in_map((-1, 0)) is False
    assert session._point_in_map((0, -1)) is False


def test_find_unit_at_prefers_last_unit_when_bounds_overlap() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
        UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    clicked = session._find_unit_at((100, 100))

    assert clicked is not None
    assert clicked.unit_id == "u2"


def test_find_unit_at_returns_none_for_position_outside_all_units() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    assert session._find_unit_at((300, 300)) is None


def test_unit_bounds_are_computed_from_center_and_marker_size() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="motorized_infantry_squad", position=(100.8, 100.2))

    bounds = session._unit_bounds(unit)

    assert bounds == (90, 90, 110, 110)


def test_clamp_point_to_map_returns_float_input_when_map_size_invalid() -> None:
    session = create_default_game_session()
    session._map_size = (0, 0)

    clamped = session._clamp_point_to_map((12, 34), unit_type_id="infantry_squad")

    assert clamped == (12.0, 34.0)


def test_clamp_point_to_map_clamps_below_and_above_bounds() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)

    clamped_low = session._clamp_point_to_map((-100, -50), unit_type_id="motorized_infantry_squad")
    clamped_high = session._clamp_point_to_map((999, 999), unit_type_id="motorized_infantry_squad")
    half_size = UNIT_TYPE_SPECS["motorized_infantry_squad"].marker_size_px / 2

    assert clamped_low == (half_size, half_size)
    assert clamped_high == (120 - half_size, 90 - half_size)


def test_get_selected_unit_returns_unit_and_keeps_selection_when_found() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "u1"

    selected = session._get_selected_unit()

    assert selected is not None
    assert selected.unit_id == "u1"
    assert session._selected_unit_id == "u1"


def test_get_selected_unit_returns_none_and_clears_invalid_selection() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "missing"

    selected = session._get_selected_unit()

    assert selected is None
    assert session._selected_unit_id is None
