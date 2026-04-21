from __future__ import annotations

from collections.abc import Mapping

from core.mission_objectives import (
    DEFAULT_MISSION_OBJECTIVE_RULES,
    MissionObjectiveRule,
    MissionObjectivesEvaluator,
    _coerce_bounds,
    _load_default_mission_objective_rules,
    create_default_mission_objectives_evaluator,
)
from core.scenario_config import ScenarioConfig


def test_default_evaluator_marks_landing_pad_cleared_when_no_zombies_remain_on_pad() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        enemy_groups=[],
        current_status={"landing_pad_cleared": False},
    )

    assert statuses["landing_pad_cleared"] is True


def test_default_mission_objective_rules_match_scenario_configuration_contract() -> None:
    expected_rules = (
        MissionObjectiveRule(
            objective_id="landing_pad_cleared",
            description_key="mission.objective.landing_pad_cleared",
            required_unit_type_id="",
            target_object_id="landing_pad",
            objective_type="enemy_absent_from_object",
            source_object_id="",
            destination_object_id="",
            required_reinforcements_found=0,
        ),
        MissionObjectiveRule(
            objective_id="supply_route_to_hq",
            description_key="mission.objective.supply_route_to_hq",
            required_unit_type_id="",
            target_object_id="",
            objective_type="supply_route_established",
            source_object_id="landing_pad",
            destination_object_id="hq",
            required_reinforcements_found=0,
        ),
        MissionObjectiveRule(
            objective_id="find_first_missing_detachment",
            description_key="mission.objective.find_first_missing_detachment",
            required_unit_type_id="",
            target_object_id="",
            objective_type="reinforcements_found",
            source_object_id="",
            destination_object_id="",
            required_reinforcements_found=1,
        ),
        MissionObjectiveRule(
            objective_id="find_second_missing_detachment",
            description_key="mission.objective.find_second_missing_detachment",
            required_unit_type_id="",
            target_object_id="",
            objective_type="reinforcements_found",
            source_object_id="",
            destination_object_id="",
            required_reinforcements_found=2,
        ),
    )

    assert DEFAULT_MISSION_OBJECTIVE_RULES == expected_rules
    assert _load_default_mission_objective_rules() == expected_rules


def test_load_default_mission_objective_rules_applies_defaults_and_coercion(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.mission_objectives.load_default_scenario_config",
        lambda: ScenarioConfig(
            scenario_id="scenario",
            campaign_id="campaign",
            default_mission_id="mission",
            mission_id="mission",
            available_mission_ids=("mission",),
            next_mission_id="",
            default_stage_id="stage",
            stage_id="stage",
            available_stage_ids=("stage",),
            map_width_km=20.0,
            map_objects=(),
            recon_sites=(),
            roads=(),
            initial_units=(),
            initial_enemy_groups=(),
            reinforcements=(),
            mission_objectives=(
                {},
                {
                    "objective_id": 12,
                    "description_key": 13,
                    "required_unit_type_id": 14,
                    "target_object_id": 15,
                    "objective_type": 16,
                    "source_object_id": 17,
                    "destination_object_id": 18,
                    "required_reinforcements_found": "2",
                },
            ),
            mission_reports=(),
            stage_events=(),
        ),
    )

    assert _load_default_mission_objective_rules() == (
        MissionObjectiveRule(objective_id="", description_key=""),
        MissionObjectiveRule(
            objective_id="12",
            description_key="13",
            required_unit_type_id="14",
            target_object_id="15",
            objective_type="16",
            source_object_id="17",
            destination_object_id="18",
            required_reinforcements_found=2,
        ),
    )


def test_default_evaluator_keeps_landing_pad_uncleared_when_zombies_are_on_pad() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        enemy_groups=[{"group_id": "z1", "position": (120.0, 220.0)}],
        current_status={"landing_pad_cleared": False},
    )

    assert statuses["landing_pad_cleared"] is False


