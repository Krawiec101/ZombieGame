# ruff: noqa: F401, I001
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
    VEHICLE_TYPE_SPECS,
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
    _equipment_state_from_config,
    _main_objective_report_rules_from_config,
    _organization_state_from_config,
    _reinforcement_templates_from_config,
    _vehicle_assignments_from_config,
    create_default_game_session,
)
from core.model.units import UnitEquipmentState, UnitOrganizationState, VehicleAssignmentState
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

__all__ = [name for name in globals() if not name.startswith('__')]
