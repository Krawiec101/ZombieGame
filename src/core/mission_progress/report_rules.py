from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MainObjectiveReportRule:
    goal_id: str
    required_objective_ids: tuple[str, ...]
    report_id: str
    title_key: str
    message_key: str


def main_objective_report_rules_from_config(
    mission_reports: Sequence[Mapping[str, Any]],
) -> tuple[MainObjectiveReportRule, ...]:
    return tuple(
        MainObjectiveReportRule(
            goal_id=str(report.get("goal_id", "")),
            required_objective_ids=tuple(
                str(objective_id) for objective_id in report.get("required_objective_ids", [])
            ),
            report_id=str(report.get("report_id", "")),
            title_key=str(report.get("title_key", "")),
            message_key=str(report.get("message_key", "")),
        )
        for report in mission_reports
    )
