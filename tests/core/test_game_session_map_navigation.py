# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_create_default_game_session_preserves_injected_providers() -> None:
    def clock() -> float:
        return 123.0

    def roll() -> float:
        return 0.25

    session = create_default_game_session(
        time_provider=clock,
        search_roll_provider=roll,
    )

    assert session._time_provider is clock
    assert session._search_roll_provider is roll

def test_build_roads_skips_invalid_layouts_and_resolves_control_points(monkeypatch) -> None:
    session = create_default_game_session()
    session._map_size = (1000, 500)
    session._map_objects = [
        {"id": "hq", "bounds": (100, 200, 140, 240)},
    ]
    monkeypatch.setattr(
        "core.game_session._ROAD_LAYOUTS",
        (
            {
                "id": 17,
                "control_points": [
                    {"point_type": "map_object_center", "object_id": "hq"},
                    {"anchor_x": 0.5, "anchor_y": 0.25},
                ],
            },
            {
                "id": "missing_object",
                "control_points": [
                    {"point_type": "map_object_center", "object_id": "missing"},
                    {"anchor_x": 1.0, "anchor_y": 1.0},
                ],
            },
            {
                "id": "too_short",
                "control_points": [{"anchor_x": 0.1, "anchor_y": 0.2}],
            },
        ),
    )

    roads = session._build_roads()

    assert [road["id"] for road in roads] == ["17"]
    assert roads[0]["points"][0] == (120.0, 220.0)
    assert roads[0]["points"][-1] == (500.0, 125.0)

def test_spawn_position_from_layout_requires_anchor_and_applies_default_offsets() -> None:
    session = create_default_game_session()
    session._map_objects = [{"id": "hq", "bounds": (10, 20, 30, 40)}]

    assert session._spawn_position_from_layout({}) is None
    assert session._spawn_position_from_layout({"anchor_object_id": "missing"}) is None
    assert session._spawn_position_from_layout({"anchor_object_id": "hq"}) == (20.0, 30.0)
    assert session._spawn_position_from_layout(
        {"anchor_object_id": "hq", "offset_x": 5, "offset_y": -3}
    ) == (25.0, 27.0)

def test_initialize_units_applies_defaults_coercion_and_skips_invalid_layouts(monkeypatch) -> None:
    session = create_default_game_session()
    session._map_size = (200, 200)
    session._map_objects = [{"id": "hq", "bounds": (80, 80, 120, 120)}]
    session._roads = [{"id": "road", "points": ((105.0, 106.0), (110.0, 111.0))}]
    monkeypatch.setattr(
        "core.game_session._INITIAL_UNIT_LAYOUT",
        (
            {
                "anchor_object_id": "hq",
                "offset_x": 4,
                "offset_y": 5,
                "snap_to_road": True,
                "unit_type_id": "mechanized_squad",
            },
            {
                "unit_id": 7,
                "unit_type_id": "infantry_squad",
                "anchor_object_id": "hq",
                "offset_x": "-6",
                "offset_y": "8",
                "name": 9,
                "commander": {"experience_level": 3},
                "experience_level": 2,
                "personnel": "11",
                "morale": "12",
                "ammo": "13",
                "rations": "14",
                "fuel": "15",
                "equipment": {"primary_weapon_key": "rifle", "vest_key": "plate"},
                "vehicles": [{"vehicle_type_id": "wheeled_apc", "count": "1"}],
                "organization": {"formation_level": "squad", "max_subordinate_units": "3"},
            },
            {
                "unit_id": "ignored",
                "unit_type_id": "infantry_squad",
            },
        ),
    )
    monkeypatch.setattr(
        "core.game_session._INITIAL_ENEMY_GROUP_LAYOUT",
        (
            {
                "anchor_object_id": "hq",
                "offset_x": 1,
                "offset_y": 2,
            },
            {
                "group_id": 9,
                "anchor_object_id": "hq",
                "offset_x": "-1",
                "offset_y": "-2",
                "name": 8,
                "personnel": "7",
            },
        ),
    )

    session._initialize_units()

    assert session._units_initialized is True
    assert session._units == [
        UnitState(
            unit_id="",
            unit_type_id="mechanized_squad",
            position=(105.0, 106.0),
            name="",
            commander=CommanderState(name="", experience_level="basic"),
            experience_level="basic",
            personnel=0,
            morale=0,
            ammo=0,
            rations=0,
            fuel=0,
        ),
        UnitState(
            unit_id="7",
            unit_type_id="infantry_squad",
            position=(94.0, 108.0),
            name="9",
            commander=CommanderState(name="", experience_level="3"),
            experience_level="2",
            personnel=11,
            morale=12,
            ammo=13,
            rations=14,
            fuel=15,
            equipment=UnitEquipmentState(primary_weapon_key="rifle", vest_key="plate"),
            vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),),
            organization=UnitOrganizationState(max_subordinate_units=3),
        ),
    ]
    assert session._enemy_groups == [
        ZombieGroupState(group_id="", position=(101.0, 102.0), name="", personnel=0),
        ZombieGroupState(group_id="9", position=(99.0, 98.0), name="8", personnel=7),
    ]

