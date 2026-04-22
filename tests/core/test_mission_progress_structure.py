from __future__ import annotations

from contracts.game_state import MissionReportSnapshot
from core.mission_progress import (
    MainObjectiveReportRule,
    MissionProgressService,
    main_objective_report_rules_from_config,
)


def test_mission_progress_package_exports_rules_and_service() -> None:
    rules = main_objective_report_rules_from_config(
        (
            {
                "goal_id": "goal_alpha",
                "required_objective_ids": ["a", "b"],
                "report_id": "report_alpha",
                "title_key": "title.alpha",
                "message_key": "message.alpha",
            },
        )
    )
    service = MissionProgressService()
    mission_reports: list[MissionReportSnapshot] = []
    completed: set[str] = set()

    service.update_main_objective_reports(
        rules=rules,
        completed_main_objective_ids=completed,
        objective_status={"a": True, "b": True},
        mission_reports=mission_reports,
    )

    assert rules == (
        MainObjectiveReportRule(
            goal_id="goal_alpha",
            required_objective_ids=("a", "b"),
            report_id="report_alpha",
            title_key="title.alpha",
            message_key="message.alpha",
        ),
    )
    assert completed == {"goal_alpha"}
    assert mission_reports == [
        MissionReportSnapshot(
            report_id="report_alpha",
            title_key="title.alpha",
            message_key="message.alpha",
        )
    ]
