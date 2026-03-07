from __future__ import annotations

from typing import Any

try:
    from contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        ExitRequested,
        LoadGameFlowRouted,
        LoadGameRequested,
        NewGameFlowRouted,
        NewGameRequested,
        UIEvent,
    )
except ModuleNotFoundError:
    from src.contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        ExitRequested,
        LoadGameFlowRouted,
        LoadGameRequested,
        NewGameFlowRouted,
        NewGameRequested,
        UIEvent,
    )


class PygameMainMenuView:
    def __init__(self) -> None:
        import pygame as pygame_module

        self._pygame = pygame_module
        pygame = self._pygame

        pygame.init()
        self._screen = pygame.display.set_mode((720, 420))
        pygame.display.set_caption("Game - Menu glowne")
        self._clock = pygame.time.Clock()
        self._font_title = pygame.font.SysFont("arial", 42, bold=True)
        self._font_menu = pygame.font.SysFont("arial", 30)
        self._font_hint = pygame.font.SysFont("arial", 22)
        self._last_hint: str | None = None
        self._menu_hitboxes: dict[str, Any] = {}
        self._closed = False

    def render(self) -> None:
        pygame = self._pygame

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

        if self._last_hint:
            self._draw_text(self._last_hint, self._font_hint, (255, 120, 120), 380)

        pygame.display.flip()

    def poll_ui_events(self) -> list[UIEvent]:
        pygame = self._pygame
        events: list[UIEvent] = []
        for pygame_event in pygame.event.get():
            if pygame_event.type == pygame.QUIT:
                events.append(ExitRequested())
            elif pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
                for choice, hitbox in self._menu_hitboxes.items():
                    if hitbox.collidepoint(pygame_event.pos):
                        mapped = _map_choice_to_ui_event(choice)
                        if mapped:
                            events.append(mapped)
            elif pygame_event.type == pygame.KEYDOWN:
                if pygame_event.key in (pygame.K_1, pygame.K_KP1):
                    events.append(NewGameRequested())
                elif pygame_event.key in (pygame.K_2, pygame.K_KP2):
                    events.append(LoadGameRequested())
                elif pygame_event.key in (pygame.K_3, pygame.K_KP3, pygame.K_ESCAPE):
                    events.append(ExitRequested())
                else:
                    self._last_hint = "Niepoprawny wybor. Uzyj klawiszy 1, 2, 3 lub ESC."
        self._clock.tick(60)
        return events

    def handle_domain_event(self, event: DomainEvent) -> None:
        if isinstance(event, NewGameFlowRouted):
            self._last_hint = "Szkic: przejscie do nowej gry"
        elif isinstance(event, LoadGameFlowRouted):
            self._last_hint = "Szkic: przejscie do wczytania gry"
        elif isinstance(event, ExitFlowRouted):
            self._last_hint = "Wyjscie z aplikacji"

    def close(self) -> None:
        if not self._closed:
            self._pygame.quit()
            self._closed = True

    def _draw_text(
        self, text: str, font: Any, color: tuple[int, int, int], y: int
    ) -> None:
        surface = font.render(text, True, color)
        x = (self._screen.get_width() - surface.get_width()) // 2
        self._screen.blit(surface, (x, y))

    def _draw_menu_item(self, text: str, y: int) -> Any:
        surface = self._font_menu.render(text, True, (220, 225, 235))
        x = (self._screen.get_width() - surface.get_width()) // 2
        rect = surface.get_rect(topleft=(x, y))
        self._screen.blit(surface, rect.topleft)
        return rect


def _map_choice_to_ui_event(choice: str) -> UIEvent | None:
    if choice == "1":
        return NewGameRequested()
    if choice == "2":
        return LoadGameRequested()
    if choice == "3":
        return ExitRequested()
    return None