def test_map_object_bounds_and_point_in_bounds_handle_invalid_shapes_and_edges() -> None:
    session = create_default_game_session()
    session._map_objects = [
        {"id": "good", "bounds": (1, 2, 3, 4)},
        {"id": "bad_type", "bounds": [1, 2, 3, 4]},
        {"id": "bad_len", "bounds": (1, 2, 3)},
    ]

    assert session._map_object_bounds("good") == (1, 2, 3, 4)
    assert session._map_object_bounds("bad_type") is None
    assert session._map_object_bounds("bad_len") is None
    assert session._map_object_bounds("missing") is None
    assert session._point_in_bounds((1, 2), (1, 2, 3, 4)) is True
    assert session._point_in_bounds((3, 4), (1, 2, 3, 4)) is True
    assert session._point_in_bounds((0, 2), (1, 2, 3, 4)) is False
    assert session._point_in_bounds((1, 5), (1, 2, 3, 4)) is False

def test_mechanized_unit_prefers_road_when_ordered_to_move() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None

    session.handle_left_click(_unit_center(_unit_by_id(session.units_snapshot(), "bravo_mechanized")))
    session.handle_left_click((880, 480))

    assert motorized.target == (880.0, 480.0)
    assert len(motorized.path) > 2
    assert motorized.path[-1] == (880.0, 480.0)
    assert any(point in _road_snapshot(session).points for point in motorized.path[:-1])

def test_motorized_squad_moves_faster_than_foot_infantry() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    target = (40, 40)
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click(target)
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click(target)
    infantry_start = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_start = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["position"]

    for _ in range(120):
        session.tick()

    infantry_now = _unit_by_id(session.units_snapshot(), "alpha_infantry")["position"]
    motorized_now = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["position"]
    infantry_distance = math.hypot(
        float(infantry_now[0]) - float(infantry_start[0]),
        float(infantry_now[1]) - float(infantry_start[1]),
    )
    motorized_distance = math.hypot(
        float(motorized_now[0]) - float(motorized_start[0]),
        float(motorized_now[1]) - float(motorized_start[1]),
    )

    assert (
        UNIT_TYPE_SPECS["mechanized_squad"].speed_kmph
        > UNIT_TYPE_SPECS["infantry_squad"].speed_kmph
    )
    assert motorized_distance > infantry_distance * 2

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

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((955, 635))

    session.update_map_dimensions(width=120, height=90)
    motorized_after_resize = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    min_x = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2
    max_x = 120 - min_x
    min_y = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2
    max_y = 90 - min_y

    x, y = motorized_after_resize["position"]
    assert min_x <= float(x) <= max_x
    assert min_y <= float(y) <= max_y

    if motorized_after_resize["target"] is not None:
        target_x, target_y = motorized_after_resize["target"]
        assert min_x <= float(target_x) <= max_x
        assert min_y <= float(target_y) <= max_y
    else:
        assert (float(x), float(y)) == (max_x, max_y)

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

def test_reset_clears_runtime_state_but_keeps_map_layout() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    map_layout_before_reset = session.map_objects_snapshot()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_left_click((840, 500))
    assert _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] is not None

    session.reset()

    assert session.units_snapshot() == []
    assert session.selected_unit_id() is None
    assert session.map_objects_snapshot() == map_layout_before_reset
    assert session.objective_status_snapshot() == {
        "landing_pad_cleared": False,
        "supply_route_to_hq": False,
        "find_first_missing_detachment": False,
        "find_second_missing_detachment": False,
    }

