# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_reinforcement_templates_match_default_scenario_contract() -> None:
    expected_templates = (
        ReinforcementTemplate(
            unit_id="charlie_infantry",
            unit_type_id="infantry_squad",
            name="3. Druzyna Charlie",
            commander=CommanderState(name="sier. Lena Brzeg", rank="sergeant", experience_level="basic"),
            experience_level="basic",
            personnel=9,
            morale=68,
            ammo=74,
            rations=12,
            fuel=0,
            equipment=UnitEquipmentState(
                primary_weapon_key="game.unit.armament.rifles_lmg",
                vest_key="game.unit.vest.light_plate",
            ),
            organization=UnitOrganizationState(max_subordinate_units=3),
        ),
        ReinforcementTemplate(
            unit_id="delta_infantry",
            unit_type_id="infantry_squad",
            name="4. Druzyna Delta",
            commander=CommanderState(name="sier. Oskar Lis", rank="sergeant", experience_level="basic"),
            experience_level="basic",
            personnel=8,
            morale=71,
            ammo=70,
            rations=10,
            fuel=0,
            equipment=UnitEquipmentState(
                primary_weapon_key="game.unit.armament.rifles_lmg",
                vest_key="game.unit.vest.light_plate",
            ),
            organization=UnitOrganizationState(max_subordinate_units=3),
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
                    "equipment": {"primary_weapon_key": 3},
                    "vehicles": [{"vehicle_type_id": "wheeled_apc", "count": "2"}],
                    "organization": {"max_subordinate_units": "3"},
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
                    "equipment": {"support_weapon_key": 22, "vest_key": 23},
                    "vehicles": ["ignored", {"vehicle_type_id": 9, "count": "1"}],
                    "organization": {
                        "formation_level": "platoon",
                        "parent_unit_id": 4,
                        "subordinate_unit_ids": [5, "6"],
                        "max_subordinate_units": 3,
                    },
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
            equipment=UnitEquipmentState(primary_weapon_key="3"),
            vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=2),),
            organization=UnitOrganizationState(max_subordinate_units=3),
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
            equipment=UnitEquipmentState(support_weapon_key="22", vest_key="23"),
            vehicles=(VehicleAssignmentState(vehicle_type_id="9", count=1),),
            organization=UnitOrganizationState(
                formation_level="platoon",
                parent_unit_id="4",
                subordinate_unit_ids=("5", "6"),
                max_subordinate_units=3,
            ),
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
                equipment=UnitEquipmentState(primary_weapon_key="autocannon", vest_key="medium_plate"),
                vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),),
                organization=UnitOrganizationState(
                    formation_level="platoon",
                    subordinate_unit_ids=("alpha", "bravo"),
                    max_subordinate_units=3,
                ),
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
            equipment=UnitEquipmentState(primary_weapon_key="autocannon", vest_key="medium_plate"),
            vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),),
            organization=UnitOrganizationState(
                formation_level="platoon",
                subordinate_unit_ids=("alpha", "bravo"),
                max_subordinate_units=3,
            ),
        )
    ]

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

