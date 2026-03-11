from __future__ import annotations

from core.mission_objectives import (
    MissionObjectiveRule,
    MissionObjectivesEvaluator,
    create_default_mission_objectives_evaluator,
)


def test_default_evaluator_marks_objective_complete_for_motorized_on_landing_pad() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (120.0, 220.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is True


def test_default_evaluator_does_not_complete_for_infantry_on_landing_pad() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "infantry_squad", "position": (120.0, 220.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is False


def test_evaluator_tracks_multiple_objectives_independently() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="a",
                description_key="a",
                required_unit_type_id="infantry_squad",
                target_object_id="hq",
            ),
            MissionObjectiveRule(
                objective_id="b",
                description_key="b",
                required_unit_type_id="motorized_infantry_squad",
                target_object_id="landing_pad",
            ),
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "infantry_squad", "position": (30.0, 30.0)}],
        map_objects=[
            {"id": "hq", "bounds": (0, 0, 50, 50)},
            {"id": "landing_pad", "bounds": (100, 100, 150, 150)},
        ],
        current_status={"a": False, "b": False},
    )

    assert statuses["a"] is True
    assert statuses["b"] is False


def test_objectives_projection_contains_only_contract_fields() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="alpha",
                description_key="objective.alpha",
                required_unit_type_id="infantry_squad",
                target_object_id="hq",
            ),
        ]
    )

    objectives = evaluator.objectives()

    assert objectives == (
        {
            "objective_id": "alpha",
            "description_key": "objective.alpha",
        },
    )


def test_evaluator_keeps_completed_status_true_when_conditions_are_not_met() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status={"motorized_to_landing_pad": True},
    )

    assert statuses["motorized_to_landing_pad"] is True


def test_evaluator_ignores_objects_without_valid_bounds() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (120.0, 220.0)}],
        map_objects=[
            {"id": "landing_pad"},
            {"id": "landing_pad", "bounds": (100, 200, 180)},
        ],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is False


def test_evaluator_ignores_units_with_invalid_position_shape() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[
            {"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": "120,220"},
            {"unit_id": "u2", "unit_type_id": "motorized_infantry_squad", "position": (120.0,)},
        ],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is False


def test_evaluator_treats_target_bounds_edges_as_inside() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    left_top = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (100.0, 200.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )
    right_bottom = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (180.0, 260.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert left_top["motorized_to_landing_pad"] is True
    assert right_bottom["motorized_to_landing_pad"] is True


def test_evaluator_does_not_mutate_input_status_mapping() -> None:
    evaluator = create_default_mission_objectives_evaluator()
    current_status = {"motorized_to_landing_pad": False}

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (120.0, 220.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status=current_status,
    )

    assert current_status == {"motorized_to_landing_pad": False}
    assert statuses is not current_status


def test_evaluator_preserves_status_for_non_boolean_truthy_current_status() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[],
        map_objects=[],
        current_status={"motorized_to_landing_pad": "yes"},
    )

    assert statuses["motorized_to_landing_pad"] is True


def test_evaluator_coerces_map_object_id_to_string_for_lookup() -> None:
    evaluator = MissionObjectivesEvaluator(
        [
            MissionObjectiveRule(
                objective_id="reach_pad",
                description_key="reach_pad.desc",
                required_unit_type_id="1",
                target_object_id="99",
            )
        ]
    )

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": 1, "position": (10.0, 10.0)}],
        map_objects=[{"id": 99, "bounds": (0, 0, 20, 20)}],
        current_status={"reach_pad": False},
    )

    assert statuses["reach_pad"] is True


def test_evaluator_coerces_bounds_values_to_int() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (180.0, 260.0)}],
        map_objects=[{"id": "landing_pad", "bounds": ("100", "200", "180", "260")}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is True


def test_evaluator_accepts_list_position_and_uses_first_two_values() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": [120.0, 220.0, 999.0]}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is True


def test_evaluator_ignores_wrong_unit_type_even_if_inside_target_bounds() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squadx", "position": (120.0, 220.0)}],
        map_objects=[{"id": "landing_pad", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is False


def test_evaluator_does_not_complete_when_target_object_id_not_found() -> None:
    evaluator = create_default_mission_objectives_evaluator()

    statuses = evaluator.evaluate(
        units=[{"unit_id": "u1", "unit_type_id": "motorized_infantry_squad", "position": (120.0, 220.0)}],
        map_objects=[{"id": "other", "bounds": (100, 200, 180, 260)}],
        current_status={"motorized_to_landing_pad": False},
    )

    assert statuses["motorized_to_landing_pad"] is False
