from __future__ import annotations

from typing import Any

from contracts.game_state import (
    BaseSnapshot,
    GameStateSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    UnitSnapshot,
)
from ui.i18n import text

_MAP_OBJECT_STYLES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "hq": ((76, 116, 158), (184, 200, 215)),
    "landing_pad": ((124, 146, 88), (184, 200, 215)),
}
_MAP_OBJECT_TEXT_KEYS: dict[str, tuple[str, str]] = {
    "hq": ("game.map.object.hq.name", "game.map.object.hq.description"),
    "landing_pad": ("game.map.object.landing_pad.name", "game.map.object.landing_pad.description"),
}
_UNIT_MARKER_STYLES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "infantry_squad": ((208, 186, 104), (78, 66, 28)),
    "mechanized_squad": ((138, 173, 112), (42, 74, 38)),
}
_SUPPLY_TRANSPORT_STYLES: dict[str, dict[str, Any]] = {
    "light_supply_helicopter": {
        "fill": (167, 196, 142),
        "border": (54, 82, 44),
        "size": (30, 12),
    },
    "heavy_supply_helicopter": {
        "fill": (164, 178, 194),
        "border": (56, 68, 82),
        "size": (38, 14),
    },
}
_SUPPLY_CONVOY_UNIT_TYPE_ID = "mechanized_squad"
_LANDING_PAD_SIZE_TEXT_KEYS = {
    "small": "game.map.object.landing_pad.size.small",
    "large": "game.map.object.landing_pad.size.large",
}
_RESOURCE_TEXT_KEYS = {
    "fuel": "resource.fuel",
    "mre": "resource.mre",
    "ammo": "resource.ammo",
}
_TRANSPORT_TYPE_TEXT_KEYS = {
    "light_supply_helicopter": "game.transport.type.light_supply_helicopter",
    "heavy_supply_helicopter": "game.transport.type.heavy_supply_helicopter",
}


