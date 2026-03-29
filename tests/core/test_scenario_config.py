from __future__ import annotations

import json

from core.scenario_config import load_default_scenario_config, load_scenario_config


def test_default_scenario_config_contains_map_layout_and_story_data() -> None:
    scenario = load_default_scenario_config()

    assert scenario.scenario_id == "default_operation"
    assert scenario.campaign_id == "northern_recovery"
    assert scenario.default_mission_id == "mission_1_secure_landing_zone"
    assert scenario.mission_id == "mission_1_secure_landing_zone"
    assert scenario.available_mission_ids == (
        "mission_1_secure_landing_zone",
        "mission_2_reach_relay",
    )
    assert scenario.next_mission_id == "mission_2_reach_relay"
    assert scenario.default_stage_id == "stage_1"
    assert scenario.stage_id == "stage_1"
    assert scenario.available_stage_ids == ("stage_1",)
    assert scenario.stage_events == ()
    assert scenario.map_width_km == 20.0
    assert {item["id"] for item in scenario.map_objects} == {"hq", "landing_pad"}
    assert {item["id"] for item in scenario.recon_sites} == {
        "recon_site_1",
        "recon_site_2",
        "recon_site_3",
        "recon_site_4",
    }
    assert [road["id"] for road in scenario.roads] == ["main_supply_road"]
    assert [objective["objective_id"] for objective in scenario.mission_objectives] == [
        "landing_pad_cleared",
        "supply_route_to_hq",
        "find_first_missing_detachment",
        "find_second_missing_detachment",
    ]
    assert [report["report_id"] for report in scenario.mission_reports] == [
        "hq_report_secure_landing_pad_and_route",
        "hq_report_find_first_missing_detachment",
        "hq_report_find_second_missing_detachment",
    ]


def test_default_scenario_config_starts_all_commanders_as_sergeants_with_basic_experience() -> None:
    scenario = load_default_scenario_config()

    commander_names = [
        unit["commander"]["name"] for unit in (*scenario.initial_units, *scenario.reinforcements)
    ]
    commander_experience_levels = [
        unit["commander"]["experience_level"] for unit in (*scenario.initial_units, *scenario.reinforcements)
    ]
    unit_experience_levels = [
        unit["experience_level"] for unit in (*scenario.initial_units, *scenario.reinforcements)
    ]

    assert commander_names == [
        "sier. Anna Sowa",
        "sier. Marek Wolny",
        "sier. Lena Brzeg",
        "sier. Oskar Lis",
    ]
    assert commander_experience_levels == ["basic", "basic", "basic", "basic"]
    assert unit_experience_levels == ["basic", "basic", "basic", "basic"]


def test_campaign_config_can_select_follow_up_mission_with_its_own_events() -> None:
    scenario = load_default_scenario_config(mission_id="mission_2_reach_relay")

    assert scenario.mission_id == "mission_2_reach_relay"
    assert scenario.next_mission_id == ""
    assert scenario.stage_id == "stage_1"
    assert scenario.stage_events == (
        {
            "event_id": "relay_distress_call",
            "trigger": {"type": "mission_started"},
            "effects": [
                {
                    "type": "hq_report",
                    "report_id": "hq_report_relay_distress_call",
                }
            ],
        },
    )
    assert [unit["unit_id"] for unit in scenario.initial_units] == ["alpha_infantry"]
    assert [group["group_id"] for group in scenario.initial_enemy_groups] == ["relay_outskirts_zombies"]


def _load_scenario_from_raw_data(monkeypatch, raw_data: dict[str, object], **kwargs):
    monkeypatch.setattr(
        "core.scenario_config.Path.read_text",
        lambda self, encoding="utf-8": json.dumps(raw_data),
    )
    return load_scenario_config("ignored.json", **kwargs)


def test_scenario_config_can_select_non_default_stage_with_stage_specific_payload(monkeypatch) -> None:
    scenario = _load_scenario_from_raw_data(
        monkeypatch,
        {
            "default_mission_id": "mission_alpha",
            "missions": [
                {
                    "mission_id": "mission_alpha",
                    "default_stage_id": "stage_1",
                    "next_mission_id": "mission_bravo",
                    "stages": [
                        {
                            "stage_id": "stage_1",
                            "events": [{"event_id": "intro"}],
                            "mission": {
                                "objectives": [{"objective_id": "secure_alpha"}],
                                "reports": [{"report_id": "alpha_report"}],
                            },
                            "initial_state": {
                                "units": [{"unit_id": "alpha"}],
                                "enemy_groups": [{"group_id": "alpha_enemy"}],
                                "reinforcements": [{"unit_id": "alpha_backup"}],
                            },
                        },
                        {
                            "stage_id": "stage_2",
                            "events": [{"event_id": "counterattack"}],
                            "mission": {
                                "objectives": [{"objective_id": "secure_bravo"}],
                                "reports": [{"report_id": "bravo_report"}],
                            },
                            "initial_state": {
                                "units": [{"unit_id": "bravo"}],
                                "enemy_groups": [{"group_id": "bravo_enemy"}],
                                "reinforcements": [{"unit_id": "bravo_backup"}],
                            },
                        },
                    ],
                }
            ],
        },
        stage_id="stage_2",
    )

    assert scenario.default_mission_id == "mission_alpha"
    assert scenario.mission_id == "mission_alpha"
    assert scenario.available_stage_ids == ("stage_1", "stage_2")
    assert scenario.default_stage_id == "stage_1"
    assert scenario.stage_id == "stage_2"
    assert scenario.stage_events == ({"event_id": "counterattack"},)
    assert scenario.mission_objectives == ({"objective_id": "secure_bravo"},)
    assert scenario.mission_reports == ({"report_id": "bravo_report"},)
    assert scenario.initial_units == ({"unit_id": "bravo"},)
    assert scenario.initial_enemy_groups == ({"group_id": "bravo_enemy"},)
    assert scenario.reinforcements == ({"unit_id": "bravo_backup"},)


