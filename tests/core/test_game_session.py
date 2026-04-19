from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

from contracts.game_state import (
    BaseSnapshot,
    CombatNotificationSnapshot,
    CombatSnapshot,
    GameStateSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MissionObjectiveProgressSnapshot,
    MissionReportSnapshot,
    RoadSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)
from core.game_session import (
    MAIN_OBJECTIVE_REPORT_RULES,
    REINFORCEMENT_TEMPLATES,
    SUPPLY_TRANSPORT_TYPE_SPECS,
    UNIT_TYPE_SPECS,
    BaseState,
    CombatNotificationState,
    CombatState,
    CommanderState,
    LandingPadState,
    MainObjectiveReportRule,
    ReinforcementTemplate,
    SupplyRouteState,
    SupplyTransportState,
    SupplyTransportTypeSpec,
    UnitState,
    ZombieGroupState,
    _commander_state_from_config,
    _main_objective_report_rules_from_config,
    _reinforcement_templates_from_config,
    create_default_game_session,
)
from core.scenario_config import ScenarioConfig


def _unit_by_id(units: list[dict[str, object]], unit_id: str) -> dict[str, object]:
    return next(unit for unit in units if unit["unit_id"] == unit_id)


def _unit_center(unit: dict[str, object]) -> tuple[int, int]:
    x, y = unit["position"]
    return (int(float(x)), int(float(y)))


class _FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.current = start

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def _landing_pad_snapshot(session) -> LandingPadSnapshot:
    return session.landing_pads_snapshot()[0]


def _enemy_group_snapshot(session) -> ZombieGroupSnapshot:
    return session.enemy_groups_snapshot()[0]


def _road_snapshot(session) -> RoadSnapshot:
    return session.roads_snapshot()[0]


def _scenario_config_for_game_session_tests(
    *,
    reinforcements: Sequence[dict[str, object]] = (),
    mission_reports: Sequence[dict[str, object]] = (),
) -> ScenarioConfig:
    return ScenarioConfig(
        scenario_id="scenario",
        campaign_id="campaign",
        default_mission_id="mission_1",
        mission_id="mission_1",
        available_mission_ids=("mission_1",),
        next_mission_id="",
        default_stage_id="stage_1",
        stage_id="stage_1",
        available_stage_ids=("stage_1",),
        map_width_km=20.0,
        map_objects=(),
        recon_sites=(),
        roads=(),
        initial_units=(),
        initial_enemy_groups=(),
        reinforcements=tuple(reinforcements),
        mission_objectives=(),
        mission_reports=tuple(mission_reports),
        stage_events=(),
    )


def test_game_session_initializes_map_objects_and_units() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    map_object_ids = {obj["id"] for obj in session.map_objects_snapshot()}
    unit_type_ids = {unit["unit_type_id"] for unit in session.units_snapshot()}
    assert map_object_ids == {"hq", "landing_pad", "recon_site_1", "recon_site_2", "recon_site_3", "recon_site_4"}
    assert unit_type_ids == {"infantry_squad", "mechanized_squad"}
    assert session.enemy_groups_snapshot() == (
        ZombieGroupSnapshot(
            group_id="zulu_zombies",
            position=session.enemy_groups_snapshot()[0].position,
            marker_size_px=22,
            name="Mala grupa zombie",
            personnel=7,
        ),
    )


def test_commander_state_from_config_coerces_values_and_applies_basic_default() -> None:
    assert _commander_state_from_config({"name": 17}) == CommanderState(
        name="17",
        experience_level="basic",
    )
    assert _commander_state_from_config({"name": "sier. Ada", "experience_level": 2}) == CommanderState(
        name="sier. Ada",
        experience_level="2",
    )


def test_commander_state_from_config_uses_empty_name_when_field_is_missing() -> None:
    assert _commander_state_from_config({}) == CommanderState(
        name="",
        experience_level="basic",
    )


def test_reinforcement_templates_match_default_scenario_contract() -> None:
    expected_templates = (
        ReinforcementTemplate(
            unit_id="charlie_infantry",
            unit_type_id="infantry_squad",
            name="3. Druzyna Charlie",
            commander=CommanderState(name="sier. Lena Brzeg", experience_level="basic"),
            experience_level="basic",
            personnel=9,
            morale=68,
            ammo=74,
            rations=12,
            fuel=0,
        ),
        ReinforcementTemplate(
            unit_id="delta_infantry",
            unit_type_id="infantry_squad",
            name="4. Druzyna Delta",
            commander=CommanderState(name="sier. Oskar Lis", experience_level="basic"),
            experience_level="basic",
            personnel=8,
            morale=71,
            ammo=70,
            rations=10,
            fuel=0,
        ),
    )

    assert REINFORCEMENT_TEMPLATES == expected_templates
    assert _reinforcement_templates_from_config() == expected_templates


def test_reinforcement_templates_from_config_applies_defaults_and_coercion(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.game_session._DEFAULT_SCENARIO",
        _scenario_config_for_game_session_tests(
            reinforcements=(
                {
                    "personnel": "9",
                    "commander": {"name": 5},
                },
                {
                    "unit_id": 17,
                    "unit_type_id": 3,
                    "name": 9,
                    "commander": {"experience_level": 4},
                    "experience_level": 2,
                    "personnel": "11",
                    "morale": "12",
                    "ammo": "13",
                    "rations": "14",
                    "fuel": "15",
                },
            ),
        ),
    )

    assert _reinforcement_templates_from_config() == (
        ReinforcementTemplate(
            unit_id="",
            unit_type_id="",
            name="",
            commander=CommanderState(name="5", experience_level="basic"),
            experience_level="basic",
            personnel=9,
            morale=0,
            ammo=0,
            rations=0,
            fuel=0,
        ),
        ReinforcementTemplate(
            unit_id="17",
            unit_type_id="3",
            name="9",
            commander=CommanderState(name="", experience_level="4"),
            experience_level="2",
            personnel=11,
            morale=12,
            ammo=13,
            rations=14,
            fuel=15,
        ),
    )


def test_main_objective_report_rules_match_default_scenario_contract() -> None:
    expected_rules = (
        MainObjectiveReportRule(
            goal_id="secure_landing_pad_and_route",
            required_objective_ids=("landing_pad_cleared", "supply_route_to_hq"),
            report_id="hq_report_secure_landing_pad_and_route",
            title_key="mission.report.title",
            message_key="mission.report.secure_landing_pad_and_route",
        ),
        MainObjectiveReportRule(
            goal_id="find_first_missing_detachment",
            required_objective_ids=("find_first_missing_detachment",),
            report_id="hq_report_find_first_missing_detachment",
            title_key="mission.report.title",
            message_key="mission.report.find_first_missing_detachment",
        ),
        MainObjectiveReportRule(
            goal_id="find_second_missing_detachment",
            required_objective_ids=("find_second_missing_detachment",),
            report_id="hq_report_find_second_missing_detachment",
            title_key="mission.report.title",
            message_key="mission.report.find_second_missing_detachment",
        ),
    )

    assert MAIN_OBJECTIVE_REPORT_RULES == expected_rules
    assert _main_objective_report_rules_from_config() == expected_rules


def test_main_objective_report_rules_from_config_applies_defaults_and_coercion(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.game_session._DEFAULT_SCENARIO",
        _scenario_config_for_game_session_tests(
            mission_reports=(
                {},
                {
                    "goal_id": 12,
                    "required_objective_ids": [1, "two"],
                    "report_id": 13,
                    "title_key": 14,
                    "message_key": 15,
                },
            ),
        ),
    )

    assert _main_objective_report_rules_from_config() == (
        MainObjectiveReportRule(
            goal_id="",
            required_objective_ids=(),
            report_id="",
            title_key="",
            message_key="",
        ),
        MainObjectiveReportRule(
            goal_id="12",
            required_objective_ids=("1", "two"),
            report_id="13",
            title_key="14",
            message_key="15",
        ),
    )


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
    assert session._resolve_road_control_point({}) == (0.0, 0.0)
    assert session._resolve_road_control_point(
        {"point_type": "map_object_center", "object_id": "missing"}
    ) is None
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
        ),
    ]
    assert session._enemy_groups == [
        ZombieGroupState(group_id="", position=(101.0, 102.0), name="", personnel=0),
        ZombieGroupState(group_id="9", position=(99.0, 98.0), name="8", personnel=7),
    ]


def test_should_reveal_reinforcement_covers_false_forced_and_probability_paths(monkeypatch) -> None:
    session = create_default_game_session(search_roll_provider=lambda: 0.4)
    monkeypatch.setattr(
        "core.game_session._RECON_SITE_LAYOUT",
        (
            {"id": "site_1"},
            {"id": "site_2"},
            {"id": "site_3"},
        ),
    )
    monkeypatch.setattr(
        "core.game_session.REINFORCEMENT_TEMPLATES",
        (
            ReinforcementTemplate(
                unit_id="r1",
                unit_type_id="infantry_squad",
                name="R1",
                commander=CommanderState(),
                experience_level="basic",
                personnel=1,
                morale=1,
                ammo=1,
                rations=1,
                fuel=0,
            ),
            ReinforcementTemplate(
                unit_id="r2",
                unit_type_id="infantry_squad",
                name="R2",
                commander=CommanderState(),
                experience_level="basic",
                personnel=1,
                morale=1,
                ammo=1,
                rations=1,
                fuel=0,
            ),
        ),
    )

    session._found_reinforcement_unit_ids = {"r1", "r2"}
    assert session._should_reveal_reinforcement() is False

    session._found_reinforcement_unit_ids = set()
    session._investigated_recon_site_ids = {"site_1", "site_2"}
    assert session._should_reveal_reinforcement() is True

    session._found_reinforcement_unit_ids = {"r1"}
    session._investigated_recon_site_ids = set()
    assert session._should_reveal_reinforcement() is False

    session._search_roll_provider = lambda: 0.25
    assert session._should_reveal_reinforcement() is True