def test_default_evaluator_marks_supply_route_objective_when_route_exists() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        supply_routes=[{"source_object_id": "landing_pad", "destination_object_id": "hq"}],
        current_status={"supply_route_to_hq": False},
    )

    assert statuses["supply_route_to_hq"] is True


def test_default_evaluator_tracks_found_reinforcements_thresholds() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        discovered_reinforcements_count=1,
        current_status={
            "find_first_missing_detachment": False,
            "find_second_missing_detachment": False,
        },
    )

    assert statuses["find_first_missing_detachment"] is True
    assert statuses["find_second_missing_detachment"] is False


def test_default_evaluator_keeps_reinforcement_objectives_false_without_discoveries() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status={},
    )

    assert statuses["find_first_missing_detachment"] is False
    assert statuses["find_second_missing_detachment"] is False


def test_default_evaluator_uses_zero_reinforcement_default_when_argument_is_omitted() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status={"landing_pad_cleared": False},
    )

    assert statuses["find_first_missing_detachment"] is False
    assert statuses["find_second_missing_detachment"] is False


def test_evaluate_signature_exposes_zero_reinforcement_default() -> None:
    kwdefaults = MissionObjectivesEvaluator.evaluate.__kwdefaults__

    assert kwdefaults is not None
    assert kwdefaults["discovered_reinforcements_count"] == 0


def test_create_default_mission_objectives_evaluator_uses_default_rules_constant() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert evaluator.objectives() == tuple(
        {
            "objective_id": rule.objective_id,
            "description_key": rule.description_key,
        }
        for rule in DEFAULT_MISSION_OBJECTIVE_RULES
    )


def test_unit_on_object_rule_still_supports_existing_projection_and_bounds_logic() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="reach_pad",
                description_key="objective.reach_pad",
                required_unit_type_id="mechanized_squad",
                target_object_id="landing_pad",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "mechanized_squad", "position": [180.0, 260.0, 0.0]}],
        map_objects=[{"id": "landing_pad", "bounds": ("100", "200", "180", "260")}],
        current_status={"reach_pad": False},
    )

    assert evaluator.objectives() == (
        {
            "objective_id": "reach_pad",
            "description_key": "objective.reach_pad",
        },
    )
    assert statuses["reach_pad"] is True


def test_evaluator_keeps_completed_status_true_when_conditions_are_no_longer_met() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status={"find_second_missing_detachment": True},
    )

    assert statuses["find_second_missing_detachment"] is True


def test_evaluator_continues_after_reinforcement_objective_to_resolve_later_rules() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="find_detachment",
                description_key="objective.find_detachment",
                objective_type="reinforcements_found",
                required_reinforcements_found=1,
            ),
            MissionObjectiveRule(
                objective_id="reach_pad",
                description_key="objective.reach_pad",
                required_unit_type_id="mechanized_squad",
                target_object_id="landing_pad",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_type_id": "mechanized_squad", "position": (150.0, 230.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"find_detachment": False, "reach_pad": False},
        discovered_reinforcements_count=1,
    )

    assert statuses == {
        "find_detachment": True,
        "reach_pad": True,
    }


def test_evaluator_requests_missing_status_with_false_default() -> None:
    class RecordingStatusMapping(Mapping[str, bool]):
        def __init__(self) -> None:
            self.defaults: list[object] = []

        def __getitem__(self, key: str) -> bool:
            raise KeyError(key)

        def __iter__(self):
            return iter(())

        def __len__(self) -> int:
            return 0

        def get(self, key: str, default=None):  # type: ignore[override]
            self.defaults.append(default)
            return default

    evaluator = create_default_mission_objectives_evaluator()
    current_status = RecordingStatusMapping()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status=current_status,
    )

    assert current_status.defaults == [False, False, False, False]
    assert statuses == {
        "landing_pad_cleared": False,
        "supply_route_to_hq": False,
        "find_first_missing_detachment": False,
        "find_second_missing_detachment": False,
    }


