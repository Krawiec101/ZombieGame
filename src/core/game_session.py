from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Mapping
from typing import Any

from contracts.game_state import (
    BaseSnapshot,
    CombatNotificationSnapshot,
    CombatSnapshot,
    GameStateSnapshot,
    LandingPadSnapshot,
    MissionObjectiveProgressSnapshot,
    MissionReportSnapshot,
    RoadSnapshot,
    SupplyRouteEndpointSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    ZombieGroupSnapshot,
)
from core.combat import CombatNotificationState, CombatResolver, CombatState, ZombieGroupState
from core.mission_objectives import (
    MissionObjectivesEvaluator,
    create_default_mission_objectives_evaluator,
)
from core.mission_progress import (
    MainObjectiveReportRule,
    MissionProgressService,
    main_objective_report_rules_from_config,
)
from core.model.buildings import (
    SUPPLY_RESOURCE_ORDER,
    BaseState,
    LandingPadState,
    LandingPadTypeSpec,
    SupplyDispatchPoint,
    SupplyReceivePoint,
    SupplyRouteState,
    SupplyTransportState,
    SupplyTransportTypeSpec,
    empty_resource_store,
    interpolate_points,
)
from core.model.units import (
    CommanderState,
    ReinforcementTemplate,
    UnitEquipmentState,
    UnitOrganizationState,
    UnitState,
    UnitTypeSpec,
    VehicleAssignmentState,
    VehicleTypeSpec,
)
from core.navigation import NavigationService
from core.scenario_config import load_default_scenario_config
from core.session_bootstrap import (
    SessionBootstrapper,
)
from core.session_bootstrap import (
    commander_state_from_config as _session_commander_state_from_config,
)
from core.session_bootstrap import (
    equipment_state_from_config as _session_equipment_state_from_config,
)
from core.session_bootstrap import (
    organization_state_from_config as _session_organization_state_from_config,
)
from core.session_bootstrap import (
    reinforcement_templates_from_config as _session_reinforcement_templates_from_config,
)
from core.session_bootstrap import (
    vehicle_assignments_from_config as _session_vehicle_assignments_from_config,
)
from core.snapshots import GameStateSnapshotBuilder
from core.supply_route_manager import SupplyRouteEndpoint, SupplyRouteManager

_SIMULATION_SECONDS_PER_TICK = 8.0
_SUPPLY_INTERVAL_SECONDS = 45.0
_SUPPLY_APPROACH_SECONDS = 6.0
_SUPPLY_UNLOAD_SECONDS = 14.0
_SUPPLY_DEPARTURE_SECONDS = 6.0
_SUPPLY_ROUTE_LOAD_SECONDS = 6.0
_SUPPLY_ROUTE_UNLOAD_SECONDS = 6.0
_COMBAT_MIN_DURATION_SECONDS = 24.0
_COMBAT_MAX_DURATION_SECONDS = 60.0
_COMBAT_EXCHANGE_INTERVAL_SECONDS = 6.0
_COMBAT_NOTIFICATION_DURATION_SECONDS = 12.0
_SUPPLY_RESOURCE_ORDER = SUPPLY_RESOURCE_ORDER
_BASE_SUPPLY_CAPACITY = 120
_TRANSPORT_SPAWN_OFFSET_X = 96.0
_TRANSPORT_SPAWN_OFFSET_Y = 120.0
_ZOMBIE_GROUP_MARKER_SIZE_PX = 22
_ROAD_SAMPLES_PER_SEGMENT = 14


_DEFAULT_SCENARIO = load_default_scenario_config()
_MAP_WIDTH_KM = _DEFAULT_SCENARIO.map_width_km
_MAP_OBJECT_LAYOUT = _DEFAULT_SCENARIO.map_objects
_RECON_SITE_LAYOUT = _DEFAULT_SCENARIO.recon_sites
_ROAD_LAYOUTS = _DEFAULT_SCENARIO.roads
_INITIAL_UNIT_LAYOUT = _DEFAULT_SCENARIO.initial_units
_INITIAL_ENEMY_GROUP_LAYOUT = _DEFAULT_SCENARIO.initial_enemy_groups


def _commander_state_from_config(config: dict[str, Any]) -> CommanderState:
    return _session_commander_state_from_config(config)


def _equipment_state_from_config(config: dict[str, Any]) -> UnitEquipmentState:
    return _session_equipment_state_from_config(config)