class PygameGameView:
    def __init__(
        self,
        *,
        pygame_module: Any,
        screen: Any,
        font_title: Any,
        font_menu: Any,
        font_hint: Any,
    ) -> None:
        self._pygame = pygame_module
        self._screen = screen
        self._font_title = font_title
        self._font_menu = font_menu
        self._font_hint = font_hint
        self._map_rect: Any | None = None
        self._map_objects: list[MapObjectSnapshot] = []
        self._bases: dict[str, BaseSnapshot] = {}
        self._landing_pads: dict[str, LandingPadSnapshot] = {}
        self._supply_routes: list[SupplyRouteSnapshot] = []
        self._supply_transports: list[SupplyTransportSnapshot] = []
        self._units: list[UnitSnapshot] = []
        self._selected_unit_id: str | None = None
        self._mission_objectives: tuple[MissionObjectiveDefinitionSnapshot, ...] = ()
        self._mission_objective_status: dict[str, bool] = {}

    def apply_game_state(self, *, snapshot: GameStateSnapshot) -> None:
        self._map_objects = list(snapshot.map_objects)
        self._bases = {base.object_id: base for base in snapshot.bases}
        self._landing_pads = {landing_pad.object_id: landing_pad for landing_pad in snapshot.landing_pads}
        self._supply_routes = list(snapshot.supply_routes)
        self._supply_transports = list(snapshot.supply_transports)
        self._units = list(snapshot.units)
        self._selected_unit_id = snapshot.selected_unit_id
        self._mission_objectives = snapshot.objective_definitions
        self._mission_objective_status = {
            objective_progress.objective_id: objective_progress.completed
            for objective_progress in snapshot.objective_progress
        }

    def clear_game_state(self) -> None:
        self._map_objects = []
        self._bases = {}
        self._landing_pads = {}
        self._supply_routes = []
        self._supply_transports = []
        self._units = []
        self._selected_unit_id = None
        self._mission_objective_status = {
            objective.objective_id: False for objective in self._mission_objectives
        }

    def render(
        self,
        *,
        character_name: str,
        show_running_hint: bool,
        supply_route_planning: dict[str, Any] | None = None,
    ) -> None:
        _ = (character_name, show_running_hint)
        self._screen.fill((14, 18, 28))
        self._map_rect = self._draw_map_area()
        self._draw_map_objects()
        self._draw_supply_routes()
        self._draw_supply_transports()
        self._draw_units()
        self._draw_mission_objectives_panel()

        if supply_route_planning is not None:
            self._draw_supply_route_planning_overlay(supply_route_planning)
            return

        hovered_object = self._find_hovered_map_object()
        if hovered_object is not None:
            tooltip = self._tooltip_content_for_map_object(hovered_object)
            if tooltip is not None:
                self._draw_object_tooltip(
                    target_rect=self._rect_from_bounds(hovered_object.bounds),
                    title=tooltip["title"],
                    description=tooltip["description"],
                    detail_lines=tooltip["detail_lines"],
                )

    def _draw_map_area(self) -> Any:
        pygame = self._pygame
        screen_width, screen_height = self._screen.get_size()
        map_rect = pygame.Rect(0, 0, screen_width, screen_height)
        pygame.draw.rect(self._screen, (23, 38, 45), map_rect, border_radius=10)
        pygame.draw.rect(self._screen, (72, 98, 112), map_rect, 2, border_radius=10)
        return map_rect

    def _draw_map_objects(self) -> None:
        pygame = self._pygame
        for map_object in self._map_objects:
            fill_color, border_color = _MAP_OBJECT_STYLES.get(
                map_object.object_id, ((95, 113, 129), (184, 200, 215))
            )
            object_rect = self._rect_from_bounds(map_object.bounds)
            pygame.draw.rect(self._screen, fill_color, object_rect, border_radius=8)
            pygame.draw.rect(self._screen, border_color, object_rect, 2, border_radius=8)

    def _draw_supply_routes(self) -> None:
        pygame = self._pygame
        for route in self._supply_routes:
            start = self._map_object_center(route.source_object_id)
            end = self._map_object_center(route.destination_object_id)
            pygame.draw.line(
                self._screen,
                (216, 182, 104),
                (int(start[0]), int(start[1])),
                (int(end[0]), int(end[1])),
                4,
            )
            pygame.draw.circle(self._screen, (252, 231, 172), (int(start[0]), int(start[1])), 6)
            pygame.draw.circle(self._screen, (252, 231, 172), (int(end[0]), int(end[1])), 6)

            label = self._font_hint.render(
                text(
                    "game.supply_route.label",
                    carried=route.carried_total,
                    capacity=route.capacity,
                ),
                True,
                (245, 236, 205),
            )
            mid_x = int((start[0] + end[0]) / 2.0 - label.get_width() / 2)
            mid_y = int((start[1] + end[1]) / 2.0 - 24)
            self._screen.blit(label, (mid_x, mid_y))

    def _draw_supply_transports(self) -> None:
        pygame = self._pygame
        for supply_transport in self._supply_transports:
            style = _SUPPLY_TRANSPORT_STYLES.get(
                supply_transport.transport_type_id,
                {"fill": (188, 192, 198), "border": (72, 78, 90), "size": (30, 12)},
            )
            body_rect = self._transport_rect(
                supply_transport=supply_transport,
                width=style["size"][0],
                height=style["size"][1],
            )
            pygame.draw.rect(self._screen, style["fill"], body_rect, border_radius=6)
            pygame.draw.rect(self._screen, style["border"], body_rect, 2, border_radius=6)
            rotor_y = body_rect.top - 4
            center_x = body_rect.left + body_rect.width // 2
            pygame.draw.line(
                self._screen,
                style["border"],
                (body_rect.left - 4, rotor_y),
                (body_rect.right + 4, rotor_y),
                2,
            )
            pygame.draw.line(
                self._screen,
                style["border"],
                (center_x, rotor_y),
                (center_x, body_rect.bottom + 2),
                1,
            )
            pygame.draw.line(
                self._screen,
                style["border"],
                (body_rect.left + 3, body_rect.bottom + 2),
                (body_rect.right - 3, body_rect.bottom + 2),
                1,
            )

    def _draw_units(self) -> None:
        pygame = self._pygame
        for unit in self._units:
            fill_color, border_color = _UNIT_MARKER_STYLES.get(
                unit.unit_type_id,
                ((180, 180, 180), (72, 72, 72)),
            )
            unit_rect = self._get_unit_rect(unit)
            pygame.draw.rect(self._screen, fill_color, unit_rect, border_radius=5)
            selection_rect = pygame.Rect(
                unit_rect.left - 1,
                unit_rect.top - 1,
                unit_rect.width + 2,
                unit_rect.height + 2,
            )
            pygame.draw.rect(self._screen, border_color, selection_rect, 2, border_radius=6)
            if unit.unit_id == self._selected_unit_id:
                selected_rect = pygame.Rect(
                    unit_rect.left - 5,
                    unit_rect.top - 5,
                    unit_rect.width + 10,
                    unit_rect.height + 10,
                )
                pygame.draw.rect(self._screen, (234, 224, 170), selected_rect, 2, border_radius=8)

    def _draw_mission_objectives_panel(self) -> None:
        if not self._mission_objectives:
            return

        pygame = self._pygame
        title_surface = self._font_hint.render(text("mission.objectives.title"), True, (236, 241, 246))
        line_entries: list[tuple[Any, bool]] = []
        for objective in self._mission_objectives:
            objective_id = objective.objective_id
            is_completed = self._mission_objective_status.get(objective_id, False)
            checkbox = "[x]" if is_completed else "[ ]"
            label = text(objective.description_key)
            line_color = (142, 150, 160) if is_completed else (212, 222, 232)
            line_entries.append((self._font_hint.render(f"{checkbox} {label}", True, line_color), is_completed))

        padding = 8
        line_gap = 6
        panel_width = title_surface.get_width()
        for surface, _is_completed in line_entries:
            panel_width = max(panel_width, surface.get_width())
        panel_width += padding * 2

        panel_height = padding * 2 + title_surface.get_height()
        if line_entries:
            panel_height += line_gap + sum(surface.get_height() for surface, _is_completed in line_entries)
            panel_height += line_gap * max(0, len(line_entries) - 1)

        panel_rect = pygame.Rect(12, 12, panel_width, panel_height)
        pygame.draw.rect(self._screen, (18, 27, 40), panel_rect, border_radius=6)
        pygame.draw.rect(self._screen, (96, 122, 150), panel_rect, 2, border_radius=6)

        y = panel_rect.top + padding
        self._screen.blit(title_surface, (panel_rect.left + padding, y))
        y += title_surface.get_height() + line_gap
        line_start_x = panel_rect.left + padding
        for surface, is_completed in line_entries:
            self._screen.blit(surface, (line_start_x, y))
            if is_completed:
                strike_y = y + surface.get_height() // 2
                pygame.draw.line(
                    self._screen,
                    (126, 136, 146),
                    (line_start_x, strike_y),
                    (line_start_x + surface.get_width(), strike_y),
                    1,
                )
            y += surface.get_height() + line_gap

    def _get_unit_rect(self, unit: UnitSnapshot | None = None) -> Any:
        pygame = self._pygame
        active_unit = unit if unit is not None else (self._units[0] if self._units else None)
        if active_unit is None:
            return pygame.Rect(0, 0, 18, 18)
        position = active_unit.position
        size = int(active_unit.marker_size_px)
        left = int(float(position[0]) - size / 2)
        top = int(float(position[1]) - size / 2)
        return pygame.Rect(left, top, size, size)

    def selected_unit(self) -> UnitSnapshot | None:
        if self._selected_unit_id is None:
            return None
        return next((unit for unit in self._units if unit.unit_id == self._selected_unit_id), None)

    def selected_unit_can_create_supply_route(self) -> bool:
        selected_unit = self.selected_unit()
        if selected_unit is None:
            return False
        return (
            selected_unit.unit_type_id == _SUPPLY_CONVOY_UNIT_TYPE_ID
            and selected_unit.can_transport_supplies
            and selected_unit.active_supply_route_id is None
        )

    def selected_unit_contains_point(self, position: tuple[int, int]) -> bool:
        selected_unit = self.selected_unit()
        if selected_unit is None:
            return False
        unit_rect = self._get_unit_rect(selected_unit)
        return unit_rect.collidepoint(position)

    def map_object_at(self, position: tuple[int, int]) -> MapObjectSnapshot | None:
        for map_object in self._map_objects:
            if self._point_in_bounds(position, map_object.bounds):
                return map_object
        return None

    def supply_route_source_candidates(self) -> tuple[str, ...]:
        return tuple(sorted(self._landing_pads))

    def supply_route_destination_candidates(self, *, source_object_id: str) -> tuple[str, ...]:
        if source_object_id not in self._landing_pads:
            return ()
        return tuple(sorted(self._bases))

    def _find_hovered_map_object(self) -> MapObjectSnapshot | None:
        mouse_x, mouse_y = self._get_mouse_position()
        for map_object in self._map_objects:
            if self._point_in_bounds((mouse_x, mouse_y), map_object.bounds):
                return map_object
        return None

    def _get_mouse_position(self) -> tuple[int, int]:
        mouse_module = getattr(self._pygame, "mouse", None)
        if mouse_module is None or not hasattr(mouse_module, "get_pos"):
            return (-1, -1)
        position = mouse_module.get_pos()
        if not isinstance(position, (tuple, list)) or len(position) < 2:
            return (-1, -1)
        return (int(position[0]), int(position[1]))

    def _point_in_bounds(self, position: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
        x, y = position
        left, top, right, bottom = bounds
        return left <= x <= right and top <= y <= bottom

    def _rect_from_bounds(self, bounds: tuple[int, int, int, int]) -> Any:
        pygame = self._pygame
        left, top, right, bottom = bounds
        return pygame.Rect(left, top, right - left, bottom - top)

    def _transport_rect(self, *, supply_transport: SupplyTransportSnapshot, width: int, height: int) -> Any:
        pygame = self._pygame
        left = int(float(supply_transport.position[0]) - width / 2)
        top = int(float(supply_transport.position[1]) - height / 2)
        return pygame.Rect(left, top, width, height)

    def _map_object_center(self, object_id: str) -> tuple[float, float]:
        map_object = next((item for item in self._map_objects if item.object_id == object_id), None)
        if map_object is None:
            return (0.0, 0.0)
        left, top, right, bottom = map_object.bounds
        return ((left + right) / 2.0, (top + bottom) / 2.0)

    def _draw_supply_route_planning_overlay(self, planning_state: dict[str, Any]) -> None:
        pygame = self._pygame
        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((7, 11, 18, 138))
        self._screen.blit(overlay, (0, 0))

        candidate_ids = tuple(str(object_id) for object_id in planning_state.get("candidate_ids", ()))
        chosen_source_id = planning_state.get("chosen_source_id")
        instruction_key = str(planning_state.get("instruction_key", "game.supply_route.planning.pickup"))

        for map_object in self._map_objects:
            if map_object.object_id not in candidate_ids:
                continue
            rect = self._rect_from_bounds(map_object.bounds)
            fill_color = (110, 136, 96) if map_object.object_id != chosen_source_id else (168, 134, 74)
            border_color = (232, 220, 172) if map_object.object_id != chosen_source_id else (255, 234, 182)
            pygame.draw.rect(self._screen, fill_color, rect, border_radius=8)
            pygame.draw.rect(self._screen, border_color, rect, 3, border_radius=8)

        instruction_surface = self._font_hint.render(text(instruction_key), True, (241, 236, 220))
        instruction_width = instruction_surface.get_width() + 24
        instruction_rect = pygame.Rect(16, self._screen.get_size()[1] - 56, instruction_width, 36)
        pygame.draw.rect(self._screen, (24, 30, 43), instruction_rect, border_radius=6)
        pygame.draw.rect(self._screen, (118, 126, 144), instruction_rect, 2, border_radius=6)
        self._screen.blit(instruction_surface, (instruction_rect.left + 12, instruction_rect.top + 8))

    def _tooltip_content_for_map_object(self, map_object: MapObjectSnapshot) -> dict[str, Any] | None:
        keys = _MAP_OBJECT_TEXT_KEYS.get(map_object.object_id)
        if keys is None:
            return None

        detail_lines: tuple[str, ...] = ()
        landing_pad = self._landing_pads.get(map_object.object_id)
        if landing_pad is not None:
            detail_lines = self._landing_pad_detail_lines(landing_pad)
        else:
            base = self._bases.get(map_object.object_id)
            if base is not None:
                detail_lines = self._base_detail_lines(base)

        return {
            "title": text(keys[0]),
            "description": text(keys[1]),
            "detail_lines": detail_lines,
        }

    def _base_detail_lines(self, base: BaseSnapshot) -> tuple[str, ...]:
        lines = [
            text("game.map.object.hq.status"),
            text(
                "game.map.object.hq.capacity",
                stored=base.total_stored,
                capacity=base.capacity,
            ),
        ]
        for resource in base.resources:
            lines.append(
                text(
                    "game.map.object.hq.resource_line",
                    label=text(_RESOURCE_TEXT_KEYS.get(resource.resource_id, resource.resource_id)),
                    amount=resource.amount,
                )
            )
        return tuple(lines)

    def _landing_pad_detail_lines(self, landing_pad: LandingPadSnapshot) -> tuple[str, ...]:
        lines = [
            self._landing_pad_status_line(landing_pad),
            text(
                "game.map.object.landing_pad.size",
                size=text(
                    _LANDING_PAD_SIZE_TEXT_KEYS.get(
                        landing_pad.pad_size,
                        "game.map.object.landing_pad.size.small",
                    )
                ),
            ),
            text(
                "game.map.object.landing_pad.capacity",
                stored=landing_pad.total_stored,
                capacity=landing_pad.capacity,
            ),
        ]
        for resource in landing_pad.resources:
            lines.append(
                text(
                    "game.map.object.landing_pad.resource_line",
                    label=text(_RESOURCE_TEXT_KEYS.get(resource.resource_id, resource.resource_id)),
                    amount=resource.amount,
                )
            )
        return tuple(lines)

    def _landing_pad_status_line(self, landing_pad: LandingPadSnapshot) -> str:
        if not landing_pad.is_secured:
            return text("game.map.object.landing_pad.status.unsecured")

        if landing_pad.active_transport_phase == "inbound":
            return text(
                "game.map.object.landing_pad.status.inbound",
                helicopter=self._transport_type_label(landing_pad.active_transport_type_id),
                seconds=landing_pad.active_transport_seconds_remaining or 0,
            )

        if landing_pad.active_transport_phase == "unloading":
            return text(
                "game.map.object.landing_pad.status.unloading",
                helicopter=self._transport_type_label(landing_pad.active_transport_type_id),
                seconds=landing_pad.active_transport_seconds_remaining or 0,
            )

        if landing_pad.active_transport_phase == "outbound":
            return text(
                "game.map.object.landing_pad.status.outbound",
                helicopter=self._transport_type_label(landing_pad.active_transport_type_id),
                seconds=landing_pad.active_transport_seconds_remaining or 0,
            )

        if landing_pad.total_stored >= landing_pad.capacity:
            return text("game.map.object.landing_pad.status.full")

        if landing_pad.next_transport_seconds is not None:
            return text(
                "game.map.object.landing_pad.status.next_transport",
                seconds=landing_pad.next_transport_seconds,
            )

        return text("game.map.object.landing_pad.status.awaiting")

    def _transport_type_label(self, transport_type_id: str | None) -> str:
        if transport_type_id is None:
            return text("game.transport.type.unknown")
        return text(_TRANSPORT_TYPE_TEXT_KEYS.get(transport_type_id, "game.transport.type.unknown"))

    def _draw_object_tooltip(
        self,
        *,
        target_rect: Any,
        title: str,
        description: str,
        detail_lines: tuple[str, ...] = (),
    ) -> None:
        pygame = self._pygame
        screen_width, screen_height = self._screen.get_size()
        title_surface = self._font_hint.render(title, True, (236, 241, 246))
        description_surface = self._font_hint.render(description, True, (189, 202, 217))
        detail_surfaces = [
            self._font_hint.render(line, True, (214, 224, 236))
            for line in detail_lines
        ]

        padding = 8
        line_gap = 4
        tooltip_width = max(
            title_surface.get_width(),
            description_surface.get_width(),
            *(surface.get_width() for surface in detail_surfaces),
        ) + padding * 2
        tooltip_height = padding * 2 + title_surface.get_height() + description_surface.get_height()
        if detail_surfaces:
            tooltip_height += line_gap * (len(detail_surfaces) + 1)
            tooltip_height += sum(surface.get_height() for surface in detail_surfaces)
        else:
            tooltip_height += padding

        tooltip_left = target_rect.right + 12
        tooltip_top = target_rect.top - 6

        if tooltip_left + tooltip_width > screen_width - 12:
            tooltip_left = max(12, target_rect.left - tooltip_width - 12)
        if tooltip_top + tooltip_height > screen_height - 12:
            tooltip_top = max(12, screen_height - tooltip_height - 12)
        if tooltip_top < 12:
            tooltip_top = 12

        tooltip_rect = pygame.Rect(tooltip_left, tooltip_top, tooltip_width, tooltip_height)
        pygame.draw.rect(self._screen, (18, 27, 40), tooltip_rect, border_radius=6)
        pygame.draw.rect(self._screen, (96, 122, 150), tooltip_rect, 2, border_radius=6)

        current_y = tooltip_rect.top + padding
        self._screen.blit(title_surface, (tooltip_rect.left + padding, current_y))
        current_y += title_surface.get_height() + line_gap
        self._screen.blit(description_surface, (tooltip_rect.left + padding, current_y))
        current_y += description_surface.get_height()
        for detail_surface in detail_surfaces:
            current_y += line_gap
            self._screen.blit(detail_surface, (tooltip_rect.left + padding, current_y))
            current_y += detail_surface.get_height()
