from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from contracts.game_state import (
    BaseSnapshot,
    CombatSnapshot,
    CombatNotificationSnapshot,
    GameStateSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    MissionReportSnapshot,
    RoadSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    UnitCommanderSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)
from core.mission_objectives import (
    MissionObjectivesEvaluator,
    create_default_mission_objectives_evaluator,
)

_MAP_WIDTH_KM = 20.0
_SIMULATION_SECONDS_PER_TICK = 8.0
_SUPPLY_INTERVAL_SECONDS = 45.0
_SUPPLY_APPROACH_SECONDS = 6.0
_SUPPLY_UNLOAD_SECONDS = 14.0
_SUPPLY_DEPARTURE_SECONDS = 6.0
_COMBAT_MIN_DURATION_SECONDS = 24.0
_COMBAT_MAX_DURATION_SECONDS = 60.0
_COMBAT_EXCHANGE_INTERVAL_SECONDS = 6.0
_COMBAT_NOTIFICATION_DURATION_SECONDS = 12.0
_SUPPLY_RESOURCE_ORDER = ("fuel", "mre", "ammo")
_BASE_SUPPLY_CAPACITY = 120
_SUPPLY_CONVOY_UNIT_TYPE_ID = "mechanized_squad"
_TRANSPORT_SPAWN_OFFSET_X = 96.0
_TRANSPORT_SPAWN_OFFSET_Y = 120.0
_ZOMBIE_GROUP_MARKER_SIZE_PX = 22
_MAIN_ROAD_ID = "main_supply_road"
_ROAD_SAMPLES_PER_SEGMENT = 14

_MAP_OBJECT_LAYOUT = (
    {
        "id": "hq",
        "anchor_x": 0.22,
        "anchor_y": 0.58,
        "width": 84,
        "height": 56,
        "storage_capacity": _BASE_SUPPLY_CAPACITY,
    },
    {
        "id": "landing_pad",
        "anchor_x": 0.78,
        "anchor_y": 0.34,
        "width": 72,
        "height": 48,
        "pad_size": "small",
        "secured_by_objective_id": "landing_pad_cleared",
    },
)
_RECON_SITE_LAYOUT = (
    {"id": "recon_site_1", "anchor_x": 0.42, "anchor_y": 0.22, "width": 58, "height": 44},
    {"id": "recon_site_2", "anchor_x": 0.56, "anchor_y": 0.20, "width": 58, "height": 44},
    {"id": "recon_site_3", "anchor_x": 0.62, "anchor_y": 0.52, "width": 58, "height": 44},
    {"id": "recon_site_4", "anchor_x": 0.34, "anchor_y": 0.76, "width": 58, "height": 44},
)


@dataclass(frozen=True)
class UnitTypeSpec:
    type_id: str
    speed_kmph: float
    marker_size_px: int
    armament_key: str = ""
    attack: int = 0
    defense: int = 0
    can_transport_supplies: bool = False
    supply_capacity: int = 0


@dataclass(frozen=True)
class LandingPadTypeSpec:
    size_id: str
    capacity: int
    transport_type_id: str


@dataclass(frozen=True)
class SupplyTransportTypeSpec:
    type_id: str
    cargo: dict[str, int]


@dataclass(frozen=True)
class CommanderState:
    name: str = ""
    experience_level: str = "recruit"


@dataclass
class UnitState:
    unit_id: str
    unit_type_id: str
    position: tuple[float, float]
    target: tuple[float, float] | None = None
    path: tuple[tuple[float, float], ...] = ()
    carried_resources: dict[str, int] = field(default_factory=dict)
    name: str = ""
    commander: CommanderState = field(default_factory=CommanderState)
    experience_level: str = "recruit"
    personnel: int = 0
    morale: int = 0
    ammo: int = 0
    rations: int = 0
    fuel: int = 0


@dataclass
class SupplyTransportState:
    transport_id: str
    transport_type_id: str
    target_object_id: str
    phase: str
    position: tuple[float, float]
    seconds_remaining: float
    total_phase_seconds: float
    origin_position: tuple[float, float]
    destination_position: tuple[float, float]


@dataclass
class LandingPadState:
    object_id: str
    pad_size: str
    capacity: int
    secured_by_objective_id: str
    resources: dict[str, int] = field(
        default_factory=lambda: {resource_id: 0 for resource_id in _SUPPLY_RESOURCE_ORDER}
    )
    next_transport_eta_seconds: float | None = None
    active_transport: SupplyTransportState | None = None


@dataclass
class BaseState:
    object_id: str
    capacity: int
    resources: dict[str, int] = field(
        default_factory=lambda: {resource_id: 0 for resource_id in _SUPPLY_RESOURCE_ORDER}
    )


@dataclass
class SupplyRouteState:
    route_id: str
    unit_id: str
    source_object_id: str
    destination_object_id: str
    phase: str


@dataclass
class ZombieGroupState:
    group_id: str
    position: tuple[float, float]
    name: str = ""
    personnel: int = 0


@dataclass
class CombatState:
    combat_id: str
    unit_id: str
    enemy_group_id: str
    seconds_remaining: float
    total_seconds: float
    seconds_until_next_exchange: float


@dataclass
class CombatNotificationState:
    notification_id: str
    unit_name: str
    enemy_group_name: str
    phase: str
    seconds_remaining: float


@dataclass(frozen=True)
class ReinforcementTemplate:
    unit_id: str
    unit_type_id: str
    name: str
    commander: CommanderState
    experience_level: str
    personnel: int
    morale: int
    ammo: int
    rations: int
    fuel: int


@dataclass(frozen=True)
class MainObjectiveReportRule:
    goal_id: str
    required_objective_ids: tuple[str, ...]
    report_id: str
    title_key: str
    message_key: str


REINFORCEMENT_TEMPLATES: tuple[ReinforcementTemplate, ...] = (
    ReinforcementTemplate(
        unit_id="charlie_infantry",
        unit_type_id="infantry_squad",
        name="3. Druzyna Charlie",
        commander=CommanderState(name="ppor. Lena Brzeg", experience_level="regular"),
        experience_level="regular",
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
        commander=CommanderState(name="sier. Oskar Lis", experience_level="veteran"),
        experience_level="regular",
        personnel=8,
        morale=71,
        ammo=70,
        rations=10,
        fuel=0,
    ),
)

