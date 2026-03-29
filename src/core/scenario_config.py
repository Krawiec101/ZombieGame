from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULT_SCENARIO_PATH = Path(__file__).resolve().parent / "scenarios" / "default_scenario.json"


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    campaign_id: str
    default_mission_id: str
    mission_id: str
    available_mission_ids: tuple[str, ...]
    next_mission_id: str
    default_stage_id: str
    stage_id: str
    available_stage_ids: tuple[str, ...]
    map_width_km: float
    map_objects: tuple[dict[str, Any], ...]
    recon_sites: tuple[dict[str, Any], ...]
    roads: tuple[dict[str, Any], ...]
    initial_units: tuple[dict[str, Any], ...]
    initial_enemy_groups: tuple[dict[str, Any], ...]
    reinforcements: tuple[dict[str, Any], ...]
    mission_objectives: tuple[dict[str, Any], ...]
    mission_reports: tuple[dict[str, Any], ...]
    stage_events: tuple[dict[str, Any], ...]


def load_default_scenario_config(
    *,
    mission_id: str | None = None,
    stage_id: str | None = None,
) -> ScenarioConfig:
    return load_scenario_config(_DEFAULT_SCENARIO_PATH, mission_id=mission_id, stage_id=stage_id)


def load_scenario_config(
    path: str | Path,
    *,
    mission_id: str | None = None,
    stage_id: str | None = None,
) -> ScenarioConfig:
    raw_data = json.loads(Path(path).read_text(encoding="utf-8"))
    scenario_data = _mapping(raw_data.get("scenario"))
    campaign_data = _mapping(raw_data.get("campaign"))
    map_data = _mapping(raw_data.get("map"))
    mission_definitions = _mapping_sequence(raw_data.get("missions"))
    available_mission_ids = tuple(str(mission.get("mission_id", "")) for mission in mission_definitions)
    configured_default_mission_id = str(raw_data.get("default_mission_id", "")) or (
        available_mission_ids[0] if available_mission_ids else "mission_1"
    )
    selected_mission = _select_mission_definition(
        mission_definitions,
        mission_id=mission_id or configured_default_mission_id,
    )
    stage_definitions = _mapping_sequence(selected_mission.get("stages"))
    available_stage_ids = tuple(str(stage.get("stage_id", "")) for stage in stage_definitions)
    configured_default_stage_id = str(selected_mission.get("default_stage_id", "")) or (
        available_stage_ids[0] if available_stage_ids else "default_stage"
    )
    selected_stage = _select_stage_definition(
        stage_definitions,
        stage_id=stage_id or configured_default_stage_id,
    )
    mission_data = _mapping(selected_stage.get("mission"))
    initial_state_data = _mapping(selected_stage.get("initial_state"))
    return ScenarioConfig(
        scenario_id=str(scenario_data.get("scenario_id", "default_scenario")),
        campaign_id=str(campaign_data.get("campaign_id", "default_campaign")),
        default_mission_id=configured_default_mission_id,
        mission_id=str(selected_mission.get("mission_id", configured_default_mission_id)),
        available_mission_ids=available_mission_ids,
        next_mission_id=str(selected_mission.get("next_mission_id", "")),
        default_stage_id=configured_default_stage_id,
        stage_id=str(selected_stage.get("stage_id", configured_default_stage_id)),
        available_stage_ids=available_stage_ids,
        map_width_km=float(map_data.get("width_km", 20.0)),
        map_objects=_mapping_sequence(map_data.get("objects")),
        recon_sites=_mapping_sequence(map_data.get("recon_sites")),
        roads=_mapping_sequence(map_data.get("roads")),
        initial_units=_mapping_sequence(initial_state_data.get("units")),
        initial_enemy_groups=_mapping_sequence(initial_state_data.get("enemy_groups")),
        reinforcements=_mapping_sequence(initial_state_data.get("reinforcements")),
        mission_objectives=_mapping_sequence(mission_data.get("objectives")),
        mission_reports=_mapping_sequence(mission_data.get("reports")),
        stage_events=_mapping_sequence(selected_stage.get("events")),
    )


def _select_mission_definition(
    mission_definitions: tuple[dict[str, Any], ...],
    *,
    mission_id: str,
) -> dict[str, Any]:
    for mission_definition in mission_definitions:
        if str(mission_definition.get("mission_id", "")) == mission_id:
            return mission_definition
    if mission_definitions:
        return mission_definitions[0]
    return {}


def _select_stage_definition(
    stage_definitions: tuple[dict[str, Any], ...],
    *,
    stage_id: str,
) -> dict[str, Any]:
    for stage_definition in stage_definitions:
        if str(stage_definition.get("stage_id", "")) == stage_id:
            return stage_definition
    if stage_definitions:
        return stage_definitions[0]
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _mapping_sequence(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_mapping(item) for item in value)