def test_spawn_next_reinforcement_copies_template_fields_and_marks_unit_found(monkeypatch) -> None:
    session = create_default_game_session()
    session._map_size = (200, 200)
    session._map_objects = [{"id": "site", "bounds": (90, 90, 110, 110)}]
    monkeypatch.setattr(
        "core.game_session.REINFORCEMENT_TEMPLATES",
        (
            ReinforcementTemplate(
                unit_id="first",
                unit_type_id="infantry_squad",
                name="First",
                commander=CommanderState(name="A", experience_level="basic"),
                experience_level="basic",
                personnel=1,
                morale=2,
                ammo=3,
                rations=4,
                fuel=5,
            ),
            ReinforcementTemplate(
                unit_id="second",
                unit_type_id="mechanized_squad",
                name="Second",
                commander=CommanderState(name="B", experience_level="elite"),
                experience_level="elite",
                personnel=6,
                morale=7,
                ammo=8,
                rations=9,
                fuel=10,
            ),
        ),
    )
    session._found_reinforcement_unit_ids = {"first"}

    session._spawn_next_reinforcement("site")
    session._spawn_next_reinforcement("site")

    assert session._found_reinforcement_unit_ids == {"first", "second"}
    assert session._units == [
        UnitState(
            unit_id="second",
            unit_type_id="mechanized_squad",
            position=(100.0, 100.0),
            name="Second",
            commander=CommanderState(name="B", experience_level="elite"),
            experience_level="elite",
            personnel=6,
            morale=7,
            ammo=8,
            rations=9,
            fuel=10,
        )
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


def test_update_main_objective_reports_adds_matching_report_only_once(monkeypatch) -> None:
    session = create_default_game_session()
    monkeypatch.setattr(
        "core.game_session.MAIN_OBJECTIVE_REPORT_RULES",
        (
            MainObjectiveReportRule(
                goal_id="goal",
                required_objective_ids=("a", "b"),
                report_id="report",
                title_key="title",
                message_key="message",
            ),
        ),
    )
    session._objective_status = {"a": True, "b": False}

    session._update_main_objective_reports()
    session._objective_status["b"] = True
    session._update_main_objective_reports()
    session._update_main_objective_reports()

    assert session._completed_main_objective_ids == {"goal"}
    assert session._mission_reports == [
        MissionReportSnapshot(
            report_id="report",
            title_key="title",
            message_key="message",
        )
    ]


def test_snapshot_exposes_typed_contract_for_ui_sync() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    snapshot = session.snapshot()

    assert isinstance(snapshot, GameStateSnapshot)
    assert {map_object.object_id for map_object in snapshot.map_objects} == {
        "hq",
        "landing_pad",
        "recon_site_1",
        "recon_site_2",
        "recon_site_3",
        "recon_site_4",
    }
    assert snapshot.roads == session.roads_snapshot()
    assert {unit.unit_type_id for unit in snapshot.units} == {
        "infantry_squad",
        "mechanized_squad",
    }
    assert snapshot.objective_progress == (
        MissionObjectiveProgressSnapshot(
            objective_id="landing_pad_cleared",
            completed=False,
        ),
        MissionObjectiveProgressSnapshot(
            objective_id="supply_route_to_hq",
            completed=False,
        ),
        MissionObjectiveProgressSnapshot(
            objective_id="find_first_missing_detachment",
            completed=False,
        ),
        MissionObjectiveProgressSnapshot(
            objective_id="find_second_missing_detachment",
            completed=False,
        ),
    )
    assert snapshot.landing_pads == (
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="small",
            is_secured=False,
            capacity=90,
            total_stored=0,
            next_transport_seconds=None,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=session.snapshot().landing_pads[0].resources,
        ),
    )
    assert snapshot.bases == (
        BaseSnapshot(
            object_id="hq",
            capacity=120,
            total_stored=0,
            resources=session.snapshot().bases[0].resources,
        ),
    )
    assert snapshot.supply_transports == ()
    assert snapshot.supply_routes == ()
    assert snapshot.enemy_groups == (
        ZombieGroupSnapshot(
            group_id="zulu_zombies",
            position=snapshot.enemy_groups[0].position,
            marker_size_px=22,
            name="Mala grupa zombie",
            personnel=7,
        ),
    )
    assert snapshot.selected_unit_id is None
    assert snapshot.objective_definitions == (
        session.snapshot().objective_definitions[0].__class__(
            objective_id="landing_pad_cleared",
            description_key="mission.objective.landing_pad_cleared",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="supply_route_to_hq",
            description_key="mission.objective.supply_route_to_hq",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="find_first_missing_detachment",
            description_key="mission.objective.find_first_missing_detachment",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="find_second_missing_detachment",
            description_key="mission.objective.find_second_missing_detachment",
        ),
    )


def test_snapshot_preserves_unit_supply_fields_without_default_fallbacks() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None
    motorized.carried_resources = {"fuel": 2, "mre": 1, "ammo": 0}
    session._selected_unit_id = motorized.unit_id
    session._supply_routes = {
        "route": SupplyRouteState(
            route_id="route",
            unit_id=motorized.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_dropoff",
        ),
    }

    snapshot = session.snapshot()
    units_by_id = {unit.unit_id: unit for unit in snapshot.units}

    assert isinstance(units_by_id["alpha_infantry"], UnitSnapshot)
    assert units_by_id["alpha_infantry"].can_transport_supplies is False
    assert units_by_id["alpha_infantry"].supply_capacity == 0
    assert units_by_id["alpha_infantry"].carried_supply_total == 0
    assert units_by_id["alpha_infantry"].active_supply_route_id is None
    assert units_by_id["bravo_mechanized"].can_transport_supplies is True
    assert units_by_id["bravo_mechanized"].supply_capacity == 24
    assert units_by_id["bravo_mechanized"].carried_supply_total == 3
    assert units_by_id["bravo_mechanized"].active_supply_route_id == "route"


def test_snapshot_includes_selected_unit_and_pending_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    snapshot = session.snapshot()

    assert snapshot.selected_unit_id == "alpha_infantry"
    alpha = next(unit for unit in snapshot.units if unit.unit_id == "alpha_infantry")
    assert alpha.target == (840.0, 500.0)
    assert alpha.name == "1. Druzyna Alfa"
    assert alpha.commander == alpha.commander.__class__(
        name="sier. Anna Sowa",
        experience_level="basic",
    )
    assert alpha.experience_level == "basic"
    assert alpha.personnel == 10
    assert alpha.armament_key == "game.unit.armament.rifles_lmg"
    assert alpha.attack == 4
    assert alpha.defense == 5
    assert alpha.morale == 72
    assert alpha.ammo == 90
    assert alpha.rations == 18
    assert alpha.fuel == 0
    assert alpha.marker_size_px == UNIT_TYPE_SPECS["infantry_squad"].marker_size_px


def test_snapshot_returns_value_objects_independent_from_future_session_mutation() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    snapshot_before = session.snapshot()

    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    session.tick()

    snapshot_after = session.snapshot()

    assert snapshot_before != snapshot_after
    alpha_before = next(unit for unit in snapshot_before.units if unit.unit_id == "alpha_infantry")
    alpha_after = next(unit for unit in snapshot_after.units if unit.unit_id == "alpha_infantry")
    assert alpha_before.target is None
    assert alpha_after.target is not None


def test_sync_state_updates_dimensions_ticks_and_returns_snapshot() -> None:
    session = create_default_game_session()

    snapshot = session.sync_state(width=960, height=640)

    assert isinstance(snapshot, GameStateSnapshot)
    assert session._map_size == (960, 640)
    assert snapshot.map_objects
    assert snapshot.units
    assert snapshot == session.snapshot()


def test_roads_snapshot_contains_naturally_curved_supply_road() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=1000, height=500)
    road = _road_snapshot(session)

    assert road.road_id == "main_supply_road"
    assert len(road.points) > 20

    start = road.points[0]
    end = road.points[-1]
    max_deviation = 0.0
    for point in road.points[1:-1]:
        progress = (point[0] - start[0]) / (end[0] - start[0]) if end[0] != start[0] else 0.0
        straight_y = start[1] + (end[1] - start[1]) * progress
        max_deviation = max(max_deviation, abs(point[1] - straight_y))

    assert max_deviation > 12.0


def test_landing_pad_supply_schedule_starts_after_objective_secured() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    initial_landing_pad = _landing_pad_snapshot(session)
    assert initial_landing_pad.is_secured is False
    assert initial_landing_pad.next_transport_seconds is None

    session._objective_status["landing_pad_cleared"] = True
    session.tick()

    secured_landing_pad = _landing_pad_snapshot(session)
    assert secured_landing_pad.is_secured is True
    assert secured_landing_pad.next_transport_seconds == 45
    assert secured_landing_pad.total_stored == 0


def test_supply_transport_appears_and_delivers_resources_after_real_time_elapsed() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session.tick()

    clock.advance(45)
    session.tick()

    transport_snapshot = session.supply_transports_snapshot()
    assert transport_snapshot == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=transport_snapshot[0].position,
            target_object_id="landing_pad",
        ),
    )

    clock.advance(6)
    session.tick()

    unloading_landing_pad = _landing_pad_snapshot(session)
    assert unloading_landing_pad.active_transport_phase == "unloading"
    assert unloading_landing_pad.active_transport_seconds_remaining == 14

    clock.advance(14)
    session.tick()

    outbound_landing_pad = _landing_pad_snapshot(session)
    delivered_by_resource = {
        resource.resource_id: resource.amount for resource in outbound_landing_pad.resources
    }
    outbound_transport = session.supply_transports_snapshot()
    assert outbound_landing_pad.total_stored == 30
    assert delivered_by_resource == {"fuel": 12, "mre": 8, "ammo": 10}
    assert outbound_landing_pad.active_transport_phase == "outbound"
    assert outbound_landing_pad.active_transport_seconds_remaining == 6
    assert outbound_transport == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="outbound",
            position=outbound_transport[0].position,
            target_object_id="landing_pad",
        ),
    )
    assert outbound_landing_pad.next_transport_seconds is None

    clock.advance(6)
    session.tick()

    delivered_landing_pad = _landing_pad_snapshot(session)
    delivered_by_resource = {
        resource.resource_id: resource.amount for resource in delivered_landing_pad.resources
    }
    assert delivered_landing_pad.total_stored == 30
    assert delivered_by_resource == {"fuel": 12, "mre": 8, "ammo": 10}
    assert session.supply_transports_snapshot() == ()
    assert delivered_landing_pad.next_transport_seconds == 45


def test_full_landing_pad_stops_future_supply_transport() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 40, "mre": 20, "ammo": 30}

    session.tick()
    landing_pad = _landing_pad_snapshot(session)

    assert landing_pad.total_stored == landing_pad.capacity
    assert landing_pad.next_transport_seconds is None
    assert landing_pad.active_transport_phase is None
    assert session.supply_transports_snapshot() == ()


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


def test_right_click_without_selection_is_noop() -> None:
    session = create_default_game_session()

    session.handle_right_click((20, 20))

    assert session.selected_unit_id() is None


def test_supply_route_can_be_created_only_for_transport_capable_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert session.supply_routes_snapshot() == ()