def test_evaluator_does_not_mutate_input_status_mapping() -> None:
    evaluator = create_default_mission_objectives_evaluator()
    current_status = {"find_first_missing_detachment": False}

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        discovered_reinforcements_count=1,
        current_status=current_status,
    )

    assert current_status == {"find_first_missing_detachment": False}
    assert statuses is not current_status


def test_evaluator_treats_missing_status_as_false_even_for_truthy_custom_mapping_fallbacks() -> None:
    missing_default = object()

    class TruthyMissingStatusMapping(Mapping[str, bool]):
        def __getitem__(self, key: str) -> bool:
            raise KeyError(key)

        def __iter__(self):
            return iter(())

        def __len__(self) -> int:
            return 0

        def get(self, key: str, default=missing_default):  # type: ignore[override]
            if default is missing_default:
                return "missing-without-default"
            if default is None:
                return "missing-with-none"
            return default

    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status=TruthyMissingStatusMapping(),
    )

    assert statuses == {
        "landing_pad_cleared": False,
        "supply_route_to_hq": False,
        "find_first_missing_detachment": False,
        "find_second_missing_detachment": False,
    }


def test_unit_on_object_skips_non_matching_units_before_later_valid_match() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[
                {"unit_type_id": "infantry_squad", "position": (140.0, 220.0)},
                {"unit_type_id": "mechanized_squad", "position": (150.0, 230.0)},
            ],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is True
    )


def test_unit_on_object_accepts_two_point_positions_after_invalid_required_unit_entry() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[
                {"unit_type_id": "mechanized_squad", "position": None},
                {"unit_type_id": "mechanized_squad", "position": [150.0, 230.0]},
            ],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is True
    )


def test_unit_on_object_returns_false_for_non_empty_bounds_with_wrong_size() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"unit_type_id": "mechanized_squad", "position": (150.0, 230.0)}],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180)},
        )
        is False
    )


def test_unit_on_object_requires_position_to_be_below_top_edge() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"unit_type_id": "mechanized_squad", "position": (150.0, 190.0)}],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_unit_on_object_requires_position_to_be_left_of_right_edge() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"unit_type_id": "mechanized_squad", "position": (220.0, 230.0)}],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_unit_on_object_ignores_none_key_alias_for_unit_type_id() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{None: "mechanized_squad", "position": (150.0, 230.0)}],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_unit_on_object_does_not_treat_missing_unit_type_as_string_none() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"position": (150.0, 230.0)}],
            required_unit_type_id="None",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_unit_on_object_ignores_empty_string_key_alias_for_unit_type_id() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"": "mechanized_squad", "position": (150.0, 230.0)}],
            required_unit_type_id="mechanized_squad",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_unit_on_object_does_not_treat_missing_unit_type_as_matching_fallback_value() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._unit_on_object(
            units=[{"position": (150.0, 230.0)}],
            required_unit_type_id="XXXX",
            target_object_id="landing_pad",
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_enemy_absent_from_object_skips_invalid_groups_before_detecting_enemy_inside() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._enemy_absent_from_object(
            target_object_id="landing_pad",
            enemy_groups=[
                {"position": None},
                {"position": (140.0, 220.0)},
            ],
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is False
    )


def test_enemy_absent_from_object_requires_enemy_inside_on_both_axes() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._enemy_absent_from_object(
            target_object_id="landing_pad",
            enemy_groups=[{"position": (99.0, 220.0)}],
            object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
        )
        is True
    )


def test_enemy_absent_from_object_treats_all_edges_as_inside_target_bounds() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    for position in (
        (100.0, 220.0),
        (180.0, 220.0),
        (140.0, 200.0),
        (140.0, 260.0),
    ):
        assert (
            evaluator._enemy_absent_from_object(
                target_object_id="landing_pad",
                enemy_groups=[{"position": position}],
                object_bounds_by_id={"landing_pad": (100, 200, 180, 260)},
            )
            is False
        )


def test_supply_route_established_allows_empty_source_when_route_dict_omits_source_key() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._supply_route_established(
            supply_routes=[{"destination_object_id": "hq"}],
            source_object_id="",
            destination_object_id="hq",
        )
        is True
    )