def test_scenario_config_falls_back_to_first_mission_and_stage_when_requested_ids_are_missing(monkeypatch) -> None:
    scenario = _load_scenario_from_raw_data(
        monkeypatch,
        {
            "default_mission_id": "",
            "missions": [
                {
                    "mission_id": "mission_alpha",
                    "default_stage_id": "",
                    "next_mission_id": "mission_bravo",
                    "stages": [
                        {
                            "stage_id": "stage_1",
                            "events": [{"event_id": "alpha_stage_1"}],
                            "mission": {
                                "objectives": [{"objective_id": "alpha_objective"}],
                                "reports": [{"report_id": "alpha_report"}],
                            },
                            "initial_state": {
                                "units": [{"unit_id": "alpha"}],
                                "enemy_groups": [{"group_id": "alpha_enemy"}],
                                "reinforcements": [{"unit_id": "alpha_backup"}],
                            },
                        }
                    ],
                },
                {
                    "mission_id": "mission_bravo",
                    "default_stage_id": "stage_2",
                    "next_mission_id": "",
                    "stages": [
                        {
                            "stage_id": "stage_2",
                            "events": [{"event_id": "bravo_stage_2"}],
                            "mission": {
                                "objectives": [{"objective_id": "bravo_objective"}],
                                "reports": [{"report_id": "bravo_report"}],
                            },
                            "initial_state": {
                                "units": [{"unit_id": "bravo"}],
                                "enemy_groups": [{"group_id": "bravo_enemy"}],
                                "reinforcements": [{"unit_id": "bravo_backup"}],
                            },
                        }
                    ],
                },
            ],
        },
        mission_id="missing_mission",
        stage_id="missing_stage",
    )

    assert scenario.available_mission_ids == ("mission_alpha", "mission_bravo")
    assert scenario.default_mission_id == "mission_alpha"
    assert scenario.mission_id == "mission_alpha"
    assert scenario.next_mission_id == "mission_bravo"
    assert scenario.available_stage_ids == ("stage_1",)
    assert scenario.default_stage_id == "stage_1"
    assert scenario.stage_id == "stage_1"
    assert scenario.stage_events == ({"event_id": "alpha_stage_1"},)
    assert scenario.mission_objectives == ({"objective_id": "alpha_objective"},)
    assert scenario.mission_reports == ({"report_id": "alpha_report"},)
    assert scenario.initial_units == ({"unit_id": "alpha"},)
    assert scenario.initial_enemy_groups == ({"group_id": "alpha_enemy"},)
    assert scenario.reinforcements == ({"unit_id": "alpha_backup"},)


def test_scenario_config_uses_empty_defaults_when_sections_have_wrong_shape(monkeypatch) -> None:
    scenario = _load_scenario_from_raw_data(
        monkeypatch,
        {
            "scenario": ["wrong"],
            "campaign": ["wrong"],
            "map": {
                "width_km": 12,
                "objects": [{"id": "hq"}],
                "recon_sites": "wrong",
                "roads": None,
            },
            "missions": "wrong",
        },
    )

    assert scenario.scenario_id == "default_scenario"
    assert scenario.campaign_id == "default_campaign"
    assert scenario.default_mission_id == "mission_1"
    assert scenario.mission_id == "mission_1"
    assert scenario.available_mission_ids == ()
    assert scenario.next_mission_id == ""
    assert scenario.default_stage_id == "default_stage"
    assert scenario.stage_id == "default_stage"
    assert scenario.available_stage_ids == ()
    assert scenario.map_width_km == 12.0
    assert scenario.map_objects == ({"id": "hq"},)
    assert scenario.recon_sites == ()
    assert scenario.roads == ()
    assert scenario.initial_units == ()
    assert scenario.initial_enemy_groups == ()
    assert scenario.reinforcements == ()
    assert scenario.mission_objectives == ()
    assert scenario.mission_reports == ()
    assert scenario.stage_events == ()