def test_handle_supply_route_accepts_transport_capable_unit_outside_legacy_convoy_allowlist() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    original_infantry_spec = UNIT_TYPE_SPECS["infantry_squad"]
    UNIT_TYPE_SPECS["cargo_truck"] = original_infantry_spec.__class__(
        type_id="cargo_truck",
        speed_kmph=12.0,
        marker_size_px=original_infantry_spec.marker_size_px,
        armament_key=original_infantry_spec.armament_key,
        attack=original_infantry_spec.attack,
        defense=original_infantry_spec.defense,
        can_transport_supplies=True,
        supply_capacity=18,
    )
    alpha_infantry = session._find_unit_by_id("alpha_infantry")
    assert alpha_infantry is not None
    try:
        alpha_infantry.unit_type_id = "cargo_truck"
        session._selected_unit_id = alpha_infantry.unit_id

        session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    finally:
        UNIT_TYPE_SPECS.pop("cargo_truck", None)
        alpha_infantry.unit_type_id = "infantry_squad"

    assert tuple(session._supply_routes) == ("alpha_infantry:landing_pad->hq",)


def test_supply_route_requires_selection_and_valid_objects() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    assert session.supply_routes_snapshot() == ()

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="hq", destination_object_id="landing_pad")

    assert session.supply_routes_snapshot() == ()


def test_supply_route_requires_landing_pad_to_be_cleared_first() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert session.supply_routes_snapshot() == ()


def test_supply_route_moves_motorized_unit_and_transfers_supply_to_hq() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session.tick()

    clock.advance(45)
    session.tick()
    clock.advance(6)
    session.tick()
    clock.advance(14)
    session.tick()
    clock.advance(6)
    session.tick()

    session._enemy_groups = []
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    route_snapshot = session.supply_routes_snapshot()
    assert route_snapshot == (
        SupplyRouteSnapshot(
            route_id=route_snapshot[0].route_id,
            unit_id="bravo_mechanized",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase=route_snapshot[0].phase,
            carried_total=route_snapshot[0].carried_total,
            capacity=24,
        ),
    )

    for _ in range(800):
        clock.advance(1)
        session.tick()
        route = session.supply_routes_snapshot()[0]
        if route.phase == "to_pickup" and route.carried_total == 0 and session.bases_snapshot()[0].total_stored > 0:
            break

    assert session.bases_snapshot()[0].total_stored == 24
    assert session.supply_routes_snapshot()[0].phase == "to_pickup"


def test_supply_route_plans_path_along_road_points_only() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 12, "mre": 8, "ammo": 4}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    active_unit = session._find_unit_by_id("bravo_mechanized")
    road_points = set(_road_snapshot(session).points)

    assert active_unit is not None
    assert active_unit.target == session._object_target_point("landing_pad", "mechanized_squad")
    assert active_unit.path
    assert set(active_unit.path).issubset(road_points)


def test_left_click_does_not_override_active_supply_route_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._landing_pads["landing_pad"].resources = {"fuel": 12, "mre": 8, "ammo": 4}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    session.handle_left_click(_unit_center(motorized))
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    target_before = _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"]

    session.handle_left_click((40, 40))

    assert _unit_by_id(session.units_snapshot(), "bravo_mechanized")["target"] == target_before


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


def test_landing_pad_objective_completes_only_after_zombies_are_removed() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    assert session.objective_status_snapshot()["landing_pad_cleared"] is False

    session._enemy_groups = []
    session.tick()

    assert session.objective_status_snapshot()["landing_pad_cleared"] is True


def test_reset_clears_units_selection_and_objective_progress() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._enemy_groups = []
    session.tick()
    assert session.objective_status_snapshot()["landing_pad_cleared"] is True

    session.reset()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    assert session.selected_unit_id() is None
    assert session.objective_status_snapshot()["landing_pad_cleared"] is False


def test_recon_site_investigation_removes_site_and_reveals_reinforcement_when_roll_hits() -> None:
    session = create_default_game_session(search_roll_provider=lambda: 0.0)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    recon_site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "recon_site_1")
    left, top, right, bottom = recon_site["bounds"]
    alpha = session._find_unit_by_id("alpha_infantry")
    assert alpha is not None
    alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)

    session.tick()

    assert "recon_site_1" not in {obj["id"] for obj in session.map_objects_snapshot()}
    assert session._find_unit_by_id("charlie_infantry") is not None
    assert session.objective_status_snapshot()["find_first_missing_detachment"] is True


def test_recon_search_finds_exactly_two_missing_detachments_with_lazy_rolls() -> None:
    rolls = iter([0.9, 0.0, 0.9, 0.0])
    session = create_default_game_session(search_roll_provider=lambda: next(rolls))
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    alpha = session._find_unit_by_id("alpha_infantry")
    assert alpha is not None

    for site_id in ("recon_site_1", "recon_site_2", "recon_site_3", "recon_site_4"):
        site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == site_id)
        left, top, right, bottom = site["bounds"]
        alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)
        session.tick()

    found_unit_ids = {unit["unit_id"] for unit in session.units_snapshot()}
    assert {"charlie_infantry", "delta_infantry"}.issubset(found_unit_ids)
    assert session.objective_status_snapshot()["find_second_missing_detachment"] is True


def test_snapshot_includes_reports_when_main_objectives_are_completed() -> None:
    session = create_default_game_session(search_roll_provider=lambda: 0.0)
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    session._enemy_groups = []
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    session.tick()

    first_recon_site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "recon_site_1")
    alpha = session._find_unit_by_id("alpha_infantry")
    assert alpha is not None
    left, top, right, bottom = first_recon_site["bounds"]
    alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)
    session.tick()

    second_recon_site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "recon_site_2")
    left, top, right, bottom = second_recon_site["bounds"]
    alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)
    session.tick()

    assert session.snapshot().mission_reports == (
        MissionReportSnapshot(
            report_id="hq_report_secure_landing_pad_and_route",
            title_key="mission.report.title",
            message_key="mission.report.secure_landing_pad_and_route",
        ),
        MissionReportSnapshot(
            report_id="hq_report_find_first_missing_detachment",
            title_key="mission.report.title",
            message_key="mission.report.find_first_missing_detachment",
        ),
        MissionReportSnapshot(
            report_id="hq_report_find_second_missing_detachment",
            title_key="mission.report.title",
            message_key="mission.report.find_second_missing_detachment",
        ),
    )


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
            "name",
            "commander",
            "experience_level",
            "personnel",
            "armament_key",
            "attack",
            "defense",
            "morale",
            "ammo",
            "rations",
            "fuel",
            "can_transport_supplies",
            "supply_capacity",
            "carried_supply_total",
            "active_supply_route_id",
            "is_in_combat",
            "combat_seconds_remaining",
        }
        assert unit["marker_size_px"] == UNIT_TYPE_SPECS[unit["unit_type_id"]].marker_size_px

    updated_infantry = _unit_by_id(units, "alpha_infantry")
    assert updated_infantry["target"] == (840.0, 500.0)
    assert updated_infantry["name"] == "1. Druzyna Alfa"
    assert updated_infantry["commander"] == {
        "name": "sier. Anna Sowa",
        "experience_level": "basic",
    }
    assert updated_infantry["experience_level"] == "basic"
    assert updated_infantry["personnel"] == 10
    assert updated_infantry["armament_key"] == "game.unit.armament.rifles_lmg"
    assert updated_infantry["attack"] == 4
    assert updated_infantry["defense"] == 5
    assert updated_infantry["morale"] == 72
    assert updated_infantry["ammo"] == 90
    assert updated_infantry["rations"] == 18
    assert updated_infantry["fuel"] == 0
    assert updated_infantry["is_in_combat"] is False
    assert updated_infantry["combat_seconds_remaining"] is None
    assert updated_infantry["can_transport_supplies"] is False
    assert updated_infantry["supply_capacity"] == 0
    assert updated_infantry["carried_supply_total"] == 0
    assert updated_infantry["active_supply_route_id"] is None

    updated_motorized = _unit_by_id(units, "bravo_mechanized")
    assert updated_motorized["name"] == "2. Sekcja Bravo"
    assert updated_motorized["commander"] == {
        "name": "sier. Marek Wolny",
        "experience_level": "basic",
    }
    assert updated_motorized["experience_level"] == "basic"
    assert updated_motorized["personnel"] == 8
    assert updated_motorized["armament_key"] == "game.unit.armament.apc_autocannon"
    assert updated_motorized["attack"] == 7
    assert updated_motorized["defense"] == 8
    assert updated_motorized["morale"] == 81
    assert updated_motorized["ammo"] == 120
    assert updated_motorized["rations"] == 24
    assert updated_motorized["fuel"] == 65
    assert updated_motorized["can_transport_supplies"] is True
    assert updated_motorized["supply_capacity"] == 24


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


def test_build_map_objects_preserves_configured_object_sizes() -> None:
    session = create_default_game_session()

    objects = session._build_map_objects(960, 640)
    layout_by_id = {obj["id"]: obj["bounds"] for obj in objects}

    hq_left, hq_top, hq_right, hq_bottom = layout_by_id["hq"]
    assert (hq_right - hq_left, hq_bottom - hq_top) == (84, 56)

    pad_left, pad_top, pad_right, pad_bottom = layout_by_id["landing_pad"]
    assert (pad_right - pad_left, pad_bottom - pad_top) == (72, 48)


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
    session._movement_pixels_per_tick = lambda unit_type_id: 5.0 if unit_type_id == "mechanized_squad" else 2.0

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
    session._movement_pixels_per_tick = lambda unit_type_id: 0.0 if unit_type_id == "infantry_squad" else 4.0

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
    session._movement_pixels_per_tick = lambda _unit_type_id: 0.0

    session._update_units_position()

    assert session._units[0].position == (100.0, 100.0)
    assert session._units[0].target == (200.0, 100.0)


def test_apply_transport_delivery_handles_full_pad_empty_cargo_and_fractional_trim() -> None:
    session = create_default_game_session()
    full_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 40, "mre": 20, "ammo": 30},
    )

    session._apply_transport_delivery(full_pad, "light_supply_helicopter")
    assert full_pad.resources == {"fuel": 40, "mre": 20, "ammo": 30}

    original_cargo = dict(SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo)
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(
        {"fuel": 0, "mre": 0, "ammo": 0}
    )
    try:
        partial_pad = LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=10,
            secured_by_objective_id="",
            resources={"fuel": 0, "mre": 0, "ammo": 0},
        )
        session._apply_transport_delivery(partial_pad, "light_supply_helicopter")
        assert partial_pad.resources == {"fuel": 0, "mre": 0, "ammo": 0}
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(original_cargo)

    fractional_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=10,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )
    session._apply_transport_delivery(fractional_pad, "heavy_supply_helicopter")

    assert sum(fractional_pad.resources.values()) == 10
    assert fractional_pad.resources["fuel"] >= fractional_pad.resources["ammo"]


