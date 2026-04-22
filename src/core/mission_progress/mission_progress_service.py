from __future__ import annotations

from collections.abc import Callable, Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from typing import Any

from contracts.game_state import MissionReportSnapshot
from core.model.units import ReinforcementTemplate, UnitState

from .report_rules import MainObjectiveReportRule

MapBoundsResolver = Callable[[str], tuple[int, int, int, int] | None]
PointInBoundsChecker = Callable[[tuple[float, float], tuple[int, int, int, int]], bool]
RefreshMapObjects = Callable[[], None]
RevealReinforcementChecker = Callable[[], bool]
SpawnReinforcement = Callable[[str], None]


@dataclass(frozen=True)
class MissionProgressService:
    def should_reveal_reinforcement(
        self,
        *,
        reinforcement_templates: Sequence[ReinforcementTemplate],
        found_reinforcement_unit_ids: set[str],
        investigated_recon_site_ids: set[str],
        recon_site_count: int,
        search_roll_provider: Callable[[], float],
    ) -> bool:
        remaining_reinforcements = len(reinforcement_templates) - len(found_reinforcement_unit_ids)
        remaining_sites = recon_site_count - len(investigated_recon_site_ids) + 1
        if remaining_reinforcements <= 0 or remaining_sites <= 0:
            return False
        if remaining_reinforcements >= remaining_sites:
            return True
        reveal_probability = remaining_reinforcements / float(remaining_sites)
        return float(search_roll_provider()) <= reveal_probability

    def investigate_recon_sites(
        self,
        *,
        recon_site_layout: Sequence[Mapping[str, Any]],
        investigated_recon_site_ids: set[str],
        units: Sequence[UnitState],
        map_object_bounds: MapBoundsResolver,
        point_in_bounds: PointInBoundsChecker,
        should_reveal_reinforcement: RevealReinforcementChecker,
        spawn_next_reinforcement: SpawnReinforcement,
        refresh_dynamic_map_objects: RefreshMapObjects,
    ) -> None:
        newly_investigated = False
        for layout in recon_site_layout:
            site_id = str(layout["id"])
            if site_id in investigated_recon_site_ids:
                continue

            site_bounds = map_object_bounds(site_id)
            if site_bounds is None:
                continue

            if not any(point_in_bounds(unit.position, site_bounds) for unit in units):
                continue

            investigated_recon_site_ids.add(site_id)
            newly_investigated = True
            if should_reveal_reinforcement():
                spawn_next_reinforcement(site_id)

        if newly_investigated:
            refresh_dynamic_map_objects()

    def update_main_objective_reports(
        self,
        *,
        rules: Sequence[MainObjectiveReportRule],
        completed_main_objective_ids: set[str],
        objective_status: Mapping[str, bool],
        mission_reports: MutableSequence[MissionReportSnapshot],
    ) -> None:
        for report_rule in rules:
            if report_rule.goal_id in completed_main_objective_ids:
                continue
            if not all(
                objective_status.get(objective_id, False)
                for objective_id in report_rule.required_objective_ids
            ):
                continue
            completed_main_objective_ids.add(report_rule.goal_id)
            mission_reports.append(
                MissionReportSnapshot(
                    report_id=report_rule.report_id,
                    title_key=report_rule.title_key,
                    message_key=report_rule.message_key,
                )
            )
