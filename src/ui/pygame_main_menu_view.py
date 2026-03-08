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
    from ui.i18n import text
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
    from src.ui.i18n import text


_MENU_OPTION_LABEL_KEYS = {
    "1": "main_menu.option.new_game",
    "2": "main_menu.option.load_game",
    "3": "main_menu.option.exit",
}


class PygameMainMenuView:
    def __init__(self) -> None:
        import pygame as pygame_module

        self._pygame = pygame_module
        pygame = self._pygame

        pygame.init()
        self._screen = pygame.display.set_mode((720, 420))
        pygame.display.set_caption(text("app.window.caption"))
        self._clock = pygame.time.Clock()
        self._font_title = pygame.font.SysFont("arial", 42, bold=True)
        self._font_menu = pygame.font.SysFont("arial", 30)
        self._font_hint = pygame.font.SysFont("arial", 22)
        self._last_hint: str | None = None
        self._menu_hitboxes: dict[str, Any] = {}
        self._modal_ok_hitbox: Any | None = None
        self._mode = "menu"
        self._character_name = ""
        self._character_name_input = ""
        self._closed = False

    def render(self) -> None:
        if self._mode == "menu":
            self._render_menu()
        else:
            self._render_game()

        if self._mode == "name_modal":
            self._render_name_modal()
        elif self._mode == "welcome_modal":
            self._render_welcome_modal()

        self._pygame.display.flip()

    def poll_ui_events(self) -> list[UIEvent]:
        pygame = self._pygame
        events: list[UIEvent] = []
        for pygame_event in pygame.event.get():
            if pygame_event.type == pygame.QUIT:
                events.append(ExitRequested())
                continue

            if self._mode == "menu":
                self._handle_menu_event(pygame_event, events)
            elif self._mode == "name_modal":
                self._handle_name_modal_event(pygame_event, events)
            elif self._mode == "welcome_modal":
                self._handle_welcome_modal_event(pygame_event, events)
            elif self._mode == "game":
                self._handle_game_event(pygame_event, events)

        self._clock.tick(60)
        return events

    def handle_domain_event(self, event: DomainEvent) -> None:
        if isinstance(event, NewGameFlowRouted):
            self._character_name = ""
            self._character_name_input = ""
            self._modal_ok_hitbox = None
            self._last_hint = None
            self._mode = "name_modal"
        elif isinstance(event, LoadGameFlowRouted):
            self._last_hint = text("flow.load_game.stub")
        elif isinstance(event, ExitFlowRouted):
            self._last_hint = text("flow.exit")

    def close(self) -> None:
        if not self._closed:
            self._pygame.quit()
            self._closed = True

    def _render_menu(self) -> None:
        self._screen.fill((18, 22, 34))
        self._draw_text(text("main_menu.title"), self._font_title, (238, 239, 243), 52)
        self._menu_hitboxes = {
            "1": self._draw_menu_item(
                text(
                    "pygame.menu.option",
                    choice="1",
                    label=text(_MENU_OPTION_LABEL_KEYS["1"]),
                ),
                150,
            ),
            "2": self._draw_menu_item(
                text(
                    "pygame.menu.option",
                    choice="2",
                    label=text(_MENU_OPTION_LABEL_KEYS["2"]),
                ),
                195,
            ),
            "3": self._draw_menu_item(
                text(
                    "pygame.menu.option",
                    choice="3",
                    label=text(_MENU_OPTION_LABEL_KEYS["3"]),
                ),
                240,
            ),
        }
        self._draw_text(text("main_menu.hint.esc_exit"), self._font_hint, (160, 172, 190), 315)
        self._draw_text(
            text("main_menu.hint.mouse_or_keys"),
            self._font_hint,
            (160, 172, 190),
            342,
        )
        if self._last_hint:
            self._draw_text(self._last_hint, self._font_hint, (255, 120, 120), 380)

    def _render_game(self) -> None:
        self._screen.fill((14, 18, 28))
        self._menu_hitboxes = {}
        self._draw_text(text("game.mode.title"), self._font_title, (233, 236, 240), 52)
        if self._character_name:
            self._draw_text(
                text("game.character.label", character_name=self._character_name),
                self._font_menu,
                (198, 210, 228),
                150,
            )
        if self._mode == "game":
            self._draw_text(
                text("game.hint.running"),
                self._font_hint,
                (160, 172, 190),
                315,
            )

    def _render_name_modal(self) -> None:
        pygame = self._pygame
        modal_rect = self._draw_modal_shell(text("modal.new_character.title"))
        self._draw_text_at(
            text("modal.new_character.prompt"),
            self._font_hint,
            (220, 225, 235),
            modal_rect.left + 36,
            modal_rect.top + 70,
        )

        input_rect = pygame.Rect(
            modal_rect.left + 36,
            modal_rect.top + 105,
            modal_rect.width - 72,
            48,
        )
        pygame.draw.rect(self._screen, (40, 48, 66), input_rect, border_radius=6)
        pygame.draw.rect(self._screen, (88, 102, 128), input_rect, 2, border_radius=6)

        typed_name = self._character_name_input
        text_color = (225, 231, 240) if typed_name else (126, 138, 158)
        visible_text = typed_name or text("modal.new_character.placeholder")
        self._draw_text_at(
            visible_text,
            self._font_menu,
            text_color,
            input_rect.left + 12,
            input_rect.top + 8,
        )

        ok_rect = pygame.Rect(modal_rect.centerx - 62, modal_rect.bottom - 58, 124, 38)
        enabled = self._has_valid_character_name()
        button_color = (73, 126, 91) if enabled else (74, 78, 92)
        pygame.draw.rect(self._screen, button_color, ok_rect, border_radius=6)
        pygame.draw.rect(self._screen, (128, 138, 158), ok_rect, 2, border_radius=6)
        self._draw_text_in_rect(text("modal.button.ok"), self._font_hint, (238, 239, 243), ok_rect)
        self._modal_ok_hitbox = ok_rect

        self._draw_text(
            text("modal.new_character.confirm_hint"),
            self._font_hint,
            (160, 172, 190),
            modal_rect.bottom - 18,
        )

    def _render_welcome_modal(self) -> None:
        pygame = self._pygame
        modal_rect = self._draw_modal_shell("")
        top_bar_height = max(24, modal_rect.height * 12 // 100)
        top_bar_rect = pygame.Rect(
            modal_rect.left + 2,
            modal_rect.top + 2,
            modal_rect.width - 4,
            top_bar_height,
        )
        pygame.draw.rect(self._screen, (34, 42, 59), top_bar_rect, border_radius=8)
        pygame.draw.line(
            self._screen,
            (84, 98, 124),
            (modal_rect.left + 12, top_bar_rect.bottom),
            (modal_rect.right - 12, top_bar_rect.bottom),
            1,
        )
        bottom_bar_height = max(44, modal_rect.height * 18 // 100)
        bottom_bar_rect = pygame.Rect(
            modal_rect.left + 2,
            modal_rect.bottom - bottom_bar_height - 2,
            modal_rect.width - 4,
            bottom_bar_height,
        )
        pygame.draw.rect(self._screen, (34, 42, 59), bottom_bar_rect, border_radius=8)
        pygame.draw.line(
            self._screen,
            (84, 98, 124),
            (modal_rect.left + 12, bottom_bar_rect.top),
            (modal_rect.right - 12, bottom_bar_rect.top),
            1,
        )

        content_rect = pygame.Rect(
            modal_rect.left + 24,
            top_bar_rect.bottom + 12,
            modal_rect.width - 48,
            bottom_bar_rect.top - (top_bar_rect.bottom + 12) - 10,
        )

        portrait_rect = pygame.Rect(
            content_rect.left + 6,
            content_rect.top + 2,
            92,
            92,
        )
        pygame.draw.rect(self._screen, (36, 46, 64), portrait_rect, border_radius=8)
        pygame.draw.rect(self._screen, (96, 114, 144), portrait_rect, 2, border_radius=8)
        pygame.draw.circle(
            self._screen,
            (162, 176, 200),
            (portrait_rect.centerx, portrait_rect.top + 31),
            14,
            2,
        )
        pygame.draw.rect(
            self._screen,
            (162, 176, 200),
            pygame.Rect(portrait_rect.centerx - 20, portrait_rect.top + 52, 40, 24),
            2,
            border_radius=12,
        )
        self._draw_wrapped_text_around_rect(
            text("modal.welcome.message", character_name=self._character_name),
            self._font_hint,
            (214, 224, 238),
            content_rect,
            portrait_rect,
        )

        ok_rect = pygame.Rect(
            modal_rect.centerx - 62,
            bottom_bar_rect.top + (bottom_bar_rect.height - 38) // 2,
            124,
            38,
        )
        pygame.draw.rect(self._screen, (76, 128, 92), ok_rect, border_radius=6)
        pygame.draw.rect(self._screen, (128, 138, 158), ok_rect, 2, border_radius=6)
        self._draw_text_in_rect(text("modal.button.ok"), self._font_hint, (238, 239, 243), ok_rect)
        self._modal_ok_hitbox = ok_rect

    def _draw_modal_shell(self, title: str) -> Any:
        pygame = self._pygame
        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((5, 8, 14, 176))
        self._screen.blit(overlay, (0, 0))

        modal_rect = pygame.Rect(120, 88, 480, 248)
        pygame.draw.rect(self._screen, (24, 30, 43), modal_rect, border_radius=10)
        pygame.draw.rect(self._screen, (97, 112, 138), modal_rect, 2, border_radius=10)
        if title:
            self._draw_text(title, self._font_menu, (235, 238, 242), modal_rect.top + 26)
        return modal_rect

    def _handle_menu_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
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
                self._last_hint = text("main_menu.hint.invalid_choice_keys")

    def _handle_game_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.KEYDOWN and pygame_event.key == pygame.K_ESCAPE:
            events.append(ExitRequested())

    def _handle_name_modal_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
            if self._modal_ok_hitbox and self._modal_ok_hitbox.collidepoint(pygame_event.pos):
                self._confirm_character_name()
            return

        if pygame_event.type != pygame.KEYDOWN:
            return

        if pygame_event.key == pygame.K_ESCAPE:
            events.append(ExitRequested())
            return

        if pygame_event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._confirm_character_name()
            return

        if pygame_event.key == pygame.K_BACKSPACE:
            self._character_name_input = self._character_name_input[:-1]
            return

        typed = pygame_event.unicode
        if typed and typed.isprintable():
            self._character_name_input = (self._character_name_input + typed)[:24]

    def _handle_welcome_modal_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
            if self._modal_ok_hitbox and self._modal_ok_hitbox.collidepoint(pygame_event.pos):
                self._enter_game()
            return

        if pygame_event.type != pygame.KEYDOWN:
            return

        if pygame_event.key == pygame.K_ESCAPE:
            events.append(ExitRequested())
            return

        if pygame_event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._enter_game()

    def _confirm_character_name(self) -> None:
        if not self._has_valid_character_name():
            return

        self._character_name = self._character_name_input.strip()
        self._modal_ok_hitbox = None
        self._mode = "welcome_modal"

    def _enter_game(self) -> None:
        self._modal_ok_hitbox = None
        self._mode = "game"

    def _has_valid_character_name(self) -> bool:
        return bool(self._character_name_input.strip())

    def _draw_text(
        self, text: str, font: Any, color: tuple[int, int, int], y: int
    ) -> None:
        surface = font.render(text, True, color)
        x = (self._screen.get_width() - surface.get_width()) // 2
        self._screen.blit(surface, (x, y))

    def _draw_text_at(
        self, text: str, font: Any, color: tuple[int, int, int], x: int, y: int
    ) -> None:
        surface = font.render(text, True, color)
        self._screen.blit(surface, (x, y))

    def _draw_text_in_rect(
        self, text: str, font: Any, color: tuple[int, int, int], rect: Any
    ) -> None:
        surface = font.render(text, True, color)
        x = rect.left + (rect.width - surface.get_width()) // 2
        y = rect.top + (rect.height - surface.get_height()) // 2
        self._screen.blit(surface, (x, y))

    def _draw_wrapped_text_around_rect(
        self,
        text: str,
        font: Any,
        color: tuple[int, int, int],
        content_rect: Any,
        obstacle_rect: Any,
        line_spacing: int = 2,
        obstacle_padding: int = 16,
    ) -> None:
        words = text.split()
        if not words:
            return

        y = content_rect.top
        word_index = 0
        line_height = font.get_linesize()
        while word_index < len(words) and y + line_height <= content_rect.bottom:
            overlaps_obstacle = (
                y < obstacle_rect.bottom and y + line_height > obstacle_rect.top
            )
            if overlaps_obstacle:
                line_x = obstacle_rect.right + obstacle_padding
                available_width = content_rect.right - line_x
            else:
                line_x = content_rect.left
                available_width = content_rect.width

            if available_width <= font.size("WW")[0]:
                if overlaps_obstacle:
                    y = obstacle_rect.bottom + line_spacing
                    continue
                break

            line = words[word_index]
            next_index = word_index + 1
            while next_index < len(words):
                candidate = f"{line} {words[next_index]}"
                if font.size(candidate)[0] > available_width:
                    break
                line = candidate
                next_index += 1

            self._draw_text_at(line, font, color, line_x, y)
            word_index = next_index
            y += line_height + line_spacing

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