def test_apply_transport_delivery_delivers_single_remaining_slot_and_defaults_missing_cargo_keys_to_zero() -> None:
    session = create_default_game_session()
    original_cargo = dict(SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo)
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update({"fuel": 1})
    try:
        landing_pad = LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=4,
            secured_by_objective_id="",
            resources={"fuel": 3, "mre": 0, "ammo": 0},
        )

        session._apply_transport_delivery(landing_pad, "light_supply_helicopter")

        assert landing_pad.resources == {"fuel": 4, "mre": 0, "ammo": 0}
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.clear()
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"].cargo.update(original_cargo)


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


def test_update_supply_routes_handles_missing_units_and_invalid_destinations() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._supply_routes = {
        "missing": SupplyRouteState(
            route_id="missing",
            unit_id="ghost",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes(elapsed_seconds=0.0)
    assert session._supply_routes == {}

    session._units = [
        UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(100.0, 100.0)),
    ]
    session._supply_routes = {
        "u1-route": SupplyRouteState(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="missing",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes(elapsed_seconds=0.0)

    assert session._supply_routes == {}


def test_refresh_route_pickup_waits_for_supply_and_capacity() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._units = [unit]
    session._bases["hq"].resources = {"fuel": 120, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)
    assert route.phase == "awaiting_supply"
    assert unit.target is None

    session._landing_pads["landing_pad"].resources = {"fuel": 10, "mre": 0, "ammo": 0}
    session._refresh_route_pickup(route, unit)
    assert route.phase == "awaiting_capacity"
    assert unit.target is None


def test_refresh_route_pickup_transfers_single_available_resource_instead_of_waiting() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="awaiting_supply",
    )
    session._units = [unit]
    session._landing_pads["landing_pad"].resources = {"fuel": 1, "mre": 0, "ammo": 0}
    session._bases["hq"].resources = {"fuel": 0, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)

    assert unit.carried_resources == {}
    assert session._landing_pads["landing_pad"].resources == {"fuel": 1, "mre": 0, "ammo": 0}
    assert unit.target is None
    assert route.phase == "loading"
    assert route.service_seconds_remaining == 6.0


def test_refresh_route_delivery_waits_for_capacity_and_preserves_remaining_cargo() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("hq", "mechanized_squad"),
        carried_resources={"fuel": 10, "mre": 8, "ammo": 6},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    session._bases["hq"].resources = {"fuel": 118, "mre": 1, "ammo": 0}

    session._refresh_route_delivery(route, unit)

    assert route.phase == "unloading"
    assert unit.target is None
    assert unit.carried_resources == {"fuel": 10, "mre": 8, "ammo": 6}
    assert route.service_seconds_remaining == 6.0


def test_helpers_cover_missing_map_object_route_clear_and_resource_math() -> None:
    session = create_default_game_session()
    session._supply_routes = {
        "route": SupplyRouteState(
            route_id="route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    assert session._map_object_center("missing") == (0.0, 0.0)
    session._clear_supply_route_for_unit("u1")
    assert session._supply_routes == {}
    assert session._subtract_resources({"fuel": 4, "mre": 2, "ammo": 1}, {"fuel": 1, "mre": 3, "ammo": 1}) == {
        "fuel": 3,
        "mre": 0,
        "ammo": 0,
    }


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


def test_store_resources_breaks_when_capacity_is_full_and_transport_position_handles_unloading() -> None:
    session = create_default_game_session()

    stored = session._store_resources(
        {"fuel": 3, "mre": 1, "ammo": 0},
        {"fuel": 4, "mre": 2, "ammo": 1},
        4,
    )
    assert stored == {"fuel": 0, "mre": 0, "ammo": 0}

    active_transport = SupplyTransportState(
        transport_id="t1",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="unloading",
        position=(10.0, 10.0),
        seconds_remaining=5.0,
        total_phase_seconds=14.0,
        origin_position=(0.0, 0.0),
        destination_position=(30.0, 40.0),
    )

    assert session._transport_position_for_progress(active_transport) == (30.0, 40.0)


def test_handle_supply_route_replaces_existing_route_resets_cargo_and_targets_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None

    session._selected_unit_id = motorized.unit_id
    motorized.target = (10.0, 20.0)
    motorized.carried_resources = {"fuel": 4, "mre": 3, "ammo": 2}
    session._supply_routes = {
        "old-route": SupplyRouteState(
            route_id="old-route",
            unit_id=motorized.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_dropoff",
        ),
    }

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    assert tuple(session._supply_routes) == ("bravo_mechanized:landing_pad->hq",)
    assert motorized.carried_resources == {"fuel": 0, "mre": 0, "ammo": 0}
    assert motorized.target == session._object_target_point("landing_pad", motorized.unit_type_id)


def test_handle_supply_route_initializes_new_route_with_to_pickup_phase_before_refresh() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    captured_phases: list[str | None] = []
    original_refresh = session._refresh_supply_route
    session._refresh_supply_route = lambda route: captured_phases.append(route.phase)  # type: ignore[method-assign]
    try:
        session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    finally:
        session._refresh_supply_route = original_refresh  # type: ignore[method-assign]

    assert captured_phases == ["to_pickup"]


def test_bases_snapshot_projects_sorted_resources_and_totals() -> None:
    session = create_default_game_session()
    session._bases = {
        "zeta": BaseState(
            object_id="zeta",
            capacity=7,
            resources={"fuel": 2, "mre": 1, "ammo": 3},
        ),
        "alpha": BaseState(
            object_id="alpha",
            capacity=9,
            resources={"fuel": 1, "mre": 4, "ammo": 0},
        ),
    }

    assert session.bases_snapshot() == (
        BaseSnapshot(
            object_id="alpha",
            capacity=9,
            total_stored=5,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=1),
                LandingPadResourceSnapshot(resource_id="mre", amount=4),
                LandingPadResourceSnapshot(resource_id="ammo", amount=0),
            ),
        ),
        BaseSnapshot(
            object_id="zeta",
            capacity=7,
            total_stored=6,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=2),
                LandingPadResourceSnapshot(resource_id="mre", amount=1),
                LandingPadResourceSnapshot(resource_id="ammo", amount=3),
            ),
        ),
    )


def test_landing_pad_and_transport_snapshots_include_transport_state_and_skip_empty_pads() -> None:
    session = create_default_game_session()
    session._objective_status["landing_pad_cleared"] = True
    active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(100.0, 200.0),
        seconds_remaining=5.2,
        total_phase_seconds=6.0,
        origin_position=(120.0, 180.0),
        destination_position=(80.0, 220.0),
    )
    session._landing_pads = {
        "zeta": LandingPadState(
            object_id="zeta",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
        ),
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="large",
            capacity=180,
            secured_by_objective_id="landing_pad_cleared",
            resources={"fuel": 3, "mre": 4, "ammo": 5},
            next_transport_eta_seconds=2.2,
            active_transport=active_transport,
        ),
    }

    assert session.landing_pads_snapshot() == (
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="large",
            is_secured=True,
            capacity=180,
            total_stored=12,
            next_transport_seconds=3,
            active_transport_type_id="light_supply_helicopter",
            active_transport_phase="inbound",
            active_transport_seconds_remaining=6,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=3),
                LandingPadResourceSnapshot(resource_id="mre", amount=4),
                LandingPadResourceSnapshot(resource_id="ammo", amount=5),
            ),
        ),
        LandingPadSnapshot(
            object_id="zeta",
            pad_size="small",
            is_secured=True,
            capacity=90,
            total_stored=0,
            next_transport_seconds=None,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=(
                LandingPadResourceSnapshot(resource_id="fuel", amount=0),
                LandingPadResourceSnapshot(resource_id="mre", amount=0),
                LandingPadResourceSnapshot(resource_id="ammo", amount=0),
            ),
        ),
    )
    assert session.supply_transports_snapshot() == (
        SupplyTransportSnapshot(
            transport_id="landing_pad_supply",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=(100.0, 200.0),
            target_object_id="landing_pad",
        ),
    )


def test_supply_routes_snapshot_skips_missing_unit_and_uses_carried_total_and_capacity() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(10.0, 20.0),
            carried_resources={"fuel": 3, "mre": 2, "ammo": 1},
        ),
    ]
    session._supply_routes = {
        "missing": SupplyRouteState(
            route_id="missing",
            unit_id="ghost",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
        "u1-route": SupplyRouteState(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
        ),
    }

    assert session.supply_routes_snapshot() == (
        SupplyRouteSnapshot(
            route_id="u1-route",
            unit_id="u1",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
            carried_total=6,
            capacity=24,
        ),
    )


def test_snapshot_includes_supply_related_subsnapshots() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    motorized = session._find_unit_by_id("bravo_mechanized")
    assert motorized is not None
    motorized.carried_resources = {"fuel": 2, "mre": 1, "ammo": 0}
    session._selected_unit_id = motorized.unit_id
    session._supply_routes = {
        "route": SupplyRouteState(
            route_id="route",
            unit_id=motorized.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_dropoff",
        ),
    }
    session._landing_pads["landing_pad"].next_transport_eta_seconds = 4.1
    session._landing_pads["landing_pad"].active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="unloading",
        position=(1.0, 2.0),
        seconds_remaining=3.1,
        total_phase_seconds=14.0,
        origin_position=(0.0, 0.0),
        destination_position=(1.0, 2.0),
    )
    session._bases["hq"].resources = {"fuel": 1, "mre": 2, "ammo": 3}

    snapshot = session.snapshot()

    assert snapshot.selected_unit_id == motorized.unit_id
    assert snapshot.supply_routes[0].carried_total == 3
    assert snapshot.supply_transports[0].phase == "unloading"
    assert snapshot.landing_pads[0].next_transport_seconds == 5
    assert snapshot.bases[0].total_stored == 6


def test_sync_bases_to_map_objects_trims_existing_resources_and_ignores_non_storage_objects() -> None:
    session = create_default_game_session()
    session._map_objects = [
        {"id": "landing_pad", "bounds": (1, 2, 3, 4), "pad_size": "small"},
        {"id": "hq", "bounds": (10, 20, 30, 40), "storage_capacity": 5},
    ]
    session._bases = {
        "hq": BaseState(
            object_id="hq",
            capacity=120,
            resources={"fuel": 3, "mre": 3, "ammo": 3},
        ),
        "stale": BaseState(
            object_id="stale",
            capacity=10,
            resources={"fuel": 9, "mre": 0, "ammo": 0},
        ),
    }

    session._sync_bases_to_map_objects()

    assert session._bases == {
        "hq": BaseState(
            object_id="hq",
            capacity=5,
            resources={"fuel": 3, "mre": 2, "ammo": 0},
        ),
    }