MAIN_OBJECTIVE_REPORT_RULES: tuple[MainObjectiveReportRule, ...] = (
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


UNIT_TYPE_SPECS: dict[str, UnitTypeSpec] = {
    "infantry_squad": UnitTypeSpec(
        type_id="infantry_squad",
        speed_kmph=4.2,
        marker_size_px=18,
        armament_key="game.unit.armament.rifles_lmg",
        attack=4,
        defense=5,
    ),
    _SUPPLY_CONVOY_UNIT_TYPE_ID: UnitTypeSpec(
        type_id=_SUPPLY_CONVOY_UNIT_TYPE_ID,
        speed_kmph=18.0,
        marker_size_px=20,
        armament_key="game.unit.armament.apc_autocannon",
        attack=7,
        defense=8,
        can_transport_supplies=True,
        supply_capacity=24,
    ),
}

LANDING_PAD_TYPE_SPECS: dict[str, LandingPadTypeSpec] = {
    "small": LandingPadTypeSpec(
        size_id="small",
        capacity=90,
        transport_type_id="light_supply_helicopter",
    ),
    "large": LandingPadTypeSpec(
        size_id="large",
        capacity=180,
        transport_type_id="heavy_supply_helicopter",
    ),
}

SUPPLY_TRANSPORT_TYPE_SPECS: dict[str, SupplyTransportTypeSpec] = {
    "light_supply_helicopter": SupplyTransportTypeSpec(
        type_id="light_supply_helicopter",
        cargo={"fuel": 12, "mre": 8, "ammo": 10},
    ),
    "heavy_supply_helicopter": SupplyTransportTypeSpec(
        type_id="heavy_supply_helicopter",
        cargo={"fuel": 24, "mre": 18, "ammo": 18},
    ),
}


class GameSession:
    def __init__(
        self,
        *,
        mission_objectives_evaluator: MissionObjectivesEvaluator,
        time_provider: Callable[[], float] | None = None,
        search_roll_provider: Callable[[], float] | None = None,
    ) -> None:
        self._mission_objectives_evaluator = mission_objectives_evaluator
        self._objective_definitions = tuple(self._mission_objectives_evaluator.objectives())
        self._objective_status = {
            definition["objective_id"]: False for definition in self._objective_definitions
        }
        self._time_provider = time_provider or time.monotonic
        self._search_roll_provider = search_roll_provider or random.random

        self._map_size: tuple[int, int] = (0, 0)
        self._map_objects: list[dict[str, Any]] = []
        self._roads: list[dict[str, Any]] = []
        self._bases: dict[str, BaseState] = {}
        self._landing_pads: dict[str, LandingPadState] = {}
        self._supply_routes: dict[str, SupplyRouteState] = {}
        self._units: list[UnitState] = []
        self._enemy_groups: list[ZombieGroupState] = []
        self._combats: dict[str, CombatState] = {}
        self._combat_notifications: list[CombatNotificationState] = []
        self._mission_reports: list[MissionReportSnapshot] = []
        self._selected_unit_id: str | None = None
        self._units_initialized = False
        self._last_supply_update_at: float | None = None
        self._last_combat_update_at: float | None = None
        self._investigated_recon_site_ids: set[str] = set()
        self._found_reinforcement_unit_ids: set[str] = set()
        self._completed_main_objective_ids: set[str] = set()

    def reset(self) -> None:
        self._units = []
        self._enemy_groups = []
        self._roads = []
        self._bases = {}
        self._landing_pads = {}
        self._supply_routes = {}
        self._selected_unit_id = None
        self._combats = {}
        self._combat_notifications = []
        self._mission_reports = []
        self._units_initialized = False
        self._last_supply_update_at = None
        self._last_combat_update_at = None
        self._investigated_recon_site_ids = set()
        self._found_reinforcement_unit_ids = set()
        self._completed_main_objective_ids = set()
        self._objective_status = {
            definition["objective_id"]: False for definition in self._objective_definitions
        }

    def update_map_dimensions(self, *, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return

        new_size = (int(width), int(height))
        map_size_changed = new_size != self._map_size
        self._map_size = new_size
        if map_size_changed or not self._map_objects:
            self._map_objects = self._build_map_objects(*self._map_size)
            self._roads = self._build_roads()
        elif not self._roads:
            self._roads = self._build_roads()

        self._sync_bases_to_map_objects()
        self._sync_landing_pads_to_map_objects()

        if not self._units_initialized:
            self._initialize_units()
        elif map_size_changed:
            for unit in self._units:
                unit.position = self._clamp_point_to_map(unit.position, unit_type_id=unit.unit_type_id)
                if unit.target is not None:
                    road_mode = (
                        "only"
                        if self._unit_has_supply_route(unit.unit_id)
                        else self._road_mode_for_unit(unit.unit_type_id)
                    )
                    self._set_unit_target(unit, unit.target, road_mode=road_mode)
            self._clamp_enemy_groups_to_map()
            self._refresh_supply_route_targets()

    def tick(self) -> None:
        elapsed_supply_seconds = self._consume_supply_elapsed_seconds()
        elapsed_combat_seconds = self._consume_combat_elapsed_seconds()
        self._update_combat_notifications(elapsed_seconds=elapsed_combat_seconds)
        self._update_combats(elapsed_seconds=elapsed_combat_seconds)
        self._update_units_position()
        self._start_combats_for_colliding_units()
        self._investigate_recon_sites()
        self._objective_status = self._mission_objectives_evaluator.evaluate(
            units=self.units_snapshot(),
            map_objects=self.map_objects_snapshot(),
            current_status=self._objective_status,
            supply_routes=self.supply_routes_state_snapshot(),
            enemy_groups=self.enemy_groups_state_snapshot(),
            discovered_reinforcements_count=self._discovered_reinforcements_count(),
        )
        self._update_main_objective_reports()
        self._update_supply_network(elapsed_seconds=elapsed_supply_seconds)
        self._update_supply_routes()

    def sync_state(self, *, width: int, height: int) -> GameStateSnapshot:
        self.update_map_dimensions(width=width, height=height)
        self.tick()
        return self.snapshot()

    def handle_left_click(self, position: tuple[int, int]) -> None:
        if not self._point_in_map(position):
            return

        clicked_unit = self._find_unit_at(position)
        if clicked_unit is not None:
            self._selected_unit_id = clicked_unit.unit_id
            return

        selected_unit = self._get_selected_unit()
        if selected_unit is None:
            return

        if self._unit_has_supply_route(selected_unit.unit_id):
            return

        self._set_unit_target(
            selected_unit,
            position,
            road_mode=self._road_mode_for_unit(selected_unit.unit_type_id),
        )

    def handle_right_click(self, _position: tuple[int, int]) -> None:
        if self._get_selected_unit() is None:
            return
        self._selected_unit_id = None

    def handle_supply_route(self, *, source_object_id: str, destination_object_id: str) -> None:
        selected_unit = self._get_selected_unit()
        if selected_unit is None:
            return

        if not self._unit_can_transport_supplies(selected_unit.unit_type_id):
            return

        if not self._is_valid_supply_route_pair(
            source_object_id=source_object_id,
            destination_object_id=destination_object_id,
        ):
            return

        self._clear_supply_route_for_unit(selected_unit.unit_id)
        selected_unit.target = None  # pragma: no mutate
        selected_unit.path = ()  # pragma: no mutate
        selected_unit.carried_resources = self._empty_resource_store()
        route = SupplyRouteState(
            route_id=f"{selected_unit.unit_id}:{source_object_id}->{destination_object_id}",
            unit_id=selected_unit.unit_id,
            source_object_id=source_object_id,
            destination_object_id=destination_object_id,
            phase="to_pickup",
        )
        self._supply_routes[route.route_id] = route
        self._refresh_supply_route(route)

    def map_objects_snapshot(self) -> list[dict[str, Any]]:
        return [{"id": obj["id"], "bounds": obj["bounds"]} for obj in self._map_objects]

    def enemy_groups_state_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "group_id": enemy_group.group_id,
                "position": enemy_group.position,
                "name": enemy_group.name,
                "personnel": enemy_group.personnel,
            }
            for enemy_group in self._enemy_groups
        ]

    def roads_snapshot(self) -> tuple[RoadSnapshot, ...]:
        return tuple(
            RoadSnapshot(
                road_id=str(road["id"]),
                points=tuple(tuple(point) for point in road["points"]),
            )
            for road in self._roads
        )

    def units_snapshot(self) -> list[dict[str, Any]]:  # pragma: no mutate
        return [
            {
                "unit_id": unit.unit_id,
                "unit_type_id": unit.unit_type_id,
                "position": unit.position,
                "target": unit.target,
                "marker_size_px": UNIT_TYPE_SPECS[unit.unit_type_id].marker_size_px,
                "name": unit.name,
                "commander": {
                    "name": unit.commander.name,
                    "experience_level": unit.commander.experience_level,
                },
                "experience_level": unit.experience_level,
                "personnel": unit.personnel,
                "armament_key": UNIT_TYPE_SPECS[unit.unit_type_id].armament_key,
                "attack": UNIT_TYPE_SPECS[unit.unit_type_id].attack,
                "defense": UNIT_TYPE_SPECS[unit.unit_type_id].defense,
                "morale": unit.morale,
                "ammo": unit.ammo,
                "rations": unit.rations,
                "fuel": unit.fuel,
                "can_transport_supplies": UNIT_TYPE_SPECS[unit.unit_type_id].can_transport_supplies,
                "supply_capacity": UNIT_TYPE_SPECS[unit.unit_type_id].supply_capacity,
                "carried_supply_total": self._resource_total(unit.carried_resources),
                "active_supply_route_id": self._supply_route_id_for_unit(unit.unit_id),  # pragma: no mutate
                "is_in_combat": self._combat_for_unit(unit.unit_id) is not None,
                "combat_seconds_remaining": self._display_seconds(
                    self._combat_seconds_remaining_for_unit(unit.unit_id)
                ),
            }
            for unit in self._units
        ]

    def bases_snapshot(self) -> tuple[BaseSnapshot, ...]:
        snapshots: list[BaseSnapshot] = []
        for object_id in sorted(self._bases):
            base = self._bases[object_id]
            snapshots.append(
                BaseSnapshot(  # pragma: no mutate
                    object_id=base.object_id,  # pragma: no mutate
                    capacity=base.capacity,  # pragma: no mutate
                    total_stored=self._resource_total(base.resources),  # pragma: no mutate
                    resources=tuple(  # pragma: no mutate
                        LandingPadResourceSnapshot(
                            resource_id=resource_id,  # pragma: no mutate
                            amount=int(base.resources.get(resource_id, 0)),  # pragma: no mutate
                        )
                        for resource_id in _SUPPLY_RESOURCE_ORDER
                    ),
                )
            )
        return tuple(snapshots)

    def enemy_groups_snapshot(self) -> tuple[ZombieGroupSnapshot, ...]:
        return tuple(
            ZombieGroupSnapshot(
                group_id=enemy_group.group_id,
                position=enemy_group.position,
                marker_size_px=_ZOMBIE_GROUP_MARKER_SIZE_PX,
                name=enemy_group.name,
                personnel=enemy_group.personnel,
                is_in_combat=self._combat_for_enemy_group(enemy_group.group_id) is not None,
            )
            for enemy_group in self._enemy_groups
        )

    def combats_snapshot(self) -> tuple[CombatSnapshot, ...]:
        snapshots: list[CombatSnapshot] = []
        for combat_id in sorted(self._combats):
            combat = self._combats[combat_id]
            unit = self._find_unit_by_id(combat.unit_id)
            enemy_group = self._find_enemy_group_by_id(combat.enemy_group_id)
            if unit is None or enemy_group is None:
                continue
            snapshots.append(
                CombatSnapshot(
                    combat_id=combat.combat_id,
                    unit_id=unit.unit_id,
                    unit_name=unit.name or unit.unit_id,
                    enemy_group_id=enemy_group.group_id,
                    enemy_group_name=enemy_group.name or enemy_group.group_id,
                    seconds_remaining=self._display_seconds(combat.seconds_remaining) or 0,
                )
            )
        return tuple(snapshots)

    def combat_notifications_snapshot(self) -> tuple[CombatNotificationSnapshot, ...]:
        return tuple(
            CombatNotificationSnapshot(
                notification_id=notification.notification_id,
                unit_name=notification.unit_name,
                enemy_group_name=notification.enemy_group_name,
                phase=notification.phase,
                seconds_remaining=self._display_seconds(notification.seconds_remaining) or 0,
            )
            for notification in reversed(self._combat_notifications)
        )

    def landing_pads_snapshot(self) -> tuple[LandingPadSnapshot, ...]:
        snapshots: list[LandingPadSnapshot] = []
        for object_id in sorted(self._landing_pads):
            landing_pad = self._landing_pads[object_id]
            active_transport = landing_pad.active_transport
            snapshots.append(
                LandingPadSnapshot(  # pragma: no mutate
                    object_id=landing_pad.object_id,  # pragma: no mutate
                    pad_size=landing_pad.pad_size,  # pragma: no mutate
                    is_secured=self._is_landing_pad_secured(landing_pad),  # pragma: no mutate
                    capacity=landing_pad.capacity,  # pragma: no mutate
                    total_stored=self._landing_pad_total_stored(landing_pad),  # pragma: no mutate
                    next_transport_seconds=self._display_seconds(  # pragma: no mutate
                        landing_pad.next_transport_eta_seconds
                    ),
                    active_transport_type_id=(  # pragma: no mutate
                        active_transport.transport_type_id if active_transport is not None else None
                    ),
                    active_transport_phase=(  # pragma: no mutate
                        active_transport.phase if active_transport is not None else None
                    ),
                    active_transport_seconds_remaining=(  # pragma: no mutate
                        self._display_seconds(active_transport.seconds_remaining)
                        if active_transport is not None
                        else None
                    ),
                    resources=tuple(  # pragma: no mutate
                        LandingPadResourceSnapshot(
                            resource_id=resource_id,  # pragma: no mutate
                            amount=int(landing_pad.resources.get(resource_id, 0)),  # pragma: no mutate
                        )
                        for resource_id in _SUPPLY_RESOURCE_ORDER
                    ),
                )
            )
        return tuple(snapshots)

    def supply_transports_snapshot(self) -> tuple[SupplyTransportSnapshot, ...]:  # pragma: no mutate
        snapshots: list[SupplyTransportSnapshot] = []
        for object_id in sorted(self._landing_pads):
            active_transport = self._landing_pads[object_id].active_transport
            if active_transport is None:
                continue
            snapshots.append(
                SupplyTransportSnapshot(  # pragma: no mutate
                    transport_id=active_transport.transport_id,  # pragma: no mutate
                    transport_type_id=active_transport.transport_type_id,  # pragma: no mutate
                    phase=active_transport.phase,  # pragma: no mutate
                    position=active_transport.position,  # pragma: no mutate
                    target_object_id=active_transport.target_object_id,  # pragma: no mutate
                )
            )
        return tuple(snapshots)

    def supply_routes_snapshot(self) -> tuple[SupplyRouteSnapshot, ...]:
        snapshots: list[SupplyRouteSnapshot] = []
        for route_id in sorted(self._supply_routes):
            route = self._supply_routes[route_id]
            unit = self._find_unit_by_id(route.unit_id)
            if unit is None:
                continue
            snapshots.append(
                SupplyRouteSnapshot(  # pragma: no mutate
                    route_id=route.route_id,  # pragma: no mutate
                    unit_id=route.unit_id,  # pragma: no mutate
                    source_object_id=route.source_object_id,  # pragma: no mutate
                    destination_object_id=route.destination_object_id,  # pragma: no mutate
                    phase=route.phase,  # pragma: no mutate
                    carried_total=self._resource_total(unit.carried_resources),  # pragma: no mutate
                    capacity=UNIT_TYPE_SPECS[unit.unit_type_id].supply_capacity,  # pragma: no mutate
                )
            )
        return tuple(snapshots)

    def supply_routes_state_snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "route_id": route.route_id,
                "unit_id": route.unit_id,
                "source_object_id": route.source_object_id,
                "destination_object_id": route.destination_object_id,
                "phase": route.phase,
            }
            for route in self._supply_routes.values()
        ]

    def objective_status_snapshot(self) -> dict[str, bool]:
        return dict(self._objective_status)

    def objective_definitions_snapshot(self) -> tuple[dict[str, str], ...]:
        return self._objective_definitions

    def objective_progress_snapshot(self) -> tuple[MissionObjectiveProgressSnapshot, ...]:
        return tuple(
            MissionObjectiveProgressSnapshot(
                objective_id=objective_id,
                completed=completed,
            )
            for objective_id, completed in self._objective_status.items()
        )

    def mission_reports_snapshot(self) -> tuple[MissionReportSnapshot, ...]:
        return tuple(self._mission_reports)

    def selected_unit_id(self) -> str | None:
        return self._selected_unit_id

    def snapshot(self) -> GameStateSnapshot:  # pragma: no mutate
        return GameStateSnapshot(
            map_objects=tuple(  # pragma: no mutate
                MapObjectSnapshot(object_id=obj["id"], bounds=obj["bounds"])
                for obj in self.map_objects_snapshot()
            ),
            roads=self.roads_snapshot(),  # pragma: no mutate
            units=tuple(  # pragma: no mutate
                UnitSnapshot(
                    unit_id=unit["unit_id"],  # pragma: no mutate
                    unit_type_id=unit["unit_type_id"],  # pragma: no mutate
                    position=unit["position"],  # pragma: no mutate
                    target=unit["target"],  # pragma: no mutate
                    marker_size_px=unit["marker_size_px"],  # pragma: no mutate
                    name=unit["name"],  # pragma: no mutate
                    commander=UnitCommanderSnapshot(**unit["commander"]),  # pragma: no mutate
                    experience_level=unit["experience_level"],  # pragma: no mutate
                    personnel=unit["personnel"],  # pragma: no mutate
                    armament_key=unit["armament_key"],  # pragma: no mutate
                    attack=unit["attack"],  # pragma: no mutate
                    defense=unit["defense"],  # pragma: no mutate
                    morale=unit["morale"],  # pragma: no mutate
                    ammo=unit["ammo"],  # pragma: no mutate
                    rations=unit["rations"],  # pragma: no mutate
                    fuel=unit["fuel"],  # pragma: no mutate
                    can_transport_supplies=unit["can_transport_supplies"],  # pragma: no mutate
                    supply_capacity=unit["supply_capacity"],  # pragma: no mutate
                    carried_supply_total=unit["carried_supply_total"],  # pragma: no mutate
                    active_supply_route_id=unit["active_supply_route_id"],  # pragma: no mutate
                    is_in_combat=unit["is_in_combat"],  # pragma: no mutate
                    combat_seconds_remaining=unit["combat_seconds_remaining"],  # pragma: no mutate
                )
                for unit in self.units_snapshot()
            ),
            enemy_groups=self.enemy_groups_snapshot(),  # pragma: no mutate
            selected_unit_id=self.selected_unit_id(),  # pragma: no mutate
            objective_definitions=tuple(  # pragma: no mutate
                MissionObjectiveDefinitionSnapshot(
                    objective_id=definition["objective_id"],  # pragma: no mutate
                    description_key=definition["description_key"],  # pragma: no mutate
                )
                for definition in self.objective_definitions_snapshot()
            ),
            objective_progress=self.objective_progress_snapshot(),  # pragma: no mutate
            mission_reports=self.mission_reports_snapshot(),  # pragma: no mutate
            landing_pads=self.landing_pads_snapshot(),  # pragma: no mutate
            bases=self.bases_snapshot(),  # pragma: no mutate
            supply_transports=self.supply_transports_snapshot(),  # pragma: no mutate
            supply_routes=self.supply_routes_snapshot(),  # pragma: no mutate
            combats=self.combats_snapshot(),  # pragma: no mutate
            combat_notifications=self.combat_notifications_snapshot(),  # pragma: no mutate
        )

    def _build_map_objects(self, width: int, height: int) -> list[dict[str, Any]]:
        objects = [self._map_object_from_layout(layout, width=width, height=height) for layout in _MAP_OBJECT_LAYOUT]
        for layout in _RECON_SITE_LAYOUT:
            if str(layout["id"]) in self._investigated_recon_site_ids:
                continue
            objects.append(self._map_object_from_layout(layout, width=width, height=height))
        return objects

    def _map_object_from_layout(
        self,
        layout: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        center_x = int(width * layout["anchor_x"])
        center_y = int(height * layout["anchor_y"])
        half_width = layout["width"] // 2
        half_height = layout["height"] // 2
        left = center_x - half_width
        top = center_y - half_height
        right = left + layout["width"]
        bottom = top + layout["height"]
        map_object = dict(layout)
        map_object["bounds"] = (left, top, right, bottom)
        return map_object

    def _build_roads(self) -> list[dict[str, Any]]:
        hq_center = self._map_object_center("hq")  # pragma: no mutate
        landing_pad_center = self._map_object_center("landing_pad")  # pragma: no mutate
        if hq_center == (0.0, 0.0) or landing_pad_center == (0.0, 0.0):  # pragma: no mutate
            return []  # pragma: no mutate

        width, height = self._map_size  # pragma: no mutate
        control_points = (  # pragma: no mutate
            hq_center,  # pragma: no mutate
            (width * 0.30, height * 0.66),  # pragma: no mutate
            (width * 0.42, height * 0.74),  # pragma: no mutate
            (width * 0.58, height * 0.63),  # pragma: no mutate
            (width * 0.69, height * 0.50),  # pragma: no mutate
            landing_pad_center,  # pragma: no mutate
        )
        return [{"id": _MAIN_ROAD_ID, "points": self._sample_road_curve(control_points)}]  # pragma: no mutate

    def _sample_road_curve(
        self,
        control_points: tuple[tuple[float, float], ...],
    ) -> tuple[tuple[float, float], ...]:
        if len(control_points) < 2:  # pragma: no mutate
            return control_points  # pragma: no mutate

        sampled_points: list[tuple[float, float]] = []  # pragma: no mutate
        for index in range(len(control_points) - 1):  # pragma: no mutate
            p0 = control_points[index - 1] if index > 0 else control_points[index]  # pragma: no mutate
            p1 = control_points[index]  # pragma: no mutate
            p2 = control_points[index + 1]  # pragma: no mutate
            p3 = (  # pragma: no mutate
                control_points[index + 2]  # pragma: no mutate
                if index + 2 < len(control_points)  # pragma: no mutate
                else control_points[index + 1]  # pragma: no mutate
            )
            for sample_index in range(_ROAD_SAMPLES_PER_SEGMENT):  # pragma: no mutate
                t = sample_index / float(_ROAD_SAMPLES_PER_SEGMENT)  # pragma: no mutate
                sampled_points.append(self._catmull_rom_point(p0, p1, p2, p3, t))  # pragma: no mutate

        sampled_points.append(control_points[-1])  # pragma: no mutate
        return tuple(self._deduplicate_points(sampled_points))  # pragma: no mutate

    def _catmull_rom_point(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
        t: float,
    ) -> tuple[float, float]:
        t2 = t * t  # pragma: no mutate
        t3 = t2 * t  # pragma: no mutate
        x = 0.5 * (  # pragma: no mutate
            (2.0 * p1[0])  # pragma: no mutate
            + (-p0[0] + p2[0]) * t  # pragma: no mutate
            + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2  # pragma: no mutate
            + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3  # pragma: no mutate
        )
        y = 0.5 * (  # pragma: no mutate
            (2.0 * p1[1])  # pragma: no mutate
            + (-p0[1] + p2[1]) * t  # pragma: no mutate
            + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2  # pragma: no mutate
            + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3  # pragma: no mutate
        )
        return self._clamp_road_point((x, y))  # pragma: no mutate

    def _clamp_road_point(self, point: tuple[float, float]) -> tuple[float, float]:
        width, height = self._map_size  # pragma: no mutate
        if width <= 0 or height <= 0:  # pragma: no mutate
            return point  # pragma: no mutate
        return (  # pragma: no mutate
            min(max(float(point[0]), 0.0), float(width)),  # pragma: no mutate
            min(max(float(point[1]), 0.0), float(height)),  # pragma: no mutate
        )

    def _deduplicate_points(
        self,
        points: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        deduplicated: list[tuple[float, float]] = []  # pragma: no mutate
        for point in points:  # pragma: no mutate
            if deduplicated and self._positions_match(deduplicated[-1], point, tolerance=0.1):  # pragma: no mutate
                continue  # pragma: no mutate
            deduplicated.append(point)  # pragma: no mutate
        return deduplicated  # pragma: no mutate

    def _sync_bases_to_map_objects(self) -> None:
        synced_bases: dict[str, BaseState] = {}
        for map_object in self._map_objects:
            if "storage_capacity" not in map_object:
                continue

            object_id = str(map_object["id"])
            capacity = int(map_object.get("storage_capacity", _BASE_SUPPLY_CAPACITY))  # pragma: no mutate
            previous = self._bases.get(object_id)
            resources = self._empty_resource_store()
            if previous is not None:
                resources = self._trim_resources_to_capacity(previous.resources, capacity)

            synced_bases[object_id] = BaseState(
                object_id=object_id,
                capacity=capacity,
                resources=resources,
            )

        self._bases = synced_bases

    def _sync_landing_pads_to_map_objects(self) -> None:
        synced_landing_pads: dict[str, LandingPadState] = {}
        for map_object in self._map_objects:
            if "pad_size" not in map_object:
                continue

            object_id = str(map_object["id"])
            pad_size = str(map_object["pad_size"])
            pad_spec = LANDING_PAD_TYPE_SPECS.get(pad_size, LANDING_PAD_TYPE_SPECS["small"])
            previous = self._landing_pads.get(object_id)
            resources = self._empty_resource_store()
            next_transport_eta_seconds = None
            active_transport = None

            if previous is not None:
                resources = {
                    resource_id: int(previous.resources.get(resource_id, 0))
                    for resource_id in _SUPPLY_RESOURCE_ORDER
                }
                resources = self._trim_resources_to_capacity(resources, pad_spec.capacity)
                next_transport_eta_seconds = previous.next_transport_eta_seconds
                active_transport = previous.active_transport

            landing_pad = LandingPadState(
                object_id=object_id,
                pad_size=pad_spec.size_id,
                capacity=pad_spec.capacity,
                secured_by_objective_id=str(map_object.get("secured_by_objective_id", "")),
                resources=resources,
                next_transport_eta_seconds=next_transport_eta_seconds,
                active_transport=active_transport,
            )
            synced_landing_pads[object_id] = landing_pad
            self._refresh_transport_geometry(landing_pad)

        self._landing_pads = synced_landing_pads

    def _initialize_units(self) -> None:
        hq = next((obj for obj in self._map_objects if obj["id"] == "hq"), None)
        landing_pad = next((obj for obj in self._map_objects if obj["id"] == "landing_pad"), None)
        if hq is None:
            return

        hq_left, hq_top, hq_right, hq_bottom = hq["bounds"]
        hq_center = ((hq_left + hq_right) / 2.0, (hq_top + hq_bottom) / 2.0)
        self._units = [
            UnitState(
                unit_id="alpha_infantry",
                unit_type_id="infantry_squad",
                position=(hq_center[0] - 22.0, hq_center[1] + 8.0),
                name="1. Druzyna Alfa",
                commander=CommanderState(name="por. Anna Sowa", experience_level="regular"),
                experience_level="recruit",
                personnel=10,
                morale=72,
                ammo=90,
                rations=18,
                fuel=0,
            ),
            UnitState(
                unit_id="bravo_mechanized",
                unit_type_id="mechanized_squad",
                position=self._road_anchor_for_point((hq_center[0] + 26.0, hq_center[1] + 8.0)),
                name="2. Sekcja Bravo",
                commander=CommanderState(name="kpt. Marek Wolny", experience_level="veteran"),
                experience_level="regular",
                personnel=8,
                morale=81,
                ammo=120,
                rations=24,
                fuel=65,
            ),
        ]
        if landing_pad is not None:
            pad_left, pad_top, pad_right, pad_bottom = landing_pad["bounds"]
            pad_center = ((pad_left + pad_right) / 2.0, (pad_top + pad_bottom) / 2.0)
            self._enemy_groups = [
                ZombieGroupState(
                    group_id="zulu_zombies",
                    position=pad_center,
                    name="Mala grupa zombie",
                    personnel=7,
                ),
            ]
        for unit in self._units:
            unit.position = self._clamp_point_to_map(unit.position, unit_type_id=unit.unit_type_id)
        self._clamp_enemy_groups_to_map()
        self._units_initialized = True

    def _clamp_enemy_groups_to_map(self) -> None:
        for enemy_group in self._enemy_groups:
            enemy_group.position = self._clamp_enemy_point_to_map(enemy_group.position)

    def _investigate_recon_sites(self) -> None:
        newly_investigated = False
        for layout in _RECON_SITE_LAYOUT:
            site_id = str(layout["id"])
            if site_id in self._investigated_recon_site_ids:
                continue

            site_bounds = self._map_object_bounds(site_id)
            if site_bounds is None:
                continue

            if not any(self._point_in_bounds(unit.position, site_bounds) for unit in self._units):
                continue

            self._investigated_recon_site_ids.add(site_id)
            newly_investigated = True
            if self._should_reveal_reinforcement():
                self._spawn_next_reinforcement(site_id)

        if newly_investigated:
            self._refresh_dynamic_map_objects()

    def _should_reveal_reinforcement(self) -> bool:
        remaining_reinforcements = len(REINFORCEMENT_TEMPLATES) - self._discovered_reinforcements_count()
        remaining_sites = len(_RECON_SITE_LAYOUT) - len(self._investigated_recon_site_ids) + 1
        if remaining_reinforcements <= 0 or remaining_sites <= 0:
            return False
        if remaining_reinforcements >= remaining_sites:
            return True
        reveal_probability = remaining_reinforcements / float(remaining_sites)
        return float(self._search_roll_provider()) <= reveal_probability

    def _spawn_next_reinforcement(self, site_id: str) -> None:
        next_template = next(
            (
                template
                for template in REINFORCEMENT_TEMPLATES
                if template.unit_id not in self._found_reinforcement_unit_ids
            ),
            None,
        )
        if next_template is None:
            return

        spawn_position = self._clamp_point_to_map(
            self._map_object_center(site_id),
            unit_type_id=next_template.unit_type_id,
        )
        self._units.append(
            UnitState(
                unit_id=next_template.unit_id,
                unit_type_id=next_template.unit_type_id,
                position=spawn_position,
                name=next_template.name,
                commander=next_template.commander,
                experience_level=next_template.experience_level,
                personnel=next_template.personnel,
                morale=next_template.morale,
                ammo=next_template.ammo,
                rations=next_template.rations,
                fuel=next_template.fuel,
            )
        )
        self._found_reinforcement_unit_ids.add(next_template.unit_id)

    def _refresh_dynamic_map_objects(self) -> None:
        width, height = self._map_size
        if width <= 0 or height <= 0:
            return
        self._map_objects = self._build_map_objects(width, height)
        self._sync_bases_to_map_objects()
        self._sync_landing_pads_to_map_objects()

    def _map_object_bounds(self, object_id: str) -> tuple[int, int, int, int] | None:
        map_object = next((obj for obj in self._map_objects if obj["id"] == object_id), None)
        if map_object is None:
            return None
        bounds = map_object.get("bounds")
        if not isinstance(bounds, tuple) or len(bounds) != 4:
            return None
        return bounds

    def _point_in_bounds(
        self,
        position: tuple[float, float] | tuple[int, int],
        bounds: tuple[int, int, int, int],
    ) -> bool:
        x, y = position
        left, top, right, bottom = bounds
        return left <= x <= right and top <= y <= bottom

    def _discovered_reinforcements_count(self) -> int:
        return len(self._found_reinforcement_unit_ids)

    def _update_main_objective_reports(self) -> None:
        for report_rule in MAIN_OBJECTIVE_REPORT_RULES:
            if report_rule.goal_id in self._completed_main_objective_ids:
                continue
            if not all(
                self._objective_status.get(objective_id, False)
                for objective_id in report_rule.required_objective_ids
            ):
                continue
            self._completed_main_objective_ids.add(report_rule.goal_id)
            self._mission_reports.append(
                MissionReportSnapshot(
                    report_id=report_rule.report_id,
                    title_key=report_rule.title_key,
                    message_key=report_rule.message_key,
                )
            )

    def _update_combats(self, *, elapsed_seconds: float) -> None:
        for combat_id in list(sorted(self._combats)):
            combat = self._combats.get(combat_id)
            if combat is None:
                continue

            unit = self._find_unit_by_id(combat.unit_id)
            enemy_group = self._find_enemy_group_by_id(combat.enemy_group_id)
            if unit is None or enemy_group is None:
                self._combats.pop(combat_id, None)
                continue

            remaining_elapsed = max(0.0, elapsed_seconds)
            while remaining_elapsed > 0.0:
                step_seconds = min(
                    remaining_elapsed,
                    combat.seconds_remaining,
                    combat.seconds_until_next_exchange,
                )
                combat.seconds_remaining = max(0.0, combat.seconds_remaining - step_seconds)
                combat.seconds_until_next_exchange = max(0.0, combat.seconds_until_next_exchange - step_seconds)
                remaining_elapsed -= step_seconds

                if combat.seconds_until_next_exchange <= 0.0:
                    self._apply_combat_attrition(unit, enemy_group)
                    if enemy_group.personnel <= 0:
                        self._resolve_combat(combat)
                        break
                    if combat.seconds_remaining > 0.0:
                        combat.seconds_until_next_exchange = min(
                            _COMBAT_EXCHANGE_INTERVAL_SECONDS,
                            combat.seconds_remaining,
                        )

                if combat.seconds_remaining <= 0.0:
                    self._resolve_combat(combat)
                    break

                if step_seconds <= 0.0:
                    break

    def _update_combat_notifications(self, *, elapsed_seconds: float) -> None:
        if elapsed_seconds <= 0.0:
            return
        updated_notifications: list[CombatNotificationState] = []
        for notification in self._combat_notifications:
            notification.seconds_remaining = max(0.0, notification.seconds_remaining - elapsed_seconds)
            if notification.seconds_remaining > 0.0:
                updated_notifications.append(notification)
        self._combat_notifications = updated_notifications

    def _start_combats_for_colliding_units(self) -> None:
        for enemy_group in self._enemy_groups:
            if self._combat_for_enemy_group(enemy_group.group_id) is not None:
                continue

            for unit in self._units:
                if self._combat_for_unit(unit.unit_id) is not None:
                    continue
                if not self._bounds_overlap(self._unit_bounds(unit), self._enemy_group_bounds(enemy_group)):
                    continue
                self._start_combat(unit, enemy_group)
                break

    def _update_units_position(self) -> None:
        for unit in self._units:
            if self._combat_for_unit(unit.unit_id) is not None:
                continue
            if unit.target is None:
                continue

            speed_px_per_tick = self._movement_pixels_per_tick(unit.unit_type_id)
            if speed_px_per_tick <= 0:
                continue

            current_x, current_y = unit.position
            next_waypoint = unit.path[0] if unit.path else unit.target
            target_x, target_y = next_waypoint
            delta_x = target_x - current_x
            delta_y = target_y - current_y
            distance = math.hypot(delta_x, delta_y)

            if distance <= speed_px_per_tick:
                unit.position = next_waypoint
                if unit.path:
                    unit.path = unit.path[1:]
                if not unit.path:
                    unit.target = None
                continue

            step = speed_px_per_tick / distance
            moved_x = current_x + delta_x * step
            moved_y = current_y + delta_y * step
            unit.position = self._clamp_point_to_map((moved_x, moved_y), unit_type_id=unit.unit_type_id)

    def _start_combat(self, unit: UnitState, enemy_group: ZombieGroupState) -> None:
        duration_seconds = self._combat_duration_seconds(unit, enemy_group)
        combat = CombatState(
            combat_id=f"{unit.unit_id}:{enemy_group.group_id}",
            unit_id=unit.unit_id,
            enemy_group_id=enemy_group.group_id,
            seconds_remaining=duration_seconds,
            total_seconds=duration_seconds,
            seconds_until_next_exchange=min(_COMBAT_EXCHANGE_INTERVAL_SECONDS, duration_seconds),
        )
        self._combats[combat.combat_id] = combat
        self._push_combat_notification(
            notification_id=f"{combat.combat_id}:started",
            unit_name=unit.name or unit.unit_id,
            enemy_group_name=enemy_group.name or enemy_group.group_id,
            phase="started",
        )
        unit.position = self._clamp_point_to_map(unit.position, unit_type_id=unit.unit_type_id)

    def _combat_duration_seconds(self, unit: UnitState, enemy_group: ZombieGroupState) -> float:
        enemy_strength = max(1, int(enemy_group.personnel))
        suppression = max(1, int(UNIT_TYPE_SPECS[unit.unit_type_id].attack) // 3)
        expected_exchanges = math.ceil(enemy_strength / suppression)
        return min(
            _COMBAT_MAX_DURATION_SECONDS,
            max(_COMBAT_MIN_DURATION_SECONDS, float(expected_exchanges * _COMBAT_EXCHANGE_INTERVAL_SECONDS)),
        )

    def _apply_combat_attrition(self, unit: UnitState, enemy_group: ZombieGroupState) -> None:
        suppression = max(1, int(UNIT_TYPE_SPECS[unit.unit_type_id].attack) // 3)
        enemy_group.personnel = max(0, enemy_group.personnel - suppression)
        unit.ammo = max(0, unit.ammo - max(4, UNIT_TYPE_SPECS[unit.unit_type_id].attack * 2))
        unit.morale = max(0, unit.morale - max(1, math.ceil(enemy_group.personnel / 5)))

    def _resolve_combat(self, combat: CombatState) -> None:
        self._combats.pop(combat.combat_id, None)
        unit = self._find_unit_by_id(combat.unit_id)
        enemy_group = self._find_enemy_group_by_id(combat.enemy_group_id)
        if unit is not None and enemy_group is not None:
            self._push_combat_notification(
                notification_id=f"{combat.combat_id}:ended",
                unit_name=unit.name or unit.unit_id,
                enemy_group_name=enemy_group.name or enemy_group.group_id,
                phase="ended",
            )
        if enemy_group is None:
            return
        self._enemy_groups = [
            active_enemy_group
            for active_enemy_group in self._enemy_groups
            if active_enemy_group.group_id != enemy_group.group_id
        ]

    def _push_combat_notification(
        self,
        *,
        notification_id: str,
        unit_name: str,
        enemy_group_name: str,
        phase: str,
    ) -> None:
        self._combat_notifications.append(
            CombatNotificationState(
                notification_id=notification_id,
                unit_name=unit_name,
                enemy_group_name=enemy_group_name,
                phase=phase,
                seconds_remaining=_COMBAT_NOTIFICATION_DURATION_SECONDS,
            )
        )
        self._combat_notifications = self._combat_notifications[-6:]

    def _set_unit_target(
        self,
        unit: UnitState,
        destination: tuple[float, float] | tuple[int, int],
        *,
        road_mode: str,
    ) -> None:
        final_target = self._clamp_point_to_map(destination, unit_type_id=unit.unit_type_id)
        if self._positions_match(unit.position, final_target):
            unit.position = final_target
            unit.target = None
            unit.path = ()
            return

        path = self._plan_unit_path(
            unit.position,
            final_target,
            road_mode=road_mode,
        )
        unit.target = final_target
        unit.path = tuple(path) if path else (final_target,)

    def _plan_unit_path(
        self,
        start: tuple[float, float],
        destination: tuple[float, float],
        *,
        road_mode: str,
    ) -> list[tuple[float, float]]:
        if road_mode == "off" or not self._roads:  # pragma: no mutate
            return [destination]  # pragma: no mutate

        road_points = self._primary_road_points()  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return [destination]  # pragma: no mutate

        start_anchor = self._road_anchor_for_point(start)  # pragma: no mutate
        destination_anchor = self._road_anchor_for_point(destination)  # pragma: no mutate
        path: list[tuple[float, float]] = []  # pragma: no mutate

        if road_mode == "prefer" and not self._positions_match(start, start_anchor, tolerance=2.0):  # pragma: no mutate
            path.append(start_anchor)  # pragma: no mutate

        path.extend(self._road_points_between(start_anchor, destination_anchor))  # pragma: no mutate

        if not path or not self._positions_match(path[-1], destination_anchor, tolerance=2.0):  # pragma: no mutate
            path.append(destination_anchor)  # pragma: no mutate

        if not self._positions_match(path[-1], destination, tolerance=2.0):  # pragma: no mutate
            path.append(destination)  # pragma: no mutate

        return self._deduplicate_points(path)  # pragma: no mutate

    def _road_mode_for_unit(self, unit_type_id: str) -> str:
        if unit_type_id == _SUPPLY_CONVOY_UNIT_TYPE_ID:  # pragma: no mutate
            return "prefer"  # pragma: no mutate
        return "off"  # pragma: no mutate

    def _primary_road_points(self) -> tuple[tuple[float, float], ...]:
        if not self._roads:  # pragma: no mutate
            return ()  # pragma: no mutate
        return tuple(self._roads[0].get("points", ()))  # pragma: no mutate

    def _road_anchor_for_point(self, point: tuple[float, float]) -> tuple[float, float]:
        road_points = self._primary_road_points()  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return point  # pragma: no mutate
        return min(  # pragma: no mutate
            road_points,  # pragma: no mutate
            key=lambda road_point: math.hypot(road_point[0] - point[0], road_point[1] - point[1]),  # pragma: no mutate
        )

    def _road_points_between(
        self,
        start_anchor: tuple[float, float],
        destination_anchor: tuple[float, float],
    ) -> list[tuple[float, float]]:
        road_points = self._primary_road_points()  # pragma: no mutate
        if not road_points:  # pragma: no mutate
            return []  # pragma: no mutate

        start_index = road_points.index(start_anchor)  # pragma: no mutate
        destination_index = road_points.index(destination_anchor)  # pragma: no mutate
        if start_index <= destination_index:  # pragma: no mutate
            return list(road_points[start_index : destination_index + 1])  # pragma: no mutate
        return list(reversed(road_points[destination_index : start_index + 1]))  # pragma: no mutate

    def _consume_supply_elapsed_seconds(self) -> float:
        now = float(self._time_provider())
        if self._last_supply_update_at is None:
            self._last_supply_update_at = now
            return 0.0
        elapsed_seconds = max(0.0, now - self._last_supply_update_at)
        self._last_supply_update_at = now
        return elapsed_seconds

    def _consume_combat_elapsed_seconds(self) -> float:
        now = float(self._time_provider())
        if self._last_combat_update_at is None:
            self._last_combat_update_at = now
            return 0.0
        elapsed_seconds = max(0.0, now - self._last_combat_update_at)
        self._last_combat_update_at = now
        return elapsed_seconds

    def _update_supply_network(self, *, elapsed_seconds: float) -> None:
        for landing_pad in self._landing_pads.values():
            self._update_landing_pad_supply(landing_pad, elapsed_seconds=max(0.0, elapsed_seconds))

    def _update_landing_pad_supply(
        self,
        landing_pad: LandingPadState,
        elapsed_seconds: float,
    ) -> None:
        if not self._is_landing_pad_secured(landing_pad):
            landing_pad.next_transport_eta_seconds = None
            landing_pad.active_transport = None
            return

        remaining_elapsed = max(0.0, elapsed_seconds)
        while True:
            if landing_pad.active_transport is not None:
                if remaining_elapsed <= 0.0:
                    self._refresh_transport_geometry(landing_pad)
                    return

                active_transport = landing_pad.active_transport
                assert active_transport is not None
                spent_seconds = min(remaining_elapsed, active_transport.seconds_remaining)
                remaining_elapsed -= spent_seconds
                self._advance_transport(landing_pad, spent_seconds)
                if remaining_elapsed <= 0.0:
                    return
                continue

            if self._landing_pad_total_stored(landing_pad) >= landing_pad.capacity:
                landing_pad.next_transport_eta_seconds = None
                return

            if landing_pad.next_transport_eta_seconds is None:
                landing_pad.next_transport_eta_seconds = _SUPPLY_INTERVAL_SECONDS

            if remaining_elapsed <= 0.0:
                return

            next_transport_eta_seconds = landing_pad.next_transport_eta_seconds
            assert next_transport_eta_seconds is not None
            if remaining_elapsed < next_transport_eta_seconds:
                landing_pad.next_transport_eta_seconds = next_transport_eta_seconds - remaining_elapsed
                return

            remaining_elapsed -= next_transport_eta_seconds
            landing_pad.next_transport_eta_seconds = None
            self._start_transport_for_landing_pad(landing_pad)

    def _advance_transport(self, landing_pad: LandingPadState, elapsed_seconds: float) -> None:
        active_transport = landing_pad.active_transport
        if active_transport is None:
            return

        active_transport.seconds_remaining = max(0.0, active_transport.seconds_remaining - elapsed_seconds)
        if active_transport.phase == "inbound":
            active_transport.position = self._transport_position_for_progress(active_transport)
            if active_transport.seconds_remaining > 0.0:
                return

            active_transport.phase = "unloading"
            active_transport.seconds_remaining = _SUPPLY_UNLOAD_SECONDS
            active_transport.total_phase_seconds = _SUPPLY_UNLOAD_SECONDS
            active_transport.position = active_transport.destination_position
            return

        if active_transport.phase == "unloading":
            active_transport.position = active_transport.destination_position
            if active_transport.seconds_remaining > 0.0:
                return

            self._apply_transport_delivery(landing_pad, active_transport.transport_type_id)
            active_transport.phase = "outbound"
            active_transport.seconds_remaining = _SUPPLY_DEPARTURE_SECONDS
            active_transport.total_phase_seconds = _SUPPLY_DEPARTURE_SECONDS
            active_transport.position = self._transport_position_for_progress(active_transport)
            return

        active_transport.position = self._transport_position_for_progress(active_transport)
        if active_transport.seconds_remaining > 0.0:
            return

        landing_pad.active_transport = None
        if self._landing_pad_total_stored(landing_pad) < landing_pad.capacity:
            landing_pad.next_transport_eta_seconds = _SUPPLY_INTERVAL_SECONDS

    def _start_transport_for_landing_pad(self, landing_pad: LandingPadState) -> None:
        transport_type_id = LANDING_PAD_TYPE_SPECS[landing_pad.pad_size].transport_type_id
        destination = self._map_object_center(landing_pad.object_id)
        origin = self._transport_origin_for_destination(destination)
        landing_pad.active_transport = SupplyTransportState(
            transport_id=f"{landing_pad.object_id}_supply",
            transport_type_id=transport_type_id,
            target_object_id=landing_pad.object_id,
            phase="inbound",
            position=origin,
            seconds_remaining=_SUPPLY_APPROACH_SECONDS,
            total_phase_seconds=_SUPPLY_APPROACH_SECONDS,
            origin_position=origin,
            destination_position=destination,
        )

    def _apply_transport_delivery(self, landing_pad: LandingPadState, transport_type_id: str) -> None:
        transport_spec = SUPPLY_TRANSPORT_TYPE_SPECS[transport_type_id]
        free_capacity = max(0, landing_pad.capacity - self._landing_pad_total_stored(landing_pad))
        if free_capacity <= 0:
            return

        cargo_by_resource = {
            resource_id: int(transport_spec.cargo.get(resource_id, 0))
            for resource_id in _SUPPLY_RESOURCE_ORDER
        }
        total_cargo = sum(cargo_by_resource.values())
        if total_cargo <= 0:
            return

        if total_cargo <= free_capacity:
            delivered_by_resource = cargo_by_resource
        else:
            delivered_by_resource = {resource_id: 0 for resource_id in _SUPPLY_RESOURCE_ORDER}
            remainders: list[tuple[float, str]] = []
            used_capacity = 0
            for resource_id in _SUPPLY_RESOURCE_ORDER:
                exact_allocation = (cargo_by_resource[resource_id] / total_cargo) * free_capacity
                base_allocation = min(cargo_by_resource[resource_id], int(math.floor(exact_allocation)))
                delivered_by_resource[resource_id] = base_allocation
                used_capacity += base_allocation
                remainders.append((exact_allocation - base_allocation, resource_id))

            remaining_capacity = free_capacity - used_capacity
            for _fraction, resource_id in sorted(remainders, reverse=True):
                if remaining_capacity <= 0:
                    break
                if delivered_by_resource[resource_id] >= cargo_by_resource[resource_id]:
                    continue
                delivered_by_resource[resource_id] += 1
                remaining_capacity -= 1

        for resource_id, delivered_amount in delivered_by_resource.items():
            landing_pad.resources[resource_id] = int(landing_pad.resources.get(resource_id, 0)) + delivered_amount

    def _update_supply_routes(self) -> None:
        for route_id in list(sorted(self._supply_routes)):
            route = self._supply_routes.get(route_id)
            if route is None:
                continue

            unit = self._find_unit_by_id(route.unit_id)
            if unit is None:
                self._supply_routes.pop(route_id, None)
                continue

            self._refresh_supply_route(route)

    def _refresh_supply_route_targets(self) -> None:
        for route in self._supply_routes.values():
            self._refresh_supply_route(route)

    def _refresh_supply_route(self, route: SupplyRouteState) -> None:
        unit = self._find_unit_by_id(route.unit_id)
        if unit is None:
            self._supply_routes.pop(route.route_id, None)
            return

        if route.source_object_id not in self._landing_pads or route.destination_object_id not in self._bases:
            self._clear_supply_route_for_unit(route.unit_id)
            return

        if self._resource_total(unit.carried_resources) > 0:
            self._refresh_route_delivery(route, unit)
            return

        self._refresh_route_pickup(route, unit)

    def _refresh_route_pickup(self, route: SupplyRouteState, unit: UnitState) -> None:
        pickup_target = self._object_target_point(route.source_object_id, unit.unit_type_id)
        if not self._positions_match(unit.position, pickup_target):
            if unit.target is None or not self._positions_match(unit.target, pickup_target):
                self._set_unit_target(unit, pickup_target, road_mode="only")
            route.phase = "to_pickup"
            return

        source = self._landing_pads[route.source_object_id]
        destination = self._bases[route.destination_object_id]
        available_at_source = self._landing_pad_total_stored(source)
        free_at_destination = max(0, destination.capacity - self._resource_total(destination.resources))
        unit_capacity = UNIT_TYPE_SPECS[unit.unit_type_id].supply_capacity
        transfer_total = min(unit_capacity, available_at_source, free_at_destination)

        if transfer_total <= 0:
            unit.target = None
            unit.path = ()
            route.phase = "awaiting_supply" if available_at_source <= 0 else "awaiting_capacity"
            return

        unit.carried_resources = self._take_resources(source.resources, transfer_total)
        self._set_unit_target(
            unit,
            self._object_target_point(route.destination_object_id, unit.unit_type_id),
            road_mode="only",
        )
        route.phase = "to_dropoff"

    def _refresh_route_delivery(self, route: SupplyRouteState, unit: UnitState) -> None:
        dropoff_target = self._object_target_point(route.destination_object_id, unit.unit_type_id)
        if not self._positions_match(unit.position, dropoff_target):
            if unit.target is None or not self._positions_match(unit.target, dropoff_target):
                self._set_unit_target(unit, dropoff_target, road_mode="only")
            route.phase = "to_dropoff"
            return

        destination = self._bases[route.destination_object_id]
        delivered_resources = self._store_resources(
            destination.resources,
            unit.carried_resources,
            destination.capacity,
        )
        delivered_total = self._resource_total(delivered_resources)
        carried_total = self._resource_total(unit.carried_resources)
        if delivered_total < carried_total:
            unit.carried_resources = self._subtract_resources(unit.carried_resources, delivered_resources)
            unit.target = None
            unit.path = ()
            route.phase = "awaiting_capacity"
            return

        unit.carried_resources = self._empty_resource_store()
        self._set_unit_target(
            unit,
            self._object_target_point(route.source_object_id, unit.unit_type_id),
            road_mode="only",
        )
        route.phase = "to_pickup"

    def _refresh_transport_geometry(self, landing_pad: LandingPadState) -> None:
        active_transport = landing_pad.active_transport
        if active_transport is None:
            return

        destination = self._map_object_center(landing_pad.object_id)
        active_transport.destination_position = destination
        active_transport.origin_position = self._transport_origin_for_destination(destination)
        active_transport.position = self._transport_position_for_progress(active_transport)

    def _movement_pixels_per_tick(self, unit_type_id: str) -> float:  # pragma: no mutate
        width, _height = self._map_size
        if width <= 0:
            return 0.0
        speed_kmph = UNIT_TYPE_SPECS[unit_type_id].speed_kmph
        km_per_tick = (speed_kmph / 3600.0) * _SIMULATION_SECONDS_PER_TICK
        km_per_pixel = _MAP_WIDTH_KM / float(width)
        if km_per_pixel <= 0:
            return 0.0
        return km_per_tick / km_per_pixel

    def _point_in_map(self, position: tuple[int, int]) -> bool:
        width, height = self._map_size
        x, y = position
        return 0 <= x <= width and 0 <= y <= height

    def _find_unit_at(self, position: tuple[int, int]) -> UnitState | None:
        x, y = position
        for unit in reversed(self._units):
            left, top, right, bottom = self._unit_bounds(unit)
            if left <= x <= right and top <= y <= bottom:
                return unit
        return None

    def _find_unit_by_id(self, unit_id: str) -> UnitState | None:
        for unit in self._units:
            if unit.unit_id == unit_id:
                return unit
        return None

    def _find_enemy_group_by_id(self, group_id: str) -> ZombieGroupState | None:
        for enemy_group in self._enemy_groups:
            if enemy_group.group_id == group_id:
                return enemy_group
        return None

    def _combat_for_unit(self, unit_id: str) -> CombatState | None:
        for combat in self._combats.values():
            if combat.unit_id == unit_id:
                return combat
        return None

    def _combat_for_enemy_group(self, group_id: str) -> CombatState | None:
        for combat in self._combats.values():
            if combat.enemy_group_id == group_id:
                return combat
        return None

    def _combat_seconds_remaining_for_unit(self, unit_id: str) -> float | None:
        combat = self._combat_for_unit(unit_id)
        if combat is None:
            return None
        return combat.seconds_remaining

    def _unit_bounds(self, unit: UnitState) -> tuple[int, int, int, int]:
        size = UNIT_TYPE_SPECS[unit.unit_type_id].marker_size_px
        left = int(unit.position[0] - size / 2)
        top = int(unit.position[1] - size / 2)
        right = left + size
        bottom = top + size
        return (left, top, right, bottom)

    def _bounds_overlap(
        self,
        first_bounds: tuple[int, int, int, int],
        second_bounds: tuple[int, int, int, int],
    ) -> bool:
        first_left, first_top, first_right, first_bottom = first_bounds
        second_left, second_top, second_right, second_bottom = second_bounds
        return not (
            first_right < second_left
            or second_right < first_left
            or first_bottom < second_top
            or second_bottom < first_top
        )

    def _enemy_group_bounds(self, enemy_group: ZombieGroupState) -> tuple[int, int, int, int]:
        size = _ZOMBIE_GROUP_MARKER_SIZE_PX
        left = int(enemy_group.position[0] - size / 2)
        top = int(enemy_group.position[1] - size / 2)
        right = left + size
        bottom = top + size
        return (left, top, right, bottom)

    def _clamp_point_to_map(  # pragma: no mutate
        self,
        position: tuple[float, float] | tuple[int, int],
        *,
        unit_type_id: str,
    ) -> tuple[float, float]:
        width, height = self._map_size
        if width <= 0 or height <= 0:
            return (float(position[0]), float(position[1]))

        half_size = UNIT_TYPE_SPECS[unit_type_id].marker_size_px / 2
        min_x = half_size
        max_x = width - half_size
        min_y = half_size
        max_y = height - half_size
        clamped_x = min(max(float(position[0]), min_x), max_x)
        clamped_y = min(max(float(position[1]), min_y), max_y)
        return (clamped_x, clamped_y)

    def _clamp_enemy_point_to_map(
        self,
        position: tuple[float, float] | tuple[int, int],
    ) -> tuple[float, float]:
        width, height = self._map_size
        if width <= 0 or height <= 0:
            return (float(position[0]), float(position[1]))

        half_size = _ZOMBIE_GROUP_MARKER_SIZE_PX / 2
        min_x = half_size
        max_x = width - half_size
        min_y = half_size
        max_y = height - half_size
        clamped_x = min(max(float(position[0]), min_x), max_x)
        clamped_y = min(max(float(position[1]), min_y), max_y)
        return (clamped_x, clamped_y)

    def _get_selected_unit(self) -> UnitState | None:
        if self._selected_unit_id is None:
            return None
        unit = self._find_unit_by_id(self._selected_unit_id)
        if unit is not None:
            return unit
        self._selected_unit_id = None
        return None

    def _display_seconds(self, seconds: float | None) -> int | None:
        if seconds is None:
            return None
        return max(0, int(math.ceil(seconds)))

    def _empty_resource_store(self) -> dict[str, int]:
        return {resource_id: 0 for resource_id in _SUPPLY_RESOURCE_ORDER}

    def _resource_total(self, resources: dict[str, int]) -> int:
        return sum(int(resources.get(resource_id, 0)) for resource_id in _SUPPLY_RESOURCE_ORDER)

    def _trim_resources_to_capacity(self, resources: dict[str, int], capacity: int) -> dict[str, int]:
        remaining_capacity = max(0, int(capacity))
        trimmed_resources: dict[str, int] = {}
        for resource_id in _SUPPLY_RESOURCE_ORDER:
            kept_amount = min(max(0, int(resources.get(resource_id, 0))), remaining_capacity)
            trimmed_resources[resource_id] = kept_amount
            remaining_capacity -= kept_amount
        return trimmed_resources

    def _is_landing_pad_secured(self, landing_pad: LandingPadState) -> bool:
        if not landing_pad.secured_by_objective_id:
            return True
        return bool(self._objective_status.get(landing_pad.secured_by_objective_id, False))

    def _landing_pad_total_stored(self, landing_pad: LandingPadState) -> int:
        return self._resource_total(landing_pad.resources)

    def _map_object_center(self, object_id: str) -> tuple[float, float]:
        map_object = next((obj for obj in self._map_objects if obj["id"] == object_id), None)
        if map_object is None:
            return (0.0, 0.0)  # pragma: no mutate
        left, top, right, bottom = map_object["bounds"]
        return ((left + right) / 2.0, (top + bottom) / 2.0)  # pragma: no mutate

    def _object_target_point(self, object_id: str, unit_type_id: str) -> tuple[float, float]:
        return self._clamp_point_to_map(self._map_object_center(object_id), unit_type_id=unit_type_id)

    def _positions_match(  # pragma: no mutate
        self,
        first: tuple[float, float],
        second: tuple[float, float],
        *,
        tolerance: float = 0.5,
    ) -> bool:
        return math.hypot(first[0] - second[0], first[1] - second[1]) <= tolerance  # pragma: no mutate

    def _unit_can_transport_supplies(self, unit_type_id: str) -> bool:
        return unit_type_id == _SUPPLY_CONVOY_UNIT_TYPE_ID

    def _supply_route_id_for_unit(self, unit_id: str) -> str | None:
        for route in self._supply_routes.values():
            if route.unit_id == unit_id:
                return route.route_id
        return None

    def _unit_has_supply_route(self, unit_id: str) -> bool:
        return self._supply_route_id_for_unit(unit_id) is not None

    def _clear_supply_route_for_unit(self, unit_id: str) -> None:  # pragma: no mutate
        route_id = self._supply_route_id_for_unit(unit_id)
        if route_id is not None:  # pragma: no mutate
            self._supply_routes.pop(route_id, None)

    def _is_valid_supply_route_pair(  # pragma: no mutate
        self,
        *,
        source_object_id: str,
        destination_object_id: str,
    ) -> bool:
        if source_object_id not in self._landing_pads or destination_object_id not in self._bases:
            return False
        return self._is_landing_pad_secured(self._landing_pads[source_object_id])

    def _take_resources(self, storage: dict[str, int], amount: int) -> dict[str, int]:  # pragma: no mutate
        remaining = max(0, int(amount))
        taken = self._empty_resource_store()
        for resource_id in _SUPPLY_RESOURCE_ORDER:
            if remaining <= 0:  # pragma: no mutate
                break
            available = max(0, int(storage.get(resource_id, 0)))  # pragma: no mutate
            transferred = min(available, remaining)  # pragma: no mutate
            storage[resource_id] = available - transferred  # pragma: no mutate
            taken[resource_id] = transferred  # pragma: no mutate
            remaining -= transferred  # pragma: no mutate
        return taken

    def _store_resources(  # pragma: no mutate
        self,
        storage: dict[str, int],
        cargo: dict[str, int],
        capacity: int,
    ) -> dict[str, int]:
        remaining_capacity = max(0, int(capacity) - self._resource_total(storage))
        stored = self._empty_resource_store()
        for resource_id in _SUPPLY_RESOURCE_ORDER:
            if remaining_capacity <= 0:  # pragma: no mutate
                break
            available = max(0, int(cargo.get(resource_id, 0)))  # pragma: no mutate
            transferred = min(available, remaining_capacity)  # pragma: no mutate
            storage[resource_id] = int(storage.get(resource_id, 0)) + transferred  # pragma: no mutate
            stored[resource_id] = transferred  # pragma: no mutate
            remaining_capacity -= transferred  # pragma: no mutate
        return stored

    def _subtract_resources(  # pragma: no mutate
        self,
        cargo: dict[str, int],
        delivered: dict[str, int],
    ) -> dict[str, int]:
        remaining = self._empty_resource_store()
        for resource_id in _SUPPLY_RESOURCE_ORDER:
            remaining[resource_id] = max(  # pragma: no mutate
                0,
                int(cargo.get(resource_id, 0)) - int(delivered.get(resource_id, 0)),
            )
        return remaining

    def _transport_origin_for_destination(
        self,
        destination: tuple[float, float],
    ) -> tuple[float, float]:
        width, height = self._map_size  # pragma: no mutate
        spawn_x = max(  # pragma: no mutate
            float(width) + _TRANSPORT_SPAWN_OFFSET_X,
            destination[0] + _TRANSPORT_SPAWN_OFFSET_X,
        )
        max_y = max(24.0, float(height) - 24.0)  # pragma: no mutate
        spawn_y = min(max(destination[1] - _TRANSPORT_SPAWN_OFFSET_Y, 24.0), max_y)  # pragma: no mutate
        return (spawn_x, spawn_y)  # pragma: no mutate

    def _interpolate_points(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        progress: float,
    ) -> tuple[float, float]:
        clamped_progress = min(max(progress, 0.0), 1.0)  # pragma: no mutate
        return (
            start[0] + (end[0] - start[0]) * clamped_progress,  # pragma: no mutate
            start[1] + (end[1] - start[1]) * clamped_progress,  # pragma: no mutate
        )

    def _transport_position_for_progress(  # pragma: no mutate
        self,
        active_transport: SupplyTransportState,
    ) -> tuple[float, float]:
        if active_transport.phase == "unloading":
            return active_transport.destination_position  # pragma: no mutate

        progress = 1.0  # pragma: no mutate
        if active_transport.total_phase_seconds > 0:
            progress = 1.0 - (  # pragma: no mutate
                active_transport.seconds_remaining / active_transport.total_phase_seconds
            )

        if active_transport.phase == "outbound":  # pragma: no mutate
            return self._interpolate_points(  # pragma: no mutate
                active_transport.destination_position,  # pragma: no mutate
                active_transport.origin_position,  # pragma: no mutate
                progress,  # pragma: no mutate
            )

        return self._interpolate_points(  # pragma: no mutate
            active_transport.origin_position,  # pragma: no mutate
            active_transport.destination_position,  # pragma: no mutate
            progress,  # pragma: no mutate
        )


def create_default_game_session(
    *,
    time_provider: Callable[[], float] | None = None,
    search_roll_provider: Callable[[], float] | None = None,
) -> GameSession:
    return GameSession(
        mission_objectives_evaluator=create_default_mission_objectives_evaluator(),
        time_provider=time_provider,
        search_roll_provider=search_roll_provider,
    )