def test_reset_allows_reinitialization_without_resizing_map() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    assert session.units_snapshot()

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.units_snapshot()

def test_reset_rebuilds_roads_when_map_size_stays_the_same() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    roads_before_reset = session.roads_snapshot()

    session.reset()

    assert session.roads_snapshot() == ()

    session.update_map_dimensions(width=960, height=640)

    assert session.roads_snapshot() == roads_before_reset

def test_init_sets_expected_internal_defaults() -> None:
    session = create_default_game_session()

    assert session._map_size == (0, 0)
    assert session._map_objects == []
    assert session._bases == {}
    assert session._landing_pads == {}
    assert session._supply_routes == {}
    assert session._units == []
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._last_supply_update_at is None
    assert session._objective_status == {
        "landing_pad_cleared": False,
        "supply_route_to_hq": False,
        "find_first_missing_detachment": False,
        "find_second_missing_detachment": False,
    }
    assert session._objective_definitions == (
        {
            "objective_id": "landing_pad_cleared",
            "description_key": "mission.objective.landing_pad_cleared",
        },
        {
            "objective_id": "supply_route_to_hq",
            "description_key": "mission.objective.supply_route_to_hq",
        },
        {
            "objective_id": "find_first_missing_detachment",
            "description_key": "mission.objective.find_first_missing_detachment",
        },
        {
            "objective_id": "find_second_missing_detachment",
            "description_key": "mission.objective.find_second_missing_detachment",
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
    assert session._bases == {}
    assert session._landing_pads == {}
    assert session._supply_routes == {}
    assert session._selected_unit_id is None
    assert session._units_initialized is False
    assert session._last_supply_update_at is None
    assert session._objective_status == {
        "landing_pad_cleared": False,
        "supply_route_to_hq": False,
        "find_first_missing_detachment": False,
        "find_second_missing_detachment": False,
    }

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

def test_build_map_objects_keeps_integer_bounds_for_odd_map_sizes() -> None:
    session = create_default_game_session()

    objects = session._build_map_objects(999, 501)

    assert objects
    for map_object in objects:
        assert all(isinstance(value, int) for value in map_object["bounds"])

def test_initialize_units_sets_expected_unit_ids_and_offsets_from_hq_center() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    hq = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "hq")
    left, top, right, bottom = hq["bounds"]
    center = ((left + right) / 2.0, (top + bottom) / 2.0)
    road_points = set(_road_snapshot(session).points)
    units = {unit["unit_id"]: unit for unit in session.units_snapshot()}

    assert set(units) == {"alpha_infantry", "bravo_mechanized"}
    alpha_x, alpha_y = units["alpha_infantry"]["position"]
    bravo_x, bravo_y = units["bravo_mechanized"]["position"]
    assert (alpha_x, alpha_y) == (center[0] - 22.0, center[1] + 8.0)
    assert (bravo_x, bravo_y) in road_points
    assert math.hypot(bravo_x - (center[0] + 26.0), bravo_y - (center[1] + 8.0)) < 16.0

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

def test_initialize_units_returns_early_when_hq_is_missing() -> None:
    session = create_default_game_session()
    session._map_objects = [{"id": "landing_pad", "bounds": (1, 2, 3, 4)}]

    session._initialize_units()

    assert session._units == []
    assert session._units_initialized is False

def test_update_units_position_clears_target_when_distance_is_within_step() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(100.0, 100.0),
            target=(101.0, 100.0),
        ),
    ]

    session._update_units_position()

    assert session._units[0].position == (101.0, 100.0)
    assert session._units[0].target is None

def test_update_units_position_reaches_exact_step_and_continues_updating_later_units() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(0.0, 0.0),
            target=(3.0, 4.0),
        ),
        UnitState(
            unit_id="u2",
            unit_type_id="infantry_squad",
            position=(10.0, 10.0),
            target=(20.0, 10.0),
        ),
    ]
    session._unit_movement_pixels_per_tick = lambda unit: 5.0 if unit.unit_type_id == "mechanized_squad" else 2.0

    session._update_units_position()

    assert session._units[0].position == (3.0, 4.0)
    assert session._units[0].target is None
    assert session._units[1].position == (12.0, 10.0)
    assert session._units[1].target == (20.0, 10.0)

