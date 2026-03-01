from __future__ import annotations

import pygame

from src.menu.main.views.main_menu_view import MainMenuView


class PygameMainMenuView(MainMenuView):
    def __init__(self) -> None:
        pygame.init()
        self._screen = pygame.display.set_mode((720, 420))
        pygame.display.set_caption("Game - Menu glowne")
        self._clock = pygame.time.Clock()
        self._font_title = pygame.font.SysFont("arial", 42, bold=True)
        self._font_menu = pygame.font.SysFont("arial", 30)
        self._font_hint = pygame.font.SysFont("arial", 22)
        self._last_error: str | None = None
        self._menu_hitboxes: dict[str, pygame.Rect] = {}
        self._closed = False

    def render(self) -> None:
        self._screen.fill((18, 22, 34))
        self._draw_text("MENU GLOWNE", self._font_title, (238, 239, 243), 52)
        self._menu_hitboxes = {
            "1": self._draw_menu_item("1 - Nowa gra", 150),
            "2": self._draw_menu_item("2 - Wczytaj", 195),
            "3": self._draw_menu_item("3 - Wyjdz", 240),
        }
        self._draw_text("ESC - Wyjdz", self._font_hint, (160, 172, 190), 315)
        self._draw_text(
            "Kliknij opcje mysza lub uzyj klawiszy 1-3",
            self._font_hint,
            (160, 172, 190),
            342,
        )

        if self._last_error:
            self._draw_text(self._last_error, self._font_hint, (255, 120, 120), 380)

        pygame.display.flip()

    def read_choice(self) -> str:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "3"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for choice, hitbox in self._menu_hitboxes.items():
                        if hitbox.collidepoint(event.pos):
                            return choice
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        return "1"
                    if event.key in (pygame.K_2, pygame.K_KP2):
                        return "2"
                    if event.key in (pygame.K_3, pygame.K_KP3, pygame.K_ESCAPE):
                        return "3"
                    return "invalid"
            self._clock.tick(60)

    def render_invalid_choice(self) -> None:
        self._last_error = "Niepoprawny wybor. Uzyj klawiszy 1, 2, 3 lub ESC."

    def show_selection_info(self, message: str) -> None:
        while True:
            self._screen.fill((18, 22, 34))
            self._draw_text("WYBRANO", self._font_title, (238, 239, 243), 110)
            self._draw_text(message, self._font_menu, (220, 225, 235), 185)
            self._draw_text(
                "Kliknij, ENTER lub ESC aby zamknac",
                self._font_hint,
                (160, 172, 190),
                290,
            )
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    return
                if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                    pygame.K_ESCAPE,
                ):
                    return
            self._clock.tick(60)

    def close(self) -> None:
        if not self._closed:
            pygame.quit()
            self._closed = True

    def _draw_text(
        self, text: str, font: pygame.font.Font, color: tuple[int, int, int], y: int
    ) -> None:
        surface = font.render(text, True, color)
        x = (self._screen.get_width() - surface.get_width()) // 2
        self._screen.blit(surface, (x, y))

    def _draw_menu_item(self, text: str, y: int) -> pygame.Rect:
        surface = self._font_menu.render(text, True, (220, 225, 235))
        x = (self._screen.get_width() - surface.get_width()) // 2
        rect = surface.get_rect(topleft=(x, y))
        self._screen.blit(surface, rect.topleft)
        return rect
