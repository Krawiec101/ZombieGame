from __future__ import annotations

from typing import Any

try:
    from ui.i18n import text
except ModuleNotFoundError:
    from src.ui.i18n import text

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
    "motorized_infantry_squad": ((138, 173, 112), (42, 74, 38)),
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
        self._map_objects: list[dict[str, Any]] = []
        self._units: list[dict[str, Any]] = []
        self._selected_unit_id: str | None = None
        self._mission_objectives: tuple[dict[str, str], ...] = ()
        self._mission_objective_status: dict[str, bool] = {}

    def apply_game_state(
        self,
        *,
        map_objects: tuple[dict[str, object], ...],
        units: tuple[dict[str, object], ...],
        selected_unit_id: str | None,
        objective_definitions: tuple[dict[str, str], ...],
        objective_status: dict[str, bool],
    ) -> None:
        self._map_objects = [dict(map_object) for map_object in map_objects]
        self._units = [dict(unit) for unit in units]
        self._selected_unit_id = selected_unit_id
        self._mission_objectives = tuple(dict(objective) for objective in objective_definitions)
        self._mission_objective_status = dict(objective_status)

    def clear_game_state(self) -> None:
        self._map_objects = []
        self._units = []
        self._selected_unit_id = None
        self._mission_objective_status = {
            objective["objective_id"]: False for objective in self._mission_objectives
        }

    def render(self, *, character_name: str, show_running_hint: bool) -> None:
        _ = (character_name, show_running_hint)
        self._screen.fill((14, 18, 28))
        self._map_rect = self._draw_map_area()
        self._draw_map_objects()
        self._draw_units()
        self._draw_mission_objectives_panel()

        hovered_object = self._find_hovered_map_object()
        if hovered_object is not None:
            keys = _MAP_OBJECT_TEXT_KEYS.get(hovered_object["id"])
            if keys is not None:
                self._draw_object_tooltip(
                    target_rect=self._rect_from_bounds(hovered_object["bounds"]),
                    title=text(keys[0]),
                    description=text(keys[1]),
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
                map_object["id"], ((95, 113, 129), (184, 200, 215))
            )
            object_rect = self._rect_from_bounds(map_object["bounds"])
            pygame.draw.rect(self._screen, fill_color, object_rect, border_radius=8)
            pygame.draw.rect(self._screen, border_color, object_rect, 2, border_radius=8)

    def _draw_units(self) -> None:
        pygame = self._pygame
        for unit in self._units:
            fill_color, border_color = _UNIT_MARKER_STYLES.get(
                unit.get("unit_type_id", ""),
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
            if unit.get("unit_id") == self._selected_unit_id:
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
            objective_id = objective["objective_id"]
            is_completed = self._mission_objective_status.get(objective_id, False)
            checkbox = "[x]" if is_completed else "[ ]"
            label = text(objective["description_key"])
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

    def _get_unit_rect(self, unit: dict[str, Any] | None = None) -> Any:
        pygame = self._pygame
        active_unit = unit if unit is not None else (self._units[0] if self._units else None)
        if active_unit is None:
            return pygame.Rect(0, 0, 18, 18)
        position = active_unit.get("position", (0.0, 0.0))
        size = int(active_unit.get("marker_size_px", 18))
        left = int(float(position[0]) - size / 2)
        top = int(float(position[1]) - size / 2)
        return pygame.Rect(left, top, size, size)

    def _find_hovered_map_object(self) -> dict[str, Any] | None:
        mouse_x, mouse_y = self._get_mouse_position()
        for map_object in self._map_objects:
            if self._point_in_bounds((mouse_x, mouse_y), map_object["bounds"]):
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

    def _draw_object_tooltip(self, *, target_rect: Any, title: str, description: str) -> None:
        pygame = self._pygame
        screen_width, screen_height = self._screen.get_size()
        title_surface = self._font_hint.render(title, True, (236, 241, 246))
        description_surface = self._font_hint.render(description, True, (189, 202, 217))

        padding = 8
        tooltip_width = max(title_surface.get_width(), description_surface.get_width()) + padding * 2
        tooltip_height = title_surface.get_height() + description_surface.get_height() + padding * 3
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
        self._screen.blit(title_surface, (tooltip_rect.left + padding, tooltip_rect.top + padding))
        self._screen.blit(
            description_surface,
            (tooltip_rect.left + padding, tooltip_rect.top + padding * 2 + title_surface.get_height()),
        )