def test_sync_landing_pads_to_map_objects_preserves_runtime_state_trims_resources_and_refreshes_geometry() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [
        {"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": "large", "secured_by_objective_id": "x"},
        {"id": "hq", "bounds": (100, 100, 200, 200), "storage_capacity": 20},
    ]
    active_transport = SupplyTransportState(
        transport_id="landing_pad_supply",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=3.0,
        total_phase_seconds=6.0,
        origin_position=(0.0, 0.0),
        destination_position=(0.0, 0.0),
    )
    session._landing_pads = {
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="old",
            resources={"fuel": 100, "mre": 60, "ammo": 40},
            next_transport_eta_seconds=9.5,
            active_transport=active_transport,
        ),
    }

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "large"
    assert landing_pad.capacity == 180
    assert landing_pad.secured_by_objective_id == "x"
    assert landing_pad.resources == {"fuel": 100, "mre": 60, "ammo": 20}
    assert landing_pad.next_transport_eta_seconds == 9.5
    assert landing_pad.active_transport is active_transport
    assert landing_pad.active_transport.destination_position == (756.0, 204.0)
    assert landing_pad.active_transport.origin_position == session._transport_origin_for_destination((756.0, 204.0))
    assert landing_pad.active_transport.position != (0.0, 0.0)


def test_sync_landing_pads_to_map_objects_defaults_missing_pad_metadata_and_resource_keys() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": None}]
    session._landing_pads = {
        "landing_pad": LandingPadState(
            object_id="landing_pad",
            pad_size="large",
            capacity=180,
            secured_by_objective_id="old-objective",
            resources={"fuel": 4},
            next_transport_eta_seconds=12.5,
        ),
    }

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "small"
    assert landing_pad.capacity == 90
    assert landing_pad.secured_by_objective_id == ""
    assert landing_pad.resources == {"fuel": 4, "mre": 0, "ammo": 0}
    assert landing_pad.next_transport_eta_seconds == 12.5


def test_sync_landing_pads_to_map_objects_initializes_missing_runtime_state_for_new_pad() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": "small"}]

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is None


def test_consume_supply_elapsed_seconds_clamps_negative_elapsed_and_updates_timestamp() -> None:
    clock = _FakeClock(start=10.0)
    session = create_default_game_session(time_provider=clock.now)

    assert session._consume_supply_elapsed_seconds() == 0.0
    clock.current = 5.0
    assert session._consume_supply_elapsed_seconds() == 0.0
    assert session._last_supply_update_at == 5.0


def test_consume_combat_elapsed_seconds_clamps_negative_elapsed_and_updates_timestamp() -> None:
    clock = _FakeClock(start=10.0)
    session = create_default_game_session(time_provider=clock.now)

    assert session._consume_combat_elapsed_seconds() == 0.0
    clock.current = 5.0
    assert session._consume_combat_elapsed_seconds() == 0.0
    assert session._last_combat_update_at == 5.0


def test_update_landing_pad_supply_clears_unsecured_transport_state() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        resources={"fuel": 1, "mre": 2, "ammo": 3},
        next_transport_eta_seconds=12.0,
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(1.0, 2.0),
            seconds_remaining=4.0,
            total_phase_seconds=6.0,
            origin_position=(0.0, 0.0),
            destination_position=(3.0, 4.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=5.0)

    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is None


def test_update_landing_pad_supply_counts_down_eta_and_starts_transport_once_interval_elapses() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        next_transport_eta_seconds=10.0,
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=4.0)
    assert landing_pad.next_transport_eta_seconds == 6.0
    assert landing_pad.active_transport is None

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=6.0)
    assert landing_pad.next_transport_eta_seconds is None
    assert landing_pad.active_transport is not None
    assert landing_pad.active_transport.phase == "inbound"


def test_advance_transport_runs_full_lifecycle_and_schedules_next_eta_when_pad_not_full() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(90.0, 90.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)
    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.position == (60.0, 60.0)
    assert active_transport.seconds_remaining == 14.0

    session._advance_transport(landing_pad, elapsed_seconds=14.0)
    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert landing_pad.resources == {"fuel": 12, "mre": 8, "ammo": 10}
    assert active_transport.seconds_remaining == 6.0

    session._advance_transport(landing_pad, elapsed_seconds=6.0)
    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 45.0


def test_start_transport_for_landing_pad_uses_pad_spec_and_map_geometry() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="large",
        capacity=180,
        secured_by_objective_id="",
    )

    session._start_transport_for_landing_pad(landing_pad)

    assert landing_pad.active_transport is not None
    assert landing_pad.active_transport.transport_type_id == "heavy_supply_helicopter"
    assert landing_pad.active_transport.destination_position == (756.0, 204.0)
    assert landing_pad.active_transport.origin_position == (1056.0, 84.0)


def test_apply_transport_delivery_uses_fractional_distribution_without_exceeding_capacity() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=7,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )

    session._apply_transport_delivery(landing_pad, "heavy_supply_helicopter")

    assert landing_pad.resources == {"fuel": 3, "mre": 2, "ammo": 2}


def test_apply_transport_delivery_preserves_existing_amounts_and_initializes_missing_keys(monkeypatch) -> None:
    session = create_default_game_session()
    transport_type_id = "test_sparse_transport"
    monkeypatch.setitem(
        SUPPLY_TRANSPORT_TYPE_SPECS,
        transport_type_id,
        SupplyTransportTypeSpec(
            type_id=transport_type_id,
            cargo={"fuel": 1, "mre": 1, "ammo": 1},
        ),
    )
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=20,
        secured_by_objective_id="",
        resources={"fuel": 5},
    )

    session._apply_transport_delivery(landing_pad, transport_type_id)

    assert landing_pad.resources == {"fuel": 6, "mre": 1, "ammo": 1}


def test_apply_transport_delivery_uses_each_remaining_slot_once() -> None:
    session = create_default_game_session()
    original_transport = SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"]
    SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"] = SupplyTransportTypeSpec(
        type_id="light_supply_helicopter",
        cargo={"fuel": 2, "mre": 2, "ammo": 2},
    )
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=2,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
    )

    try:
        session._apply_transport_delivery(landing_pad, "light_supply_helicopter")
    finally:
        SUPPLY_TRANSPORT_TYPE_SPECS["light_supply_helicopter"] = original_transport

    assert landing_pad.resources == {"fuel": 1, "mre": 1, "ammo": 0}


def test_refresh_supply_route_targets_updates_pickup_and_delivery_targets_for_all_routes() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._landing_pads["landing_pad"].resources = {"fuel": 10, "mre": 0, "ammo": 0}
    session._bases["hq"].resources = {"fuel": 0, "mre": 0, "ammo": 0}
    pickup_unit = session._find_unit_by_id("bravo_mechanized")
    delivery_unit = UnitState(
        unit_id="delivery",
        unit_type_id="mechanized_squad",
        position=(10.0, 10.0),
        carried_resources={"fuel": 2, "mre": 0, "ammo": 0},
    )
    assert pickup_unit is not None
    session._units.append(delivery_unit)
    session._supply_routes = {
        "pickup": SupplyRouteState(
            route_id="pickup",
            unit_id=pickup_unit.unit_id,
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_supply",
        ),
        "delivery": SupplyRouteState(
            route_id="delivery",
            unit_id="delivery",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="awaiting_capacity",
        ),
    }

    session._refresh_supply_route_targets()

    assert pickup_unit.target == session._object_target_point("landing_pad", pickup_unit.unit_type_id)
    assert delivery_unit.target == session._object_target_point("hq", delivery_unit.unit_type_id)
    assert session._supply_routes["pickup"].phase == "to_pickup"
    assert session._supply_routes["delivery"].phase == "to_dropoff"


def test_refresh_route_pickup_transfers_minimum_of_source_destination_and_unit_capacity() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._units = [unit]
    session._landing_pads["landing_pad"].resources = {"fuel": 3, "mre": 4, "ammo": 10}
    session._bases["hq"].resources = {"fuel": 118, "mre": 0, "ammo": 0}

    session._refresh_route_pickup(route, unit)

    assert unit.carried_resources == {}
    assert session._landing_pads["landing_pad"].resources == {"fuel": 3, "mre": 4, "ammo": 10}
    assert unit.target is None
    assert route.phase == "loading"
    assert route.service_seconds_remaining == 6.0


def test_refresh_route_delivery_drops_all_cargo_and_returns_unit_to_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("hq", "mechanized_squad"),
        carried_resources={"fuel": 2, "mre": 3, "ammo": 4},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_dropoff",
    )
    session._bases["hq"].resources = {"fuel": 1, "mre": 1, "ammo": 1}

    session._refresh_route_delivery(route, unit)

    assert session._bases["hq"].resources == {"fuel": 1, "mre": 1, "ammo": 1}
    assert unit.carried_resources == {"fuel": 2, "mre": 3, "ammo": 4}
    assert unit.target is None
    assert route.phase == "unloading"
    assert route.service_seconds_remaining == 6.0


def test_refresh_supply_route_uses_unit_type_service_times_from_specs(monkeypatch) -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=session._object_target_point("landing_pad", "mechanized_squad"),
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._units = [unit]
    session._landing_pads["landing_pad"].resources = {"fuel": 4, "mre": 0, "ammo": 0}
    monkeypatch.setitem(
        UNIT_TYPE_SPECS,
        "mechanized_squad",
        replace(UNIT_TYPE_SPECS["mechanized_squad"], supply_load_seconds=9.0, supply_unload_seconds=11.0),
    )

    session._refresh_supply_route(route)

    assert route.phase == "loading"
    assert route.service_seconds_remaining == 9.0


def test_resource_helpers_trim_take_and_store_in_resource_order() -> None:
    session = create_default_game_session()

    trimmed = session._trim_resources_to_capacity({"fuel": 5, "mre": 5, "ammo": 5}, 7)
    assert trimmed == {"fuel": 5, "mre": 2, "ammo": 0}

    storage = {"fuel": 3, "mre": 4, "ammo": 5}
    taken = session._take_resources(storage, 6)
    assert taken == {"fuel": 3, "mre": 3, "ammo": 0}
    assert storage == {"fuel": 0, "mre": 1, "ammo": 5}

    base_storage = {"fuel": 1, "mre": 0, "ammo": 0}
    stored = session._store_resources(
        base_storage,
        {"fuel": 5, "mre": 4, "ammo": 3},
        6,
    )
    assert stored == {"fuel": 5, "mre": 0, "ammo": 0}
    assert base_storage == {"fuel": 6, "mre": 0, "ammo": 0}


