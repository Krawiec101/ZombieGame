from __future__ import annotations

import math
from typing import Any

try:
    from ui.i18n import text
except ModuleNotFoundError:
    from src.ui.i18n import text

_UNIT_SIZE = 18
_MAP_WIDTH_KM = 20.0
_INFANTRY_SPEED_KMPH = 4.2
_SIMULATION_SECONDS_PER_FRAME = 8.0


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
        self._map_objects: list[dict[str, Any]] = []
        self._map_rect: Any | None = None
        self._unit_selected = False
        self._unit_position = (0.0, 0.0)
        self._unit_target: tuple[float, float] | None = None
        self._unit_initialized = False

    def render(self, *, character_name: str, show_running_hint: bool) -> None:
        _ = (character_name, show_running_hint)
        self._screen.fill((14, 18, 28))
        map_rect = self._draw_map_area()
        self._map_rect = map_rect
        self._map_objects = self._build_map_objects(map_rect)
        if not self._unit_initialized:
            self._initialize_unit_position(self._map_objects)
        self._update_unit_position()
        self._draw_map_objects(self._map_objects)
        self._draw_unit()

        hovered_object = self._find_hovered_map_object(self._map_objects)
        if hovered_object:
            self._draw_object_tooltip(
                target_rect=hovered_object["rect"],
                title=text(hovered_object["name_key"]),
                description=text(hovered_object["description_key"]),
            )

    def handle_left_click(self, position: tuple[int, int]) -> None:
        if self._map_rect is None or not self._unit_initialized:
            return

        if not self._map_rect.collidepoint(position):
            return

        unit_rect = self._get_unit_rect()
        if unit_rect.collidepoint(position):
            self._unit_selected = True
            return

        if not self._unit_selected:
            return

        self._unit_target = self._clamp_point_to_map(position)

    def handle_right_click(self, position: tuple[int, int]) -> None:
        _ = position
        if self._map_rect is None or not self._unit_initialized or not self._unit_selected:
            return
        self._unit_selected = False

    def _draw_text(
        self,
        message: str,
        font: Any,
        color: tuple[int, int, int],
        y: int,
    ) -> None:
        surface = font.render(message, True, color)
        x = (self._screen.get_width() - surface.get_width()) // 2
        self._screen.blit(surface, (x, y))

    def _draw_map_area(self) -> Any:
        pygame = self._pygame
        screen_width, screen_height = self._screen.get_size()
        map_rect = pygame.Rect(0, 0, screen_width, screen_height)

        pygame.draw.rect(self._screen, (23, 38, 45), map_rect, border_radius=10)
        pygame.draw.rect(self._screen, (72, 98, 112), map_rect, 2, border_radius=10)
        return map_rect

    def _build_map_objects(self, map_rect: Any) -> list[dict[str, Any]]:
        return [
            {
                "id": "hq",
                "rect": self._create_map_object_rect(
                    map_rect=map_rect,
                    anchor_x=0.22,
                    anchor_y=0.58,
                    width=84,
                    height=56,
                ),
                "name_key": "game.map.object.hq.name",
                "description_key": "game.map.object.hq.description",
                "fill_color": (76, 116, 158),
            },
            {
                "id": "landing_pad",
                "rect": self._create_map_object_rect(
                    map_rect=map_rect,
                    anchor_x=0.78,
                    anchor_y=0.34,
                    width=72,
                    height=48,
                ),
                "name_key": "game.map.object.landing_pad.name",
                "description_key": "game.map.object.landing_pad.description",
                "fill_color": (124, 146, 88),
            },
        ]

    def _create_map_object_rect(
        self,
        *,
        map_rect: Any,
        anchor_x: float,
        anchor_y: float,
        width: int,
        height: int,
    ) -> Any:
        pygame = self._pygame
        center_x = map_rect.left + int(map_rect.width * anchor_x)
        center_y = map_rect.top + int(map_rect.height * anchor_y)
        return pygame.Rect(center_x - width // 2, center_y - height // 2, width, height)

    def _draw_map_objects(self, map_objects: list[dict[str, Any]]) -> None:
        pygame = self._pygame
        for map_object in map_objects:
            object_rect = map_object["rect"]
            fill_color = map_object["fill_color"]
            pygame.draw.rect(self._screen, fill_color, object_rect, border_radius=8)
            pygame.draw.rect(self._screen, (184, 200, 215), object_rect, 2, border_radius=8)

    def _initialize_unit_position(self, map_objects: list[dict[str, Any]]) -> None:
        hq = next((map_object for map_object in map_objects if map_object["id"] == "hq"), None)
        if hq is None:
            return

        hq_rect = hq["rect"]
        self._unit_position = (
            float(hq_rect.left + hq_rect.width // 2),
            float(hq_rect.top + hq_rect.height // 2),
        )
        self._unit_initialized = True

    def _draw_unit(self) -> None:
        pygame = self._pygame
        unit_rect = self._get_unit_rect()
        unit_fill = (226, 202, 114) if self._unit_selected else (208, 186, 104)
        pygame.draw.rect(self._screen, unit_fill, unit_rect, border_radius=5)
        pygame.draw.rect(self._screen, (78, 66, 28), unit_rect, 2, border_radius=5)
        if self._unit_selected:
            selection_rect = pygame.Rect(
                unit_rect.left - 4,
                unit_rect.top - 4,
                unit_rect.width + 8,
                unit_rect.height + 8,
            )
            pygame.draw.rect(self._screen, (234, 224, 170), selection_rect, 2, border_radius=7)

    def _get_unit_rect(self) -> Any:
        pygame = self._pygame
        unit_left = int(self._unit_position[0] - _UNIT_SIZE / 2)
        unit_top = int(self._unit_position[1] - _UNIT_SIZE / 2)
        return pygame.Rect(unit_left, unit_top, _UNIT_SIZE, _UNIT_SIZE)

    def _update_unit_position(self) -> None:
        if self._unit_target is None:
            return

        pixels_per_frame = self._movement_pixels_per_frame()
        if pixels_per_frame <= 0:
            return

        current_x, current_y = self._unit_position
        target_x, target_y = self._unit_target
        delta_x = target_x - current_x
        delta_y = target_y - current_y
        distance = math.hypot(delta_x, delta_y)

        if distance <= pixels_per_frame:
            self._unit_position = self._unit_target
            self._unit_target = None
            return

        step = pixels_per_frame / distance
        moved_x = current_x + delta_x * step
        moved_y = current_y + delta_y * step
        self._unit_position = self._clamp_point_to_map((moved_x, moved_y))

    def _movement_pixels_per_frame(self) -> float:
        if self._map_rect is None or self._map_rect.width <= 0:
            return 0.0

        km_per_frame = (_INFANTRY_SPEED_KMPH / 3600.0) * _SIMULATION_SECONDS_PER_FRAME
        km_per_pixel = _MAP_WIDTH_KM / float(self._map_rect.width)
        if km_per_pixel <= 0:
            return 0.0
        return km_per_frame / km_per_pixel

    def _clamp_point_to_map(self, position: tuple[float, float] | tuple[int, int]) -> tuple[float, float]:
        if self._map_rect is None:
            return (float(position[0]), float(position[1]))

        half_size = _UNIT_SIZE / 2
        min_x = self._map_rect.left + half_size
        max_x = self._map_rect.right - half_size
        min_y = self._map_rect.top + half_size
        max_y = self._map_rect.bottom - half_size
        clamped_x = min(max(float(position[0]), min_x), max_x)
        clamped_y = min(max(float(position[1]), min_y), max_y)
        return (clamped_x, clamped_y)

    def _find_hovered_map_object(self, map_objects: list[dict[str, Any]]) -> dict[str, Any] | None:
        mouse_x, mouse_y = self._get_mouse_position()
        for map_object in map_objects:
            if map_object["rect"].collidepoint((mouse_x, mouse_y)):
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
