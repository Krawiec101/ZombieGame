from __future__ import annotations

import pygame

from src.core.orders import ExitRequested, LoadGameRequested, NewGameRequested, Order


class PygameMainMenuView:
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

    def poll_orders(self) -> list[Order]:
        orders: list[Order] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                orders.append(ExitRequested())
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for choice, hitbox in self._menu_hitboxes.items():
                    if hitbox.collidepoint(event.pos):
                        mapped = _map_choice_to_order(choice)
                        if mapped:
                            orders.append(mapped)
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_1, pygame.K_KP1):
                    orders.append(NewGameRequested())
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    orders.append(LoadGameRequested())
                elif event.key in (pygame.K_3, pygame.K_KP3, pygame.K_ESCAPE):
                    orders.append(ExitRequested())
                else:
                    self._last_error = "Niepoprawny wybor. Uzyj klawiszy 1, 2, 3 lub ESC."
        self._clock.tick(60)
        return orders

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


def _map_choice_to_order(choice: str) -> Order | None:
    if choice == "1":
        return NewGameRequested()
    if choice == "2":
        return LoadGameRequested()
    if choice == "3":
        return ExitRequested()
    return None