def test_take_resources_with_non_positive_amount_is_noop() -> None:
    session = create_default_game_session()
    storage = {"fuel": 3, "mre": 4, "ammo": 5}

    assert session._take_resources(storage, 0) == {"fuel": 0, "mre": 0, "ammo": 0}
    assert storage == {"fuel": 3, "mre": 4, "ammo": 5}


def test_store_resources_spills_into_next_resource_until_capacity_is_reached() -> None:
    session = create_default_game_session()
    storage = {"fuel": 0, "mre": 1, "ammo": 0}

    stored = session._store_resources(
        storage,
        {"fuel": 2, "mre": 5, "ammo": 7},
        5,
    )

    assert stored == {"fuel": 2, "mre": 2, "ammo": 0}
    assert storage == {"fuel": 2, "mre": 3, "ammo": 0}


def test_landing_pad_security_center_target_and_tolerance_helpers_cover_edge_cases() -> None:
    session = create_default_game_session()
    session._map_size = (120, 90)
    session._map_objects = [{"id": "landing_pad", "bounds": (10, 20, 50, 60)}]
    secured_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
            secured_by_objective_id="landing_pad_cleared",
    )
    always_secured_pad = LandingPadState(
        object_id="other",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
    )

    assert session._is_landing_pad_secured(secured_pad) is False
    assert session._is_landing_pad_secured(always_secured_pad) is True
    session._objective_status["landing_pad_cleared"] = True
    assert session._is_landing_pad_secured(secured_pad) is True
    assert session._map_object_center("landing_pad") == (30.0, 40.0)
    assert session._object_target_point("landing_pad", "mechanized_squad") == (30.0, 40.0)
    assert session._positions_match((10.0, 10.0), (10.3, 10.3)) is True
    assert session._positions_match((10.0, 10.0), (10.4, 10.4)) is False


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


def test_refresh_route_pickup_moves_unit_towards_source_when_not_yet_at_pickup() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(10.0, 10.0))
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="awaiting_supply",
    )

    session._refresh_route_pickup(route, unit)

    assert route.phase == "to_pickup"
    assert unit.target == session._object_target_point("landing_pad", "mechanized_squad")


def test_refresh_route_delivery_moves_unit_towards_destination_when_not_yet_at_dropoff() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(10.0, 10.0),
        carried_resources={"fuel": 3, "mre": 0, "ammo": 0},
    )
    route = SupplyRouteState(
        route_id="u1-route",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="awaiting_capacity",
    )

    session._refresh_route_delivery(route, unit)

    assert route.phase == "to_dropoff"


def test_sync_landing_pads_to_map_objects_defaults_missing_pad_size_to_small() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228), "pad_size": None}]

    session._sync_landing_pads_to_map_objects()

    landing_pad = session._landing_pads["landing_pad"]
    assert landing_pad.pad_size == "small"
    assert landing_pad.capacity == 90


def test_update_landing_pad_supply_refreshes_transport_geometry_even_when_elapsed_is_zero() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(1.0, 2.0),
            seconds_remaining=6.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=0.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.destination_position == (756.0, 204.0)
    assert active_transport.origin_position == session._transport_origin_for_destination((756.0, 204.0))
    assert active_transport.position != (1.0, 2.0)


def test_update_landing_pad_supply_returns_after_exactly_consuming_elapsed_transport_time() -> None:
    session = create_default_game_session()
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    def finish_transport(pad: LandingPadState, elapsed_seconds: float) -> None:
        assert elapsed_seconds == 1.0
        pad.active_transport = None

    session._advance_transport = finish_transport  # type: ignore[method-assign]

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=1.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds is None


def test_update_landing_pad_supply_advances_exactly_one_second_of_active_transport() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(0.0, 0.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(12.0, 18.0),
            destination_position=(30.0, 42.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.seconds_remaining == 14.0
    assert active_transport.position == (30.0, 42.0)


def test_update_landing_pad_supply_consumes_one_second_of_leftover_eta_after_transport_finishes() -> None:
    session = create_default_game_session()
    session._objective_status["landing_pad_cleared"] = True
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="landing_pad_cleared",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(10.0, 20.0),
            destination_position=(30.0, 40.0),
        ),
    )

    def finish_transport(pad: LandingPadState, elapsed_seconds: float) -> None:
        assert elapsed_seconds == 1.0
        pad.active_transport = None

    session._advance_transport = finish_transport  # type: ignore[method-assign]

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=2.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 44.0


def test_update_landing_pad_supply_uses_leftover_elapsed_time_to_start_next_eta_countdown() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(90.0, 90.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._update_landing_pad_supply(landing_pad, elapsed_seconds=2.0)

    assert landing_pad.active_transport is None
    assert landing_pad.next_transport_eta_seconds == 44.0


def test_advance_transport_keeps_inbound_phase_while_one_second_remains() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(0.0, 0.0),
            seconds_remaining=2.0,
            total_phase_seconds=10.0,
            origin_position=(0.0, 0.0),
            destination_position=(10.0, 0.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "inbound"
    assert active_transport.seconds_remaining == 1.0
    assert active_transport.position == (9.0, 0.0)


def test_advance_transport_updates_inbound_position_before_arrival() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(0.0, 0.0),
            seconds_remaining=5.0,
            total_phase_seconds=10.0,
            origin_position=(0.0, 0.0),
            destination_position=(10.0, 0.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=2.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "inbound"
    assert active_transport.seconds_remaining == 3.0
    assert active_transport.position == (7.0, 0.0)


def test_advance_transport_transitions_from_inbound_to_unloading_on_exact_arrival() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="inbound",
            position=(0.0, 0.0),
            seconds_remaining=1.0,
            total_phase_seconds=6.0,
            origin_position=(12.0, 18.0),
            destination_position=(30.0, 42.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "unloading"
    assert active_transport.seconds_remaining == 14.0
    assert active_transport.total_phase_seconds == 14.0
    assert active_transport.position == (30.0, 42.0)


def test_advance_transport_keeps_destination_position_while_unloading_and_sets_outbound_position() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="unloading",
            position=(1.0, 2.0),
            seconds_remaining=1.0,
            total_phase_seconds=14.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert active_transport.seconds_remaining == 6.0
    assert active_transport.total_phase_seconds == 6.0
    assert active_transport.position == (60.0, 60.0)


def test_advance_transport_updates_outbound_position_before_departure_finishes() -> None:
    session = create_default_game_session()
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        resources={"fuel": 0, "mre": 0, "ammo": 0},
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(0.0, 0.0),
            seconds_remaining=2.0,
            total_phase_seconds=6.0,
            origin_position=(120.0, 120.0),
            destination_position=(60.0, 60.0),
        ),
    )

    session._advance_transport(landing_pad, elapsed_seconds=1.0)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.phase == "outbound"
    assert active_transport.position == (110.0, 110.0)


def test_display_seconds_rounds_up_and_clamps_negative_values() -> None:
    session = create_default_game_session()

    assert session._display_seconds(0.1) == 1
    assert session._display_seconds(-0.1) == 0
    assert session._display_seconds(None) is None


def test_transport_origin_interpolation_and_progress_cover_clamping_and_outbound_paths() -> None:
    session = create_default_game_session()
    session._map_size = (100, 80)

    assert session._transport_origin_for_destination((10.0, 10.0)) == (196.0, 24.0)
    assert session._transport_origin_for_destination((300.0, 90.0)) == (396.0, 24.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), -1.0) == (0.0, 10.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), 0.25) == (25.0, 15.0)
    assert session._interpolate_points((0.0, 10.0), (100.0, 30.0), 2.0) == (100.0, 30.0)

    inbound = SupplyTransportState(
        transport_id="t1",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=5.0,
        total_phase_seconds=10.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )
    outbound = SupplyTransportState(
        transport_id="t2",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="outbound",
        position=(0.0, 0.0),
        seconds_remaining=5.0,
        total_phase_seconds=10.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )
    instant = SupplyTransportState(
        transport_id="t3",
        transport_type_id="light_supply_helicopter",
        target_object_id="landing_pad",
        phase="inbound",
        position=(0.0, 0.0),
        seconds_remaining=3.0,
        total_phase_seconds=0.0,
        origin_position=(100.0, 100.0),
        destination_position=(20.0, 40.0),
    )

    assert session._transport_position_for_progress(inbound) == (60.0, 70.0)
    assert session._transport_position_for_progress(outbound) == (60.0, 70.0)
    assert session._transport_position_for_progress(instant) == (20.0, 40.0)


def test_transport_origin_for_destination_uses_wider_x_and_clamps_y_to_bounds() -> None:
    session = create_default_game_session()
    session._map_size = (100, 300)

    assert session._transport_origin_for_destination((10.0, 10.0)) == (196.0, 24.0)
    assert session._transport_origin_for_destination((300.0, 90.0)) == (396.0, 24.0)
    assert session._transport_origin_for_destination((10.0, 500.0)) == (196.0, 276.0)
    assert session._transport_origin_for_destination((500.0, 500.0)) == (596.0, 276.0)


def test_refresh_transport_geometry_recomputes_positions_for_outbound_transport() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    session._map_objects = [{"id": "landing_pad", "bounds": (720, 180, 792, 228)}]
    landing_pad = LandingPadState(
        object_id="landing_pad",
        pad_size="small",
        capacity=90,
        secured_by_objective_id="",
        active_transport=SupplyTransportState(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            target_object_id="landing_pad",
            phase="outbound",
            position=(0.0, 0.0),
            seconds_remaining=3.0,
            total_phase_seconds=6.0,
            origin_position=(0.0, 0.0),
            destination_position=(0.0, 0.0),
        ),
    )

    session._refresh_transport_geometry(landing_pad)

    active_transport = landing_pad.active_transport
    assert active_transport is not None
    assert active_transport.destination_position == (756.0, 204.0)
    assert active_transport.origin_position == (1056.0, 84.0)
    assert active_transport.position == (906.0, 144.0)


def test_update_map_dimensions_accepts_minimum_positive_dimensions() -> None:
    session = create_default_game_session()

    session.update_map_dimensions(width=1, height=1)

    assert session.map_objects_snapshot()
    assert session.units_snapshot()


def test_units_snapshot_exposes_active_supply_route_id_for_routed_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"

    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")

    assert motorized["active_supply_route_id"] == "bravo_mechanized:landing_pad->hq"