def _vehicle_assignments_from_config(value: Any) -> tuple[VehicleAssignmentState, ...]:
    return _session_vehicle_assignments_from_config(value)


def _organization_state_from_config(config: dict[str, Any]) -> UnitOrganizationState:
    return _session_organization_state_from_config(config)


def _reinforcement_templates_from_config() -> tuple[ReinforcementTemplate, ...]:
    return _session_reinforcement_templates_from_config(_DEFAULT_SCENARIO.reinforcements)


def _main_objective_report_rules_from_config() -> tuple[MainObjectiveReportRule, ...]:
    return main_objective_report_rules_from_config(_DEFAULT_SCENARIO.mission_reports)


REINFORCEMENT_TEMPLATES: tuple[ReinforcementTemplate, ...] = _reinforcement_templates_from_config()
MAIN_OBJECTIVE_REPORT_RULES: tuple[MainObjectiveReportRule, ...] = _main_objective_report_rules_from_config()


UNIT_TYPE_SPECS: dict[str, UnitTypeSpec] = {
    "infantry_squad": UnitTypeSpec(
        type_id="infantry_squad",
        speed_kmph=4.2,
        marker_size_px=18,
        armament_key="game.unit.armament.rifles_lmg",
        attack=4,
        defense=5,
    ),
    "mechanized_squad": UnitTypeSpec(
        type_id="mechanized_squad",
        speed_kmph=18.0,
        marker_size_px=20,
        armament_key="game.unit.armament.apc_autocannon",
        attack=7,
        defense=8,
        can_transport_supplies=True,
        supply_capacity=24,
        supply_load_seconds=_SUPPLY_ROUTE_LOAD_SECONDS,
        supply_unload_seconds=_SUPPLY_ROUTE_UNLOAD_SECONDS,
    ),
}