def test_update_units_position_uses_both_axes_and_skips_zero_speed_without_stopping_loop() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._units = [
        UnitState(
            unit_id="slow",
            unit_type_id="infantry_squad",
            position=(100.0, 100.0),
            target=(200.0, 100.0),
        ),
        UnitState(
            unit_id="diag",
            unit_type_id="mechanized_squad",
            position=(20.0, 20.0),
            target=(23.0, 24.0),
        ),
    ]
    session._unit_movement_pixels_per_tick = lambda unit: 0.0 if unit.unit_type_id == "infantry_squad" else 4.0

    session._update_units_position()

    assert session._units[0].position == (100.0, 100.0)
    assert session._units[0].target == (200.0, 100.0)
    assert session._units[1].position == (22.4, 23.2)
    assert session._units[1].target == (23.0, 24.0)

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
    session._unit_movement_pixels_per_tick = lambda _unit: 0.0

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

def test_vehicle_bonus_helpers_ignore_unknown_types_and_negative_counts() -> None:
    session = create_default_game_session()
    mechanized = UnitState(
        unit_id="bravo",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        vehicles=(
            VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),
            VehicleAssignmentState(vehicle_type_id="unknown", count=4),
            VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=-3),
        ),
    )

    assert (
        session._unit_vehicle_speed_bonus_kmph(mechanized)
        == VEHICLE_TYPE_SPECS["wheeled_apc"].transport_speed_bonus_kmph
    )
    assert session._unit_vehicle_attack_bonus(mechanized) == VEHICLE_TYPE_SPECS["wheeled_apc"].attack_bonus
    assert session._unit_vehicle_defense_bonus(mechanized) == VEHICLE_TYPE_SPECS["wheeled_apc"].defense_bonus

def test_point_in_map_boundaries_are_inclusive() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)

    assert session._point_in_map((0, 0)) is True
    assert session._point_in_map((960, 640)) is True
    assert session._point_in_map((961, 640)) is False
    assert session._point_in_map((960, 641)) is False
    assert session._point_in_map((-1, 0)) is False
    assert session._point_in_map((0, -1)) is False

def test_find_unit_at_returns_none_for_position_outside_all_units() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    assert session._find_unit_at((300, 300)) is None

def test_unit_bounds_are_computed_from_center_and_marker_size() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(100.8, 100.2))

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

    clamped_low = session._clamp_point_to_map((-100, -50), unit_type_id="mechanized_squad")
    clamped_high = session._clamp_point_to_map((999, 999), unit_type_id="mechanized_squad")
    half_size = UNIT_TYPE_SPECS["mechanized_squad"].marker_size_px / 2

    assert clamped_low == (half_size, half_size)
    assert clamped_high == (120 - half_size, 90 - half_size)

def test_clamp_point_to_map_keeps_points_inside_bounds_unchanged() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)

    assert session._clamp_point_to_map((30, 40), unit_type_id="infantry_squad") == (30.0, 40.0)

def test_clamp_point_to_map_returns_original_point_when_either_dimension_is_invalid() -> None:
    session = create_default_game_session()

    session._map_size = (0, 90)
    assert session._clamp_point_to_map((12, 34), unit_type_id="infantry_squad") == (12.0, 34.0)

    session._map_size = (120, 0)
    assert session._clamp_point_to_map((56, 78), unit_type_id="mechanized_squad") == (56.0, 78.0)

def test_find_unit_at_includes_edges_of_unit_bounds() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0))
    session._units = [unit]
    left, top, right, bottom = session._unit_bounds(unit)

    assert session._find_unit_at((left, top)) is unit
    assert session._find_unit_at((right, bottom)) is unit

def test_display_seconds_rounds_up_and_clamps_negative_values() -> None:
    session = create_default_game_session()

    assert session._display_seconds(0.1) == 1
    assert session._display_seconds(-0.1) == 0
    assert session._display_seconds(None) is None

def test_update_map_dimensions_accepts_minimum_positive_dimensions() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=1, height=1)

    assert session.map_objects_snapshot()
    assert session.units_snapshot()

def test_set_unit_target_assigns_tuple_path_for_non_matching_destination() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0))

    session._set_unit_target(unit, (140.0, 100.0), road_mode="off")

    assert unit.target == (140.0, 100.0)
    assert unit.path == ((140.0, 100.0),)

def test_create_default_game_session_initializes_empty_roads_collection() -> None:
    session = create_default_game_session()

    assert session._roads == []