def test_supply_transports_snapshot_skips_empty_pads_without_stopping_iteration() -> None:
    session = create_default_game_session()
    session._landing_pads = {
        "alpha_pad": LandingPadState(
            object_id="alpha_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
            active_transport=None,
        ),
        "bravo_pad": LandingPadState(
            object_id="bravo_pad",
            pad_size="small",
            capacity=90,
            secured_by_objective_id="",
            active_transport=SupplyTransportState(
                transport_id="t1",
                transport_type_id="light_supply_helicopter",
                target_object_id="bravo_pad",
                phase="inbound",
                position=(12.0, 34.0),
                seconds_remaining=5.0,
                total_phase_seconds=10.0,
                origin_position=(100.0, 40.0),
                destination_position=(20.0, 40.0),
            ),
        ),
    }

    assert session.supply_transports_snapshot() == (
        SupplyTransportSnapshot(
            transport_id="t1",
            transport_type_id="light_supply_helicopter",
            phase="inbound",
            position=(12.0, 34.0),
            target_object_id="bravo_pad",
        ),
    )


def test_snapshot_projects_current_bounds_positions_and_route_ids() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")

    map_objects = {obj["id"]: obj["bounds"] for obj in session.map_objects_snapshot()}
    motorized = _unit_by_id(session.units_snapshot(), "bravo_mechanized")
    snapshot = session.snapshot()

    assert {obj.object_id: obj.bounds for obj in snapshot.map_objects} == map_objects
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").position == motorized["position"]
    assert snapshot.enemy_groups[0].group_id == "zulu_zombies"
    assert next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized").active_supply_route_id == (
        "bravo_mechanized:landing_pad->hq"
    )


def test_enemy_group_starts_on_landing_pad_center() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]

    enemy_group = _enemy_group_snapshot(session)

    assert enemy_group.position == ((left + right) / 2.0, (top + bottom) / 2.0)


def test_collision_with_enemy_starts_combat_and_exposes_alert_snapshot() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = session._find_unit_by_id("bravo_mechanized")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert motorized is not None
    assert enemy_group is not None

    motorized.position = enemy_group.position
    motorized.target = (120.0, 120.0)
    motorized.path = ((120.0, 120.0),)

    session.tick()

    snapshot = session.snapshot()
    motorized_snapshot = next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized")

    assert snapshot.combats == (
        CombatSnapshot(
            combat_id="bravo_mechanized:zulu_zombies",
            unit_id="bravo_mechanized",
            unit_name="2. Sekcja Bravo",
            enemy_group_id="zulu_zombies",
            enemy_group_name="Mala grupa zombie",
            seconds_remaining=24,
        ),
    )
    assert snapshot.combat_notifications == (
        CombatNotificationSnapshot(
            notification_id="bravo_mechanized:zulu_zombies:started",
            unit_name="2. Sekcja Bravo",
            enemy_group_name="Mala grupa zombie",
            phase="started",
            seconds_remaining=12,
        ),
    )
    assert motorized_snapshot.is_in_combat is True
    assert motorized_snapshot.combat_seconds_remaining == 24
    assert snapshot.enemy_groups[0].is_in_combat is True


def test_active_combat_stops_unit_movement_until_enemy_group_is_cleared() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = session._find_unit_by_id("alpha_infantry")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert infantry is not None
    assert enemy_group is not None

    infantry.position = enemy_group.position
    infantry.target = (120.0, 120.0)
    infantry.path = ((120.0, 120.0),)

    session.tick()
    locked_position = infantry.position

    clock.advance(5)
    session.tick()

    assert infantry.position == locked_position
    assert session.combats_snapshot()[0].seconds_remaining == 37

    for _ in range(12):
        clock.advance(6)
        session.tick()
        if session.combats_snapshot() == ():
            break

    assert session.combats_snapshot() == ()
    assert session.enemy_groups_snapshot() == ()


def test_start_combats_does_not_assign_enemy_group_to_second_unit_when_already_engaged() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    alpha = session._find_unit_by_id("alpha_infantry")
    bravo = session._find_unit_by_id("bravo_mechanized")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert alpha is not None
    assert bravo is not None
    assert enemy_group is not None

    alpha.position = enemy_group.position
    bravo.position = enemy_group.position
    session._combats = {
        "alpha_infantry:zulu_zombies": CombatState(
            combat_id="alpha_infantry:zulu_zombies",
            unit_id="alpha_infantry",
            enemy_group_id="zulu_zombies",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._start_combats_for_colliding_units()

    assert tuple(sorted(session._combats)) == ("alpha_infantry:zulu_zombies",)


def test_update_combats_continues_after_none_placeholder_and_updates_real_combat() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "a_placeholder": None,  # type: ignore[dict-item]
        "z_real": CombatState(
            combat_id="z_real",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=8.0)

    real_combat = session._combats["z_real"]
    assert isinstance(real_combat, CombatState)
    assert real_combat.seconds_remaining == 16.0
    assert real_combat.seconds_until_next_exchange == 4.0


def test_update_combats_removes_stale_combat_when_unit_or_enemy_disappears() -> None:
    session = create_default_game_session()
    session._combats = {
        "missing": CombatState(
            combat_id="missing",
            unit_id="ghost_unit",
            enemy_group_id="ghost_enemy",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=4.0)

    assert session._combats == {}


def test_update_combats_removes_combat_when_enemy_group_disappears_but_unit_still_exists() -> None:
    session = create_default_game_session()
    session._units = [UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0))]
    session._combats = {
        "missing-enemy": CombatState(
            combat_id="missing-enemy",
            unit_id="u1",
            enemy_group_id="ghost_enemy",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=4.0)

    assert session._combats == {}


def test_update_combats_waits_for_exchange_boundary_before_applying_attrition() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=5.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 19.0
    assert combat.seconds_until_next_exchange == 1.0
    assert enemy_group.personnel == 5
    assert unit.ammo == 30
    assert unit.morale == 20


def test_update_combats_resolves_on_enemy_elimination_even_when_time_remains() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=12,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=1)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    assert session._combats == {}
    assert session._enemy_groups == []
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="engagement:ended",
            unit_name="u1",
            enemy_group_name="e1",
            phase="ended",
            seconds_remaining=12,
        ),
    )


def test_update_combats_keeps_engagement_active_when_enemy_survives_and_timer_stays_above_zero() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="infantry_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=20,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=10)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=10.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=8.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 2.0
    assert session._enemy_groups[0].personnel == 9
    assert combat.seconds_until_next_exchange == 2.0


def test_update_combats_keeps_engagement_active_when_attrition_leaves_one_enemy_remaining() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=20,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=3)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=12.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 11.0
    assert combat.seconds_until_next_exchange == 6.0
    assert enemy_group.personnel == 1


def test_update_combats_applies_final_exchange_when_timer_hits_zero_on_exchange_boundary() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=12,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=2)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=6.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=6.0)

    assert session._combats == {}
    assert session._enemy_groups == []
    assert unit.ammo == 26
    assert unit.morale == 11
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="engagement:ended",
            unit_name="u1",
            enemy_group_name="e1",
            phase="ended",
            seconds_remaining=12,
        ),
    )


def test_update_combats_continues_after_resolving_earlier_combat() -> None:
    session = create_default_game_session()
    first_unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(50.0, 50.0), ammo=40, morale=20)
    second_unit = UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(60.0, 60.0), ammo=30, morale=20)
    first_enemy = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=1)
    second_enemy = ZombieGroupState(group_id="e2", position=(60.0, 60.0), personnel=5)
    session._units = [first_unit, second_unit]
    session._enemy_groups = [first_enemy, second_enemy]
    session._combats = {
        "a_first": CombatState(
            combat_id="a_first",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        ),
        "z_second": CombatState(
            combat_id="z_second",
            unit_id="u2",
            enemy_group_id="e2",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=2.0)

    assert "a_first" not in session._combats
    assert session._combats["z_second"].seconds_remaining == 22.0
    assert session._combats["z_second"].seconds_until_next_exchange == 4.0


def test_update_combats_keeps_combat_alive_for_last_second_after_exchange() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=10)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=7.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=6.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 1.0
    assert combat.seconds_until_next_exchange == 1.0
    assert enemy_group.personnel == 9


def test_update_combats_resolves_when_timer_reaches_zero_between_exchanges() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=1.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    assert session._combats == {}
    assert session._enemy_groups == []


def test_update_combats_zero_step_on_one_combat_does_not_block_later_combats() -> None:
    session = create_default_game_session()
    first_unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    second_unit = UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(60.0, 60.0), ammo=30, morale=20)
    first_enemy = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    second_enemy = ZombieGroupState(group_id="e2", position=(60.0, 60.0), personnel=5)
    session._units = [first_unit, second_unit]
    session._enemy_groups = [first_enemy, second_enemy]
    session._combats = {
        "a_first": CombatState(
            combat_id="a_first",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=5.0,
            total_seconds=24.0,
            seconds_until_next_exchange=0.0,
        ),
        "z_second": CombatState(
            combat_id="z_second",
            unit_id="u2",
            enemy_group_id="e2",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=2.0)

    assert session._combats["a_first"].seconds_until_next_exchange == 5.0
    assert first_enemy.personnel == 4
    assert session._combats["z_second"].seconds_remaining == 22.0
    assert session._combats["z_second"].seconds_until_next_exchange == 4.0


def test_combat_notifications_expire_after_display_window() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=3.0,
        )
    ]

    session._update_combat_notifications(elapsed_seconds=1.0)
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=2,
        ),
    )

    session._update_combat_notifications(elapsed_seconds=2.5)
    assert session.combat_notifications_snapshot() == ()


def test_combat_notifications_snapshot_keeps_zero_seconds_without_fallback_to_one() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=0.0,
        )
    ]

    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=0,
        ),
    )


def test_apply_combat_attrition_uses_expected_suppression_for_infantry_and_mechanized_units() -> None:
    session = create_default_game_session()
    infantry = UnitState(
        unit_id="alpha",
        unit_type_id="infantry_squad",
        position=(0.0, 0.0),
        ammo=90,
        morale=72,
    )
    infantry_enemy = ZombieGroupState(group_id="e1", position=(0.0, 0.0), personnel=7)

    session._apply_combat_attrition(infantry, infantry_enemy)

    assert infantry_enemy.personnel == 6
    assert infantry.ammo == 82
    assert infantry.morale == 70

    mechanized = UnitState(
        unit_id="bravo",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        ammo=120,
        morale=81,
    )
    mechanized_enemy = ZombieGroupState(group_id="e2", position=(0.0, 0.0), personnel=7)

    session._apply_combat_attrition(mechanized, mechanized_enemy)

    assert mechanized_enemy.personnel == 5
    assert mechanized.ammo == 106
    assert mechanized.morale == 80


def test_bounds_overlap_requires_axis_overlap_in_each_direction() -> None:
    session = create_default_game_session()

    assert session._bounds_overlap((0, 0, 10, 10), (5, 5, 15, 15)) is True
    assert session._bounds_overlap((0, 0, 10, 10), (11, 0, 20, 10)) is False
    assert session._bounds_overlap((11, 0, 20, 10), (0, 0, 10, 10)) is False
    assert session._bounds_overlap((0, 0, 10, 10), (0, 11, 10, 20)) is False
    assert session._bounds_overlap((0, 11, 10, 20), (0, 0, 10, 10)) is False


