from __future__ import annotations

from typing import Any

try:
    from ui.i18n import text
except ModuleNotFoundError:
    from src.ui.i18n import text


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

    def render(self, *, character_name: str, show_running_hint: bool) -> None:
        _ = show_running_hint
        self._screen.fill((14, 18, 28))
        self._draw_text(text("game.mode.title"), self._font_title, (233, 236, 240), 52)
        if character_name:
            self._draw_text(
                text("game.character.label", character_name=character_name),
                self._font_menu,
                (198, 210, 228),
                150,
            )

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