VEHICLE_TYPE_SPECS: dict[str, VehicleTypeSpec] = {
    "wheeled_apc": VehicleTypeSpec(
        type_id="wheeled_apc",
        transport_speed_bonus_kmph=6.0,
        attack_bonus=1,
        defense_bonus=1,
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
        self._combat_resolver = CombatResolver(
            min_duration_seconds=_COMBAT_MIN_DURATION_SECONDS,
            max_duration_seconds=_COMBAT_MAX_DURATION_SECONDS,
            exchange_interval_seconds=_COMBAT_EXCHANGE_INTERVAL_SECONDS,
            notification_duration_seconds=_COMBAT_NOTIFICATION_DURATION_SECONDS,
        )
        self._navigation_service = NavigationService(
            simulation_seconds_per_tick=_SIMULATION_SECONDS_PER_TICK,
            map_width_km=_MAP_WIDTH_KM,
        )
        self._mission_progress_service = MissionProgressService()
        self._session_bootstrapper = SessionBootstrapper()
        self._snapshot_builder = GameStateSnapshotBuilder()

        self._map_size: tuple[int, int] = (0, 0)
        self._map_objects: list[dict[str, Any]] = []
        self._roads: list[dict[str, Any]] = []
        self._bases: dict[str, BaseState] = {}
        self._landing_pads: dict[str, LandingPadState] = {}
        self._supply_route_manager = SupplyRouteManager(
            resource_order=_SUPPLY_RESOURCE_ORDER,
            can_unit_type_transport_supplies=self._unit_can_transport_supplies,
        )
        self._supply_routes = {}
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
        self._supply_route_manager.clear()
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

    @property
    def _supply_routes(self) -> dict[str, SupplyRouteState]:
        return self._supply_route_manager.routes

    @_supply_routes.setter
    def _supply_routes(self, routes: dict[str, SupplyRouteState]) -> None:
        self._supply_route_manager.routes = routes

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
        self._update_supply_routes(elapsed_seconds=elapsed_supply_seconds)

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
        self._supply_route_manager.create_route(
            selected_unit=self._get_selected_unit(),
            source_object_id=source_object_id,
            destination_object_id=destination_object_id,
            endpoints=self._supply_route_endpoints(),
            dispatch_points=self._supply_dispatch_points(),
            receive_points=self._supply_receive_points(),
            object_target_point=self._object_target_point,
            positions_match=self._positions_match,
            set_unit_target=lambda unit, target: self._set_unit_target(unit, target, road_mode="only"),
            unit_supply_capacity=self._unit_supply_capacity,
            find_unit_by_id=self._find_unit_by_id,
            refresh_route=self._refresh_supply_route,
        )

    def map_objects_snapshot(self) -> list[dict[str, Any]]:
        return self._snapshot_builder.map_objects_state(self._map_objects)

    def enemy_groups_state_snapshot(self) -> list[dict[str, Any]]:
        return self._snapshot_builder.enemy_groups_state(self._enemy_groups)

    def roads_snapshot(self) -> tuple[RoadSnapshot, ...]:
        return self._snapshot_builder.roads(self._roads)

    def units_snapshot(self) -> list[dict[str, Any]]:  # pragma: no mutate
        return self._snapshot_builder.units(
            self._units,
            unit_type_specs=UNIT_TYPE_SPECS,
            unit_armament_key=self._unit_armament_key,
            unit_attack=self._unit_attack,
            unit_defense=self._unit_defense,
            resource_order=_SUPPLY_RESOURCE_ORDER,
            supply_route_id_for_unit=self._supply_route_id_for_unit,
            combat_for_unit=self._combat_for_unit,
            combat_seconds_remaining_for_unit=self._combat_seconds_remaining_for_unit,
            display_seconds=self._display_seconds,
        )

    def bases_snapshot(self) -> tuple[BaseSnapshot, ...]:
        return self._snapshot_builder.bases(
            self._bases,
            resource_order=_SUPPLY_RESOURCE_ORDER,
        )

    def enemy_groups_snapshot(self) -> tuple[ZombieGroupSnapshot, ...]:
        return self._snapshot_builder.enemy_groups(
            self._enemy_groups,
            marker_size_px=_ZOMBIE_GROUP_MARKER_SIZE_PX,
            combat_for_enemy_group=self._combat_for_enemy_group,
        )

    def combats_snapshot(self) -> tuple[CombatSnapshot, ...]:
        return self._snapshot_builder.combats(
            self._combats,
            find_unit_by_id=self._find_unit_by_id,
            find_enemy_group_by_id=self._find_enemy_group_by_id,
            display_seconds=self._display_seconds,
        )

    def combat_notifications_snapshot(self) -> tuple[CombatNotificationSnapshot, ...]:
        return self._snapshot_builder.combat_notifications(
            self._combat_notifications,
            display_seconds=self._display_seconds,
        )

    def landing_pads_snapshot(self) -> tuple[LandingPadSnapshot, ...]:
        return self._snapshot_builder.landing_pads(
            self._landing_pads,
            objective_status=self._objective_status,
            resource_order=_SUPPLY_RESOURCE_ORDER,
            display_seconds=self._display_seconds,
        )

    def supply_transports_snapshot(self) -> tuple[SupplyTransportSnapshot, ...]:  # pragma: no mutate
        return self._snapshot_builder.supply_transports(self._landing_pads)

    def supply_routes_snapshot(self) -> tuple[SupplyRouteSnapshot, ...]:
        return self._supply_route_manager.supply_routes_snapshot(
            find_unit_by_id=self._find_unit_by_id,
            unit_supply_capacity=self._unit_supply_capacity,
        )

    def supply_route_endpoints_snapshot(self) -> tuple[SupplyRouteEndpointSnapshot, ...]:
        return self._snapshot_builder.supply_route_endpoints(
            self._supply_route_endpoints(),
        )

    def supply_routes_state_snapshot(self) -> list[dict[str, Any]]:
        return self._supply_route_manager.supply_routes_state_snapshot()

    def objective_status_snapshot(self) -> dict[str, bool]:
        return dict(self._objective_status)

    def objective_definitions_snapshot(self) -> tuple[dict[str, str], ...]:
        return self._objective_definitions

    def objective_progress_snapshot(self) -> tuple[MissionObjectiveProgressSnapshot, ...]:
        return self._snapshot_builder.objective_progress(self._objective_status)

    def mission_reports_snapshot(self) -> tuple[MissionReportSnapshot, ...]:
        return tuple(self._mission_reports)

    def selected_unit_id(self) -> str | None:
        return self._selected_unit_id

    def snapshot(self) -> GameStateSnapshot:  # pragma: no mutate
        return self._snapshot_builder.game_state(
            map_objects=self.map_objects_snapshot(),
            roads=self.roads_snapshot(),
            units=self.units_snapshot(),
            enemy_groups=self.enemy_groups_snapshot(),
            selected_unit_id=self.selected_unit_id(),
            objective_definitions=self.objective_definitions_snapshot(),
            objective_progress=self.objective_progress_snapshot(),
            mission_reports=self.mission_reports_snapshot(),
            landing_pads=self.landing_pads_snapshot(),
            bases=self.bases_snapshot(),
            supply_route_endpoints=self.supply_route_endpoints_snapshot(),
            supply_transports=self.supply_transports_snapshot(),
            supply_routes=self.supply_routes_snapshot(),
            combats=self.combats_snapshot(),
            combat_notifications=self.combat_notifications_snapshot(),
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
        roads: list[dict[str, Any]] = []
        for road_layout in _ROAD_LAYOUTS:
            control_points: list[tuple[float, float]] = []
            for control_point in road_layout.get("control_points", []):
                resolved_point = self._resolve_road_control_point(dict(control_point))
                if resolved_point is None:
                    control_points = []
                    break
                control_points.append(resolved_point)
            if len(control_points) < 2:
                continue
            roads.append(
                {
                    "id": str(road_layout.get("id", "")),
                    "points": self._sample_road_curve(tuple(control_points)),
                }
            )
        return roads

    def _resolve_road_control_point(self, control_point: dict[str, Any]) -> tuple[float, float] | None:
        point_type = str(control_point.get("point_type", "relative_map_point"))
        if point_type == "map_object_center":
            object_id = str(control_point.get("object_id", ""))
            if self._map_object_bounds(object_id) is None:
                return None
            return self._map_object_center(object_id)

        width, height = self._map_size
        return (
            width * float(control_point.get("anchor_x", 0.0)),
            height * float(control_point.get("anchor_y", 0.0)),
        )

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
        if self._map_object_bounds("hq") is None:
            self._units = []
            self._enemy_groups = []
            return

        bootstrap_state = self._session_bootstrapper.initialize_runtime_state(
            initial_unit_layout=_INITIAL_UNIT_LAYOUT,
            initial_enemy_group_layout=_INITIAL_ENEMY_GROUP_LAYOUT,
            map_object_bounds=self._map_object_bounds,
            map_object_center=self._map_object_center,
            road_anchor_for_point=self._road_anchor_for_point,
            clamp_unit_point=lambda position, unit_type_id: self._clamp_point_to_map(
                position,
                unit_type_id=unit_type_id,
            ),
            clamp_enemy_point=self._clamp_enemy_point_to_map,
        )
        self._units = bootstrap_state.units
        self._enemy_groups = bootstrap_state.enemy_groups
        self._units_initialized = True

    def _spawn_position_from_layout(self, layout: dict[str, Any]) -> tuple[float, float] | None:
        return self._session_bootstrapper.spawn_position_from_layout(
            layout,
            map_object_bounds=self._map_object_bounds,
            map_object_center=self._map_object_center,
        )

    def _clamp_enemy_groups_to_map(self) -> None:
        for enemy_group in self._enemy_groups:
            enemy_group.position = self._clamp_enemy_point_to_map(enemy_group.position)

    def _investigate_recon_sites(self) -> None:
        self._mission_progress_service.investigate_recon_sites(
            recon_site_layout=_RECON_SITE_LAYOUT,
            investigated_recon_site_ids=self._investigated_recon_site_ids,
            units=self._units,
            map_object_bounds=self._map_object_bounds,
            point_in_bounds=self._point_in_bounds,
            should_reveal_reinforcement=self._should_reveal_reinforcement,
            spawn_next_reinforcement=self._spawn_next_reinforcement,
            refresh_dynamic_map_objects=self._refresh_dynamic_map_objects,
        )

    def _should_reveal_reinforcement(self) -> bool:
        return self._mission_progress_service.should_reveal_reinforcement(
            reinforcement_templates=REINFORCEMENT_TEMPLATES,
            found_reinforcement_unit_ids=self._found_reinforcement_unit_ids,
            investigated_recon_site_ids=self._investigated_recon_site_ids,
            recon_site_count=len(_RECON_SITE_LAYOUT),
            search_roll_provider=self._search_roll_provider,
        )

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

        self._units.append(
            self._session_bootstrapper.spawn_reinforcement(
                next_template,
                site_id=site_id,
                map_object_center=self._map_object_center,
                clamp_unit_point=lambda position, unit_type_id: self._clamp_point_to_map(
                    position,
                    unit_type_id=unit_type_id,
                ),
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
        self._mission_progress_service.update_main_objective_reports(
            rules=MAIN_OBJECTIVE_REPORT_RULES,
            completed_main_objective_ids=self._completed_main_objective_ids,
            objective_status=self._objective_status,
            mission_reports=self._mission_reports,
        )

    def _update_combats(self, *, elapsed_seconds: float) -> None:
        self._combat_resolver.update_combats(
            self._combats,
            self._combat_notifications,
            elapsed_seconds=elapsed_seconds,
            find_unit_by_id=self._find_unit_by_id,
            find_enemy_group_by_id=self._find_enemy_group_by_id,
            remove_enemy_group_by_id=self._remove_enemy_group_by_id,
            unit_attack=self._unit_attack,
            unit_defense=self._unit_defense,
        )

    def _update_combat_notifications(self, *, elapsed_seconds: float) -> None:
        self._combat_notifications = self._combat_resolver.update_notifications(
            self._combat_notifications,
            elapsed_seconds=elapsed_seconds,
        )

    def _start_combats_for_colliding_units(self) -> None:
        self._combat_resolver.start_combats_for_colliding_units(
            self._combats,
            self._combat_notifications,
            units=self._units,
            enemy_groups=self._enemy_groups,
            combat_for_unit=self._combat_for_unit,
            combat_for_enemy_group=self._combat_for_enemy_group,
            unit_bounds=self._unit_bounds,
            enemy_group_bounds=self._enemy_group_bounds,
            bounds_overlap=self._bounds_overlap,
            unit_attack=self._unit_attack,
            clamp_unit_position=lambda position, unit_type_id: self._clamp_point_to_map(
                position,
                unit_type_id=unit_type_id,
            ),
        )

    def _update_units_position(self) -> None:
        for unit in self._units:
            if self._combat_for_unit(unit.unit_id) is not None:
                continue
            if unit.target is None:
                continue

            def clamp_position(
                position: tuple[float, float],
                unit_type_id: str = unit.unit_type_id,
            ) -> tuple[float, float]:
                return self._clamp_point_to_map(position, unit_type_id=unit_type_id)
            speed_px_per_tick = self._unit_movement_pixels_per_tick(unit)
            unit.advance_towards_target(
                speed_px_per_tick=speed_px_per_tick,
                clamp_position=clamp_position,
            )

    def _start_combat(self, unit: UnitState, enemy_group: ZombieGroupState) -> None:
        self._combat_resolver.start_combat(
            self._combats,
            self._combat_notifications,
            unit=unit,
            enemy_group=enemy_group,
            unit_attack=self._unit_attack,
            clamp_unit_position=lambda position, unit_type_id: self._clamp_point_to_map(
                position,
                unit_type_id=unit_type_id,
            ),
        )

    def _combat_duration_seconds(self, unit: UnitState, enemy_group: ZombieGroupState) -> float:
        return self._combat_resolver.combat_duration_seconds(
            unit,
            enemy_group,
            unit_attack=self._unit_attack,
        )

    def _apply_combat_attrition(self, unit: UnitState, enemy_group: ZombieGroupState) -> None:
        self._combat_resolver.apply_combat_attrition(
            unit,
            enemy_group,
            unit_attack=self._unit_attack,
            unit_defense=self._unit_defense,
        )

    def _resolve_combat(self, combat: CombatState) -> None:
        self._combat_resolver.resolve_combat(
            self._combats,
            self._combat_notifications,
            combat=combat,
            find_unit_by_id=self._find_unit_by_id,
            find_enemy_group_by_id=self._find_enemy_group_by_id,
            remove_enemy_group_by_id=self._remove_enemy_group_by_id,
        )

    def _push_combat_notification(
        self,
        *,
        notification_id: str,
        unit_name: str,
        enemy_group_name: str,
        phase: str,
    ) -> None:
        self._combat_resolver.append_notification(
            self._combat_notifications,
            notification_id=notification_id,
            unit_name=unit_name,
            enemy_group_name=enemy_group_name,
            phase=phase,
        )

    def _set_unit_target(
        self,
        unit: UnitState,
        destination: tuple[float, float] | tuple[int, int],
        *,
        road_mode: str,
    ) -> None:
        self._navigation_service.set_unit_target(
            unit,
            destination,
            road_mode=road_mode,
            roads=self._roads,
            clamp_point_to_map=lambda position, unit_type_id: self._clamp_point_to_map(
                position,
                unit_type_id=unit_type_id,
            ),
            positions_match=self._positions_match,
            deduplicate_points=lambda points: self._deduplicate_points(list(points)),
        )

    def _plan_unit_path(
        self,
        start: tuple[float, float],
        destination: tuple[float, float],
        *,
        road_mode: str,
    ) -> list[tuple[float, float]]:
        return self._navigation_service.plan_unit_path(
            start,
            destination,
            road_mode=road_mode,
            roads=self._roads,
            positions_match=self._positions_match,
            deduplicate_points=lambda points: self._deduplicate_points(list(points)),
        )

    def _road_mode_for_unit(self, unit_type_id: str) -> str:
        return self._navigation_service.road_mode_for_unit(
            unit_type_id,
            can_unit_type_create_convoy=self._supply_route_manager.can_unit_type_create_convoy,
        )

    def _primary_road_points(self) -> tuple[tuple[float, float], ...]:
        return self._navigation_service.primary_road_points(self._roads)

    def _road_anchor_for_point(self, point: tuple[float, float]) -> tuple[float, float]:
        return self._navigation_service.road_anchor_for_point(
            point,
            roads=self._roads,
        )

    def _road_points_between(
        self,
        start_anchor: tuple[float, float],
        destination_anchor: tuple[float, float],
    ) -> list[tuple[float, float]]:
        return self._navigation_service.road_points_between(
            start_anchor,
            destination_anchor,
            roads=self._roads,
        )

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
        landing_pad.update_supply(
            elapsed_seconds,
            is_secured=landing_pad.is_secured(self._objective_status),
            supply_interval_seconds=_SUPPLY_INTERVAL_SECONDS,
            refresh_transport_geometry=lambda: self._refresh_transport_geometry(landing_pad),
            start_transport=lambda: self._start_transport_for_landing_pad(landing_pad),
            advance_transport=lambda spent_seconds: self._advance_transport(landing_pad, spent_seconds),
            resource_order=_SUPPLY_RESOURCE_ORDER,
        )

    def _advance_transport(self, landing_pad: LandingPadState, elapsed_seconds: float) -> None:
        active_transport = landing_pad.active_transport
        if active_transport is None:
            return
        landing_pad.advance_transport(
            elapsed_seconds=elapsed_seconds,
            unload_seconds=_SUPPLY_UNLOAD_SECONDS,
            departure_seconds=_SUPPLY_DEPARTURE_SECONDS,
            delivery_cargo=SUPPLY_TRANSPORT_TYPE_SPECS[active_transport.transport_type_id].cargo,
            supply_interval_seconds=_SUPPLY_INTERVAL_SECONDS,
            resource_order=_SUPPLY_RESOURCE_ORDER,
        )

    def _start_transport_for_landing_pad(self, landing_pad: LandingPadState) -> None:
        transport_type_id = LANDING_PAD_TYPE_SPECS[landing_pad.pad_size].transport_type_id
        destination = self._map_object_center(landing_pad.object_id)
        origin = self._transport_origin_for_destination(destination)
        landing_pad.start_transport(
            transport_type_id=transport_type_id,
            origin_position=origin,
            destination_position=destination,
            approach_seconds=_SUPPLY_APPROACH_SECONDS,
        )

    def _apply_transport_delivery(self, landing_pad: LandingPadState, transport_type_id: str) -> None:
        landing_pad.apply_transport_delivery(
            SUPPLY_TRANSPORT_TYPE_SPECS[transport_type_id].cargo,
            resource_order=_SUPPLY_RESOURCE_ORDER,
        )

    def _update_supply_routes(self, *, elapsed_seconds: float) -> None:
        for route_id in list(sorted(self._supply_routes)):
            route = self._supply_routes.get(route_id)
            if route is None:
                continue

            unit = self._find_unit_by_id(route.unit_id)
            if unit is None:
                self._supply_routes.pop(route_id, None)
                continue

            self._refresh_supply_route(route, elapsed_seconds=elapsed_seconds)

    def _refresh_supply_route_targets(self) -> None:
        for route in self._supply_routes.values():
            self._refresh_supply_route(route)

    def _refresh_supply_route(self, route: SupplyRouteState, *, elapsed_seconds: float = 0.0) -> None:
        self._supply_route_manager.refresh_route(
            route,
            elapsed_seconds=elapsed_seconds,
            find_unit_by_id=self._find_unit_by_id,
            dispatch_points=self._supply_dispatch_points(),
            receive_points=self._supply_receive_points(),
            object_target_point=self._object_target_point,
            positions_match=self._positions_match,
            set_unit_target=lambda unit, target: self._set_unit_target(unit, target, road_mode="only"),
            unit_supply_capacity=self._unit_supply_capacity,
            unit_load_seconds=self._unit_supply_load_seconds,
            unit_unload_seconds=self._unit_supply_unload_seconds,
        )

    def _refresh_route_pickup(self, route: SupplyRouteState, unit: UnitState) -> None:
        self._supply_route_manager.refresh_route_pickup(
            route,
            unit,
            dispatch_points=self._supply_dispatch_points(),
            receive_points=self._supply_receive_points(),
            object_target_point=self._object_target_point,
            positions_match=self._positions_match,
            set_unit_target=lambda active_unit, target: self._set_unit_target(active_unit, target, road_mode="only"),
            unit_supply_capacity=self._unit_supply_capacity,
            unit_load_seconds=self._unit_supply_load_seconds,
        )

    def _refresh_route_delivery(self, route: SupplyRouteState, unit: UnitState) -> None:
        self._supply_route_manager.refresh_route_delivery(
            route,
            unit,
            receive_points=self._supply_receive_points(),
            object_target_point=self._object_target_point,
            positions_match=self._positions_match,
            set_unit_target=lambda active_unit, target: self._set_unit_target(active_unit, target, road_mode="only"),
            unit_unload_seconds=self._unit_supply_unload_seconds,
        )

    def _refresh_transport_geometry(self, landing_pad: LandingPadState) -> None:
        destination = self._map_object_center(landing_pad.object_id)
        landing_pad.refresh_transport_geometry(
            destination_position=destination,
            origin_position=self._transport_origin_for_destination(destination),
        )

    def _movement_pixels_per_tick(self, unit_type_id: str) -> float:  # pragma: no mutate
        width, _height = self._map_size
        return self._navigation_service.movement_pixels_per_tick(
            unit_type_id,
            map_width_px=width,
            base_speed_kmph=lambda active_unit_type_id: UNIT_TYPE_SPECS[active_unit_type_id].speed_kmph,
        )

    def _unit_movement_pixels_per_tick(self, unit: UnitState) -> float:
        width, _height = self._map_size
        return self._navigation_service.unit_movement_pixels_per_tick(
            unit,
            map_width_px=width,
            unit_speed_kmph=self._unit_speed_kmph,
        )

    def _pixels_per_tick_from_speed_kmph(self, speed_kmph: float) -> float:
        width, _height = self._map_size
        return self._navigation_service.pixels_per_tick_from_speed_kmph(
            speed_kmph,
            map_width_px=width,
        )

    def _unit_armament_key(self, unit: UnitState) -> str:
        if unit.equipment.primary_weapon_key:
            return unit.equipment.primary_weapon_key
        return UNIT_TYPE_SPECS[unit.unit_type_id].armament_key

    def _unit_speed_kmph(self, unit: UnitState) -> float:
        return UNIT_TYPE_SPECS[unit.unit_type_id].speed_kmph + self._unit_vehicle_speed_bonus_kmph(unit)

    def _unit_attack(self, unit: UnitState) -> int:
        return UNIT_TYPE_SPECS[unit.unit_type_id].attack + self._unit_vehicle_attack_bonus(unit)

    def _unit_defense(self, unit: UnitState) -> int:
        return UNIT_TYPE_SPECS[unit.unit_type_id].defense + self._unit_vehicle_defense_bonus(unit)

    def _unit_vehicle_speed_bonus_kmph(self, unit: UnitState) -> float:
        return sum(
            VEHICLE_TYPE_SPECS.get(vehicle.vehicle_type_id, VehicleTypeSpec(type_id="")).transport_speed_bonus_kmph
            * max(0, int(vehicle.count))
            for vehicle in unit.vehicles
        )

    def _unit_vehicle_attack_bonus(self, unit: UnitState) -> int:
        return sum(
            VEHICLE_TYPE_SPECS.get(vehicle.vehicle_type_id, VehicleTypeSpec(type_id="")).attack_bonus
            * max(0, int(vehicle.count))
            for vehicle in unit.vehicles
        )

    def _unit_vehicle_defense_bonus(self, unit: UnitState) -> int:
        return sum(
            VEHICLE_TYPE_SPECS.get(vehicle.vehicle_type_id, VehicleTypeSpec(type_id="")).defense_bonus
            * max(0, int(vehicle.count))
            for vehicle in unit.vehicles
        )

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

    def _remove_enemy_group_by_id(self, group_id: str) -> None:
        self._enemy_groups = [
            enemy_group for enemy_group in self._enemy_groups if enemy_group.group_id != group_id
        ]

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
        return unit.bounds(marker_size_px=UNIT_TYPE_SPECS[unit.unit_type_id].marker_size_px)

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
        return empty_resource_store()

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

    def _supply_route_endpoints(self) -> dict[str, SupplyRouteEndpoint]:
        endpoints: dict[str, SupplyRouteEndpoint] = {}
        for object_id, landing_pad in self._landing_pads.items():
            endpoints[object_id] = SupplyRouteEndpoint(
                object_id=object_id,
                location_type="landing_pad",
                can_dispatch_supplies=True,
                can_receive_supplies=False,
                is_active=self._is_landing_pad_secured(landing_pad),
            )
        for object_id in self._bases:
            endpoints[object_id] = SupplyRouteEndpoint(
                object_id=object_id,
                location_type="base",
                can_dispatch_supplies=False,
                can_receive_supplies=True,
                is_active=True,
            )
        return endpoints

    def _supply_dispatch_points(self) -> Mapping[str, SupplyDispatchPoint]:
        return dict(self._landing_pads)

    def _supply_receive_points(self) -> Mapping[str, SupplyReceivePoint]:
        return dict(self._bases)

    def _is_landing_pad_secured(self, landing_pad: LandingPadState) -> bool:
        return landing_pad.is_secured(self._objective_status)

    def _landing_pad_total_stored(self, landing_pad: LandingPadState) -> int:
        return landing_pad.total_stored(resource_order=_SUPPLY_RESOURCE_ORDER)

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
        return UNIT_TYPE_SPECS[unit_type_id].can_transport_supplies

    def _unit_supply_capacity(self, unit_type_id: str) -> int:
        return UNIT_TYPE_SPECS[unit_type_id].supply_capacity

    def _unit_supply_load_seconds(self, unit_type_id: str) -> float:
        return UNIT_TYPE_SPECS[unit_type_id].supply_load_seconds

    def _unit_supply_unload_seconds(self, unit_type_id: str) -> float:
        return UNIT_TYPE_SPECS[unit_type_id].supply_unload_seconds

    def _supply_route_id_for_unit(self, unit_id: str) -> str | None:
        return self._supply_route_manager.route_id_for_unit(unit_id)

    def _unit_has_supply_route(self, unit_id: str) -> bool:
        return self._supply_route_manager.unit_has_route(unit_id)

    def _clear_supply_route_for_unit(self, unit_id: str) -> None:  # pragma: no mutate
        self._supply_route_manager.clear_route_for_unit(unit_id)

    def _is_valid_supply_route_pair(  # pragma: no mutate
        self,
        *,
        source_object_id: str,
        destination_object_id: str,
    ) -> bool:
        return self._supply_route_manager.is_valid_route_pair(
            first_object_id=source_object_id,
            second_object_id=destination_object_id,
            endpoints=self._supply_route_endpoints(),
        )

    def _take_resources(self, storage: dict[str, int], amount: int) -> dict[str, int]:  # pragma: no mutate
        pad = LandingPadState(
            object_id="",
            pad_size="small",
            capacity=max(0, self._resource_total(storage)),
            secured_by_objective_id="",
            resources=dict(storage),
        )
        taken = pad.take_resources(amount, resource_order=_SUPPLY_RESOURCE_ORDER)
        storage.clear()
        storage.update(pad.resources)
        return taken

    def _store_resources(  # pragma: no mutate
        self,
        storage: dict[str, int],
        cargo: dict[str, int],
        capacity: int,
    ) -> dict[str, int]:
        base = BaseState(
            object_id="",
            capacity=capacity,
            resources=dict(storage),
        )
        stored = base.store_resources(cargo, resource_order=_SUPPLY_RESOURCE_ORDER)
        storage.clear()
        storage.update(base.resources)
        return stored

    def _subtract_resources(  # pragma: no mutate
        self,
        cargo: dict[str, int],
        delivered: dict[str, int],
    ) -> dict[str, int]:
        unit = UnitState(
            unit_id="",
            unit_type_id="infantry_squad",
            position=(0.0, 0.0),
            carried_resources=dict(cargo),
        )
        unit.subtract_delivered_resources(delivered, resource_order=_SUPPLY_RESOURCE_ORDER)
        return unit.carried_resources

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
        return interpolate_points(start, end, progress)

    def _transport_position_for_progress(  # pragma: no mutate
        self,
        active_transport: SupplyTransportState,
    ) -> tuple[float, float]:
        return active_transport.progress_position()


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