def test_refresh_supply_route_removes_route_when_required_objects_disappear() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True
    session._selected_unit_id = "bravo_mechanized"
    session.handle_supply_route(source_object_id="landing_pad", destination_object_id="hq")
    route = next(iter(session._supply_routes.values()))

    session._landing_pads.pop("landing_pad")
    session._refresh_supply_route(route)

    assert session.supply_routes_snapshot() == ()


def test_refresh_supply_route_removes_route_when_unit_disappears() -> None:
    session = create_default_game_session()
    route = SupplyRouteState(
        route_id="missing-unit-route",
        unit_id="ghost_unit",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
    )
    session._supply_routes = {route.route_id: route}

    session._refresh_supply_route(route)

    assert session._supply_routes == {}


def test_update_supply_routes_continues_after_removing_missing_unit_route() -> None:
    session = create_default_game_session()
    session._units = [UnitState(unit_id="u2", unit_type_id="mechanized_squad", position=(10.0, 10.0))]
    handled_route_ids: list[str] = []
    session._refresh_supply_route = (  # type: ignore[method-assign]
        lambda route, *, elapsed_seconds=0.0: handled_route_ids.append(route.route_id)
    )
    session._supply_routes = {
        "a-missing": SupplyRouteState(
            route_id="a-missing",
            unit_id="ghost_unit",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
        "z-present": SupplyRouteState(
            route_id="z-present",
            unit_id="u2",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        ),
    }

    session._update_supply_routes(elapsed_seconds=0.0)

    assert "a-missing" not in session._supply_routes
    assert handled_route_ids == ["z-present"]


def test_is_valid_supply_route_pair_requires_both_source_and_destination() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session._objective_status["landing_pad_cleared"] = True

    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="hq") is True
    assert session._is_valid_supply_route_pair(source_object_id="landing_pad", destination_object_id="missing") is False
    assert session._is_valid_supply_route_pair(source_object_id="missing", destination_object_id="hq") is False


def test_tick_passes_runtime_snapshots_and_elapsed_times_to_subsystems() -> None:
    class RecordingEvaluator:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def evaluate(self, **kwargs):
            self.calls.append(kwargs)
            return dict(kwargs["current_status"])

    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    evaluator = RecordingEvaluator()
    session._mission_objectives_evaluator = evaluator
    recorded: dict[str, object] = {}

    session._consume_supply_elapsed_seconds = lambda: 7.5
    session._consume_combat_elapsed_seconds = lambda: 3.25
    session._update_combat_notifications = lambda *, elapsed_seconds: recorded.setdefault(
        "combat_notifications", elapsed_seconds
    )
    session._update_combats = lambda *, elapsed_seconds: recorded.setdefault("combats", elapsed_seconds)
    session._update_units_position = lambda: recorded.setdefault("units_position", True)
    session._start_combats_for_colliding_units = lambda: recorded.setdefault("start_combats", True)
    session._investigate_recon_sites = lambda: recorded.setdefault("investigate_recon_sites", True)
    session._update_main_objective_reports = lambda: recorded.setdefault("main_objective_reports", True)
    session._update_supply_network = lambda *, elapsed_seconds: recorded.setdefault(
        "supply_network", elapsed_seconds
    )
    session._update_supply_routes = lambda *, elapsed_seconds: recorded.setdefault("supply_routes", elapsed_seconds)

    session.tick()

    assert recorded == {
        "combat_notifications": 3.25,
        "combats": 3.25,
        "units_position": True,
        "start_combats": True,
        "investigate_recon_sites": True,
        "main_objective_reports": True,
        "supply_network": 7.5,
        "supply_routes": 7.5,
    }
    assert len(evaluator.calls) == 1
    assert evaluator.calls[0]["units"] == session.units_snapshot()
    assert evaluator.calls[0]["map_objects"] == session.map_objects_snapshot()
    assert evaluator.calls[0]["current_status"] == session.objective_status_snapshot()
    assert evaluator.calls[0]["supply_routes"] == session.supply_routes_state_snapshot()
    assert evaluator.calls[0]["enemy_groups"] == session.enemy_groups_state_snapshot()
    assert evaluator.calls[0]["discovered_reinforcements_count"] == 0


def test_enemy_groups_state_snapshot_exposes_exact_keys_for_objective_evaluation() -> None:
    session = create_default_game_session()
    session._enemy_groups = [
        ZombieGroupState(
            group_id="z1",
            position=(120.0, 230.0),
            name="Patrol",
            personnel=5,
        )
    ]

    assert session.enemy_groups_state_snapshot() == [
        {
            "group_id": "z1",
            "position": (120.0, 230.0),
            "name": "Patrol",
            "personnel": 5,
        }
    ]


def test_supply_routes_state_snapshot_exposes_route_id_and_exact_keys() -> None:
    session = create_default_game_session()
    session._supply_routes = {
        "route-1": SupplyRouteState(
            route_id="route-1",
            unit_id="bravo_mechanized",
            source_object_id="landing_pad",
            destination_object_id="hq",
            phase="to_pickup",
        )
    }

    assert session.supply_routes_state_snapshot() == [
        {
            "route_id": "route-1",
            "unit_id": "bravo_mechanized",
            "source_object_id": "landing_pad",
            "destination_object_id": "hq",
            "phase": "to_pickup",
        }
    ]


def test_reset_clears_internal_combat_notifications_list() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=2.0,
        )
    ]

    session.reset()

    assert session._combat_notifications == []
    assert session.combat_notifications_snapshot() == ()


def test_recon_investigation_without_unit_on_site_does_not_refresh_map_objects() -> None:
    session = create_default_game_session(search_roll_provider=lambda: 0.0)
    session.update_map_dimensions(width=960, height=640)
    refresh_calls: list[str] = []
    session._refresh_dynamic_map_objects = lambda: refresh_calls.append("refresh")

    session._investigate_recon_sites()

    assert refresh_calls == []
    assert session._investigated_recon_site_ids == set()


def test_recon_investigation_skips_missing_site_bounds_and_continues_to_later_site() -> None:
    session = create_default_game_session(search_roll_provider=lambda: 1.0)
    session.update_map_dimensions(width=960, height=640)
    session._map_objects = [obj for obj in session._map_objects if obj["id"] != "recon_site_1"]
    site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "recon_site_2")
    left, top, right, bottom = site["bounds"]
    alpha = session._find_unit_by_id("alpha_infantry")
    assert alpha is not None
    alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)

    session._investigate_recon_sites()

    assert "recon_site_2" in session._investigated_recon_site_ids
    assert "recon_site_2" not in {obj["id"] for obj in session.map_objects_snapshot()}


def test_recon_investigation_checks_later_sites_when_first_site_is_empty() -> None:
    session = create_default_game_session(search_roll_provider=lambda: 1.0)
    session.update_map_dimensions(width=960, height=640)
    site = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "recon_site_2")
    left, top, right, bottom = site["bounds"]
    alpha = session._find_unit_by_id("alpha_infantry")
    assert alpha is not None
    alpha.position = ((left + right) / 2.0, (top + bottom) / 2.0)

    session._investigate_recon_sites()

    assert "recon_site_2" in session._investigated_recon_site_ids
    assert "recon_site_2" not in {obj["id"] for obj in session.map_objects_snapshot()}


def test_set_unit_target_assigns_tuple_path_for_non_matching_destination() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0))

    session._set_unit_target(unit, (140.0, 100.0), road_mode="off")

    assert unit.target == (140.0, 100.0)
    assert unit.path == ((140.0, 100.0),)


def test_reinforcement_templates_from_config_uses_empty_commander_and_zero_personnel_defaults(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.game_session._DEFAULT_SCENARIO",
        _scenario_config_for_game_session_tests(
            reinforcements=(
                {
                    "unit_id": "echo",
                    "unit_type_id": "infantry_squad",
                    "name": "Echo",
                },
            ),
        ),
    )

    assert _reinforcement_templates_from_config() == (
        ReinforcementTemplate(
            unit_id="echo",
            unit_type_id="infantry_squad",
            name="Echo",
            commander=CommanderState(name="", experience_level="basic"),
            experience_level="basic",
            personnel=0,
            morale=0,
            ammo=0,
            rations=0,
            fuel=0,
        ),
    )


def test_create_default_game_session_initializes_empty_roads_collection() -> None:
    session = create_default_game_session()

    assert session._roads == []


def test_reset_clears_enemy_groups_and_mission_reports_collections() -> None:
    session = create_default_game_session()
    session._enemy_groups = [
        ZombieGroupState(group_id="z1", position=(10.0, 10.0), name="patrol", personnel=4)
    ]
    session._mission_reports = [
        MissionReportSnapshot(
            report_id="report",
            title_key="title",
            message_key="message",
        )
    ]

    session.reset()

    assert session._enemy_groups == []
    assert session._mission_reports == []


def test_update_map_dimensions_retargets_units_with_supply_route_aware_road_mode_after_resize() -> None:
    session = create_default_game_session()
    session._map_size = (100, 100)
    session._map_objects = [{"id": "hq", "bounds": (0, 0, 10, 10)}]
    session._roads = [{"id": "road", "points": ((0.0, 0.0), (10.0, 10.0))}]
    session._units_initialized = True
    session._units = [
        UnitState(
            unit_id="u1",
            unit_type_id="mechanized_squad",
            position=(25.0, 25.0),
            target=(75.0, 75.0),
        )
    ]

    recorded_road_modes: list[str | None] = []
    session._build_map_objects = lambda width, height: session._map_objects  # type: ignore[method-assign]
    session._build_roads = lambda: session._roads  # type: ignore[method-assign]
    session._sync_bases_to_map_objects = lambda: None  # type: ignore[method-assign]
    session._sync_landing_pads_to_map_objects = lambda: None  # type: ignore[method-assign]
    session._clamp_point_to_map = lambda position, *, unit_type_id: position  # type: ignore[method-assign]
    session._unit_has_supply_route = lambda unit_id: unit_id == "u1"  # type: ignore[method-assign]
    session._road_mode_for_unit = lambda unit_type_id: "off"  # type: ignore[method-assign]
    session._set_unit_target = (  # type: ignore[method-assign]
        lambda unit, target, *, road_mode: recorded_road_modes.append(road_mode)
    )
    session._clamp_enemy_groups_to_map = lambda: None  # type: ignore[method-assign]
    session._refresh_supply_route_targets = lambda: None  # type: ignore[method-assign]

    session.update_map_dimensions(width=120, height=120)

    assert recorded_road_modes == ["only"]