def test_supply_route_established_allows_empty_destination_when_route_dict_omits_destination_key() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._supply_route_established(
            supply_routes=[{"source_object_id": "landing_pad"}],
            source_object_id="landing_pad",
            destination_object_id="",
        )
        is True
    )


def test_supply_route_established_skips_wrong_source_before_later_match() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._supply_route_established(
            supply_routes=[
                {"source_object_id": "hq", "destination_object_id": "landing_pad"},
                {"source_object_id": "landing_pad", "destination_object_id": "hq"},
            ],
            source_object_id="landing_pad",
            destination_object_id="hq",
        )
        is True
    )


def test_supply_route_established_skips_wrong_destination_before_later_match() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._supply_route_established(
            supply_routes=[
                {"source_object_id": "landing_pad", "destination_object_id": "forward_base"},
                {"source_object_id": "landing_pad", "destination_object_id": "hq"},
            ],
            source_object_id="landing_pad",
            destination_object_id="hq",
        )
        is True
    )


def test_supply_route_established_returns_false_when_no_route_matches() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    assert (
        evaluator._supply_route_established(
            supply_routes=[],
            source_object_id="landing_pad",
            destination_object_id="hq",
        )
        is False
    )


def test_unit_on_object_ignores_unrelated_map_object_with_non_numeric_bounds() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="reach_pad",
                description_key="objective.reach_pad",
                required_unit_type_id="mechanized_squad",
                target_object_id="landing_pad",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_type_id": "mechanized_squad", "position": (150.0, 230.0)}],
        map_objects=[
            {"id": "noise", "bounds": ["bad", 0, 1, 1]},
            {"id": "landing_pad", "bounds": (100, 200, 180, 260)},
        ],
        current_status={"reach_pad": False},
    )

    assert statuses["reach_pad"] is True


def test_load_default_mission_objective_rules_preserves_explicit_fields_and_empty_defaults(monkeypatch) -> None:
    class ScenarioStub:
        mission_objectives = (
            {
                "objective_id": "reach_relay",
                "description_key": "objective.reach_relay",
                "required_unit_type_id": "engineer_team",
                "target_object_id": "relay",
            },
            {},
        )

    monkeypatch.setattr(
        "core.mission_objectives.load_default_scenario_config",
        lambda: ScenarioStub(),
    )

    assert _load_default_mission_objective_rules() == (
        MissionObjectiveRule(
            objective_id="reach_relay",
            description_key="objective.reach_relay",
            required_unit_type_id="engineer_team",
            target_object_id="relay",
        ),
        MissionObjectiveRule(
            objective_id="",
            description_key="",
            required_unit_type_id="",
            target_object_id="",
        ),
    )


def test_evaluator_distinguishes_missing_map_object_id_from_literal_none() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="reach_none",
                description_key="objective.reach_none",
                required_unit_type_id="mechanized_squad",
                target_object_id="None",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_type_id": "mechanized_squad", "position": (150.0, 150.0)}],
        map_objects=[
            {"id": "None", "bounds": (0, 0, 10, 10)},
            {"bounds": (100, 100, 200, 200)},
        ],
        current_status={"reach_none": False},
    )

    assert statuses["reach_none"] is False


def test_evaluator_distinguishes_missing_map_object_id_from_literal_xxxx() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="reach_xxxx",
                description_key="objective.reach_xxxx",
                required_unit_type_id="mechanized_squad",
                target_object_id="XXXX",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_type_id": "mechanized_squad", "position": (350.0, 350.0)}],
        map_objects=[
            {"id": "XXXX", "bounds": (0, 0, 10, 10)},
            {"bounds": (300, 300, 400, 400)},
        ],
        current_status={"reach_xxxx": False},
    )

    assert statuses["reach_xxxx"] is False


def test_coerce_bounds_returns_none_for_non_numeric_values() -> None:
    assert _coerce_bounds(["bad", 0, 1, 1]) is None
    assert _coerce_bounds((100, "200", 180.8, 260)) == (100, 200, 180, 260)
