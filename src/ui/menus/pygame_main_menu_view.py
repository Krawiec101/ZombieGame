from __future__ import annotations

import time
from typing import Any

from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    GameFrameSyncRequested,
    GameLeftClickRequested,
    GameRightClickRequested,
    GameStateSynced,
    GameSupplyRouteRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
    UIEvent,
)
from ui.game_views.pygame_game_view import PygameGameView
from ui.i18n import text

_MENU_OPTION_LABEL_KEYS = {
    "1": "main_menu.option.new_game",
    "2": "main_menu.option.load_game",
    "3": "main_menu.option.exit",
}
_WINDOWED_FALLBACK_SIZE = (1280, 720)
_MODAL_SHELL_SIZE = (480, 248)
_UNIT_CONTEXT_MENU_HOLD_SECONDS = 1.0
_FRAME_SYNC_MODES = {
    "game",
    "game_report_modal",
    "game_context_menu",
    "game_unit_context_menu",
    "game_supply_route_planning",
}


class PygameMainMenuView:
    def __init__(self) -> None:
        import pygame as pygame_module

        self._pygame = pygame_module
        pygame = self._pygame

        pygame.init()
        self._screen = self._create_screen()
        pygame.display.set_caption(text("app.window.caption"))
        self._clock = pygame.time.Clock()
        self._font_title = pygame.font.SysFont("arial", 42, bold=True)
        self._font_menu = pygame.font.SysFont("arial", 30)
        self._font_hint = pygame.font.SysFont("arial", 22)
        self._game_view = PygameGameView(
            pygame_module=pygame,
            screen=self._screen,
            font_title=self._font_title,
            font_menu=self._font_menu,
            font_hint=self._font_hint,
        )
        self._last_hint: str | None = None
        self._menu_hitboxes: dict[str, Any] = {}
        self._context_menu_hitboxes: dict[str, Any] = {}
        self._unit_context_menu_hitboxes: dict[str, Any] = {}
        self._unit_context_menu_anchor = (0, 0)
        self._right_mouse_hold_started_at: float | None = None
        self._right_mouse_hold_position: tuple[int, int] | None = None
        self._right_mouse_hold_allows_menu = False
        self._modal_ok_hitbox: Any | None = None
        self._mode = "menu"
        self._character_name = ""
        self._character_name_input = ""
        self._planned_supply_route_source_id: str | None = None
        self._mission_report_queue: list[tuple[str, str, str]] = []
        self._dismissed_mission_report_ids: set[str] = set()
        self._active_mission_report: tuple[str, str, str] | None = None
        self._closed = False

    def _create_screen(self) -> Any:
        pygame = self._pygame
        try:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        except Exception:
            return pygame.display.set_mode(_WINDOWED_FALLBACK_SIZE)

    def render(self) -> None:
        if self._mode == "menu":
            self._render_menu()
        else:
            self._render_game()

        if self._mode == "name_modal":
            self._render_name_modal()
        elif self._mode == "welcome_modal":
            self._render_welcome_modal()
        elif self._mode == "game_report_modal":
            self._render_game_report_modal()
        elif self._mode == "game_context_menu":
            self._render_game_context_menu()
        elif self._mode == "game_unit_context_menu":
            self._render_unit_context_menu()

        self._pygame.display.flip()

    def poll_ui_events(self) -> list[UIEvent]:
        pygame = self._pygame
        events: list[UIEvent] = []
        for pygame_event in pygame.event.get():
            if pygame_event.type == pygame.QUIT:
                events.append(ExitRequested())
                continue

            self._dispatch_ui_event(pygame_event, events)

        self._update_mouse_holds()

        if self._should_emit_game_frame_sync():
            width, height = self._screen.get_size()
            events.append(GameFrameSyncRequested(width=width, height=height))

        self._clock.tick(60)
        return events

    def _dispatch_ui_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        handlers = {
            "menu": self._handle_menu_event,
            "name_modal": self._handle_name_modal_event,
            "welcome_modal": self._handle_welcome_modal_event,
            "game_report_modal": self._handle_game_report_modal_input,
            "game": self._handle_game_event,
            "game_context_menu": self._handle_game_context_menu_event,
            "game_unit_context_menu": self._handle_unit_context_menu_event,
            "game_supply_route_planning": self._handle_supply_route_planning_event,
        }
        handler = handlers.get(self._mode)
        if handler is not None:
            handler(pygame_event, events)

    def _handle_game_report_modal_input(self, pygame_event: Any, _events: list[UIEvent]) -> None:
        self._handle_game_report_modal_event(pygame_event)

    def _should_emit_game_frame_sync(self) -> bool:
        return self._mode in _FRAME_SYNC_MODES

    def handle_domain_event(self, event: DomainEvent) -> None:
        if isinstance(event, NewGameFlowRouted):
            self._game_view.clear_game_state()
            self._character_name = ""
            self._character_name_input = ""
            self._modal_ok_hitbox = None
            self._context_menu_hitboxes = {}
            self._unit_context_menu_hitboxes = {}
            self._planned_supply_route_source_id = None
            self._mission_report_queue = []
            self._dismissed_mission_report_ids = set()
            self._active_mission_report = None
            self._clear_right_mouse_hold()
            self._last_hint = None
            self._mode = "name_modal"
        elif isinstance(event, GameStateSynced):
            self._game_view.apply_game_state(snapshot=event.snapshot)
            self._queue_mission_reports(event.snapshot.mission_reports)
            if self._mode == "game_unit_context_menu" and not self._game_view.selected_unit_can_create_supply_route():
                self._close_unit_context_menu()
            if self._mode in {
                "game",
                "game_context_menu",
                "game_unit_context_menu",
                "game_supply_route_planning",
                "game_report_modal",
            }:
                self._open_next_mission_report_if_needed()
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

    def _render_game(self) -> None:
        self._menu_hitboxes = {}
        self._game_view.render(
            character_name=self._character_name,
            show_running_hint=self._mode == "game",
            supply_route_planning=self._supply_route_planning_state(),
        )

    def _render_game_context_menu(self) -> None:
        pygame = self._pygame
        modal_rect = self._draw_modal_shell("")
        self._context_menu_hitboxes = {}
        button_width = modal_rect.width - 120
        button_height = 36
        button_x = modal_rect.left + 60
        buttons = [
            ("resume", text("game.context_menu.option.resume"), (76, 128, 92)),
            ("to_menu", text("game.context_menu.option.main_menu"), (80, 112, 144)),
            ("exit", text("game.context_menu.option.exit_game"), (132, 76, 76)),
        ]
        for index, (action, label, fill_color) in enumerate(buttons):
            y = modal_rect.top + 72 + index * 48
            button_rect = pygame.Rect(button_x, y, button_width, button_height)
            pygame.draw.rect(self._screen, fill_color, button_rect, border_radius=6)
            pygame.draw.rect(self._screen, (128, 138, 158), button_rect, 2, border_radius=6)
            self._draw_text_in_rect(label, self._font_hint, (238, 239, 243), button_rect)
            self._context_menu_hitboxes[action] = button_rect

    def _render_unit_context_menu(self) -> None:
        pygame = self._pygame
        menu_width = 240
        menu_height = 52
        screen_width, screen_height = self._screen.get_size()
        left = min(self._unit_context_menu_anchor[0], max(0, screen_width - menu_width - 8))
        top = min(self._unit_context_menu_anchor[1], max(0, screen_height - menu_height - 8))
        menu_rect = pygame.Rect(left, top, menu_width, menu_height)
        pygame.draw.rect(self._screen, (24, 30, 43), menu_rect, border_radius=8)
        pygame.draw.rect(self._screen, (112, 124, 146), menu_rect, 2, border_radius=8)

        button_rect = pygame.Rect(menu_rect.left + 8, menu_rect.top + 8, menu_rect.width - 16, 36)
        pygame.draw.rect(self._screen, (96, 124, 84), button_rect, border_radius=6)
        pygame.draw.rect(self._screen, (196, 218, 174), button_rect, 2, border_radius=6)
        self._draw_text_in_rect(
            text("game.supply_route.menu.create"),
            self._font_hint,
            (243, 245, 238),
            button_rect,
        )
        self._unit_context_menu_hitboxes = {"create_supply_route": button_rect}

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

    def _render_game_report_modal(self) -> None:
        if self._active_mission_report is None:
            return

        pygame = self._pygame
        _report_id, title_key, message_key = self._active_mission_report
        modal_rect = self._draw_modal_shell(text(title_key))
        content_rect = pygame.Rect(
            modal_rect.left + 28,
            modal_rect.top + 66,
            modal_rect.width - 56,
            modal_rect.height - 132,
        )
        self._draw_wrapped_text(
            text(message_key),
            self._font_hint,
            (214, 224, 238),
            content_rect,
        )

        ok_rect = pygame.Rect(modal_rect.centerx - 62, modal_rect.bottom - 58, 124, 38)
        pygame.draw.rect(self._screen, (76, 128, 92), ok_rect, border_radius=6)
        pygame.draw.rect(self._screen, (128, 138, 158), ok_rect, 2, border_radius=6)
        self._draw_text_in_rect(text("modal.button.ok"), self._font_hint, (238, 239, 243), ok_rect)
        self._modal_ok_hitbox = ok_rect

    def _draw_modal_shell(self, title: str) -> Any:
        pygame = self._pygame
        overlay = pygame.Surface(self._screen.get_size(), pygame.SRCALPHA)
        overlay.fill((5, 8, 14, 176))
        self._screen.blit(overlay, (0, 0))

        modal_width, modal_height = _MODAL_SHELL_SIZE
        screen_width, screen_height = self._screen.get_size()
        modal_left = max(0, (screen_width - modal_width) // 2)
        modal_top = max(0, (screen_height - modal_height) // 2)
        modal_rect = pygame.Rect(modal_left, modal_top, modal_width, modal_height)
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
        if pygame_event.type == pygame.MOUSEBUTTONDOWN:
            if pygame_event.button == 1:
                events.append(GameLeftClickRequested(position=pygame_event.pos))
                return
            if pygame_event.button == 3:
                self._begin_right_mouse_hold(pygame_event.pos)
                return

        if pygame_event.type == getattr(pygame, "MOUSEBUTTONUP", object()):
            if pygame_event.button == 3:
                if self._right_mouse_hold_position is not None:
                    events.append(GameRightClickRequested(position=self._right_mouse_hold_position))
                self._clear_right_mouse_hold()
                return

        if pygame_event.type == pygame.KEYDOWN and pygame_event.key == pygame.K_ESCAPE:
            self._clear_right_mouse_hold()
            self._open_game_context_menu()

    def _handle_game_context_menu_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
            for action, hitbox in self._context_menu_hitboxes.items():
                if hitbox.collidepoint(pygame_event.pos):
                    self._handle_context_menu_action(action, events)
                    break
            return

        if pygame_event.type != pygame.KEYDOWN:
            return

        if pygame_event.key == pygame.K_ESCAPE:
            self._close_game_context_menu()
            return

        if pygame_event.key in (pygame.K_1, pygame.K_KP1):
            self._handle_context_menu_action("resume", events)
            return

        if pygame_event.key in (pygame.K_2, pygame.K_KP2):
            self._handle_context_menu_action("to_menu", events)
            return

        if pygame_event.key in (pygame.K_3, pygame.K_KP3):
            self._handle_context_menu_action("exit", events)

    def _handle_unit_context_menu_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN:
            if pygame_event.button == 1:
                for action, hitbox in self._unit_context_menu_hitboxes.items():
                    if hitbox.collidepoint(pygame_event.pos):
                        if action == "create_supply_route":
                            self._begin_supply_route_planning()
                        return
                self._close_unit_context_menu()
                return

            if pygame_event.button == 3:
                self._close_unit_context_menu()
                return

        if pygame_event.type != pygame.KEYDOWN:
            return

        if pygame_event.key == pygame.K_ESCAPE:
            self._close_unit_context_menu()
            return

        if pygame_event.key in (pygame.K_1, pygame.K_KP1):
            self._begin_supply_route_planning()

    def _handle_supply_route_planning_event(self, pygame_event: Any, events: list[UIEvent]) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN:
            if pygame_event.button == 3:
                self._cancel_supply_route_planning()
                return

            if pygame_event.button != 1:
                return

            clicked_object = self._game_view.map_object_at(pygame_event.pos)
            if clicked_object is None:
                return

            if self._planned_supply_route_source_id is None:
                if clicked_object.object_id in self._game_view.supply_route_source_candidates():
                    self._planned_supply_route_source_id = clicked_object.object_id
                return

            if clicked_object.object_id in self._game_view.supply_route_destination_candidates(
                source_object_id=self._planned_supply_route_source_id,
            ):
                events.append(
                    GameSupplyRouteRequested(
                        source_object_id=self._planned_supply_route_source_id,
                        destination_object_id=clicked_object.object_id,
                    )
                )
                self._cancel_supply_route_planning()
                return

        if pygame_event.type == pygame.KEYDOWN and pygame_event.key == pygame.K_ESCAPE:
            self._cancel_supply_route_planning()

    def _handle_context_menu_action(self, action: str, events: list[UIEvent]) -> None:
        if action == "resume":
            self._close_game_context_menu()
        elif action == "to_menu":
            self._return_to_main_menu()
        elif action == "exit":
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

    def _handle_game_report_modal_event(self, pygame_event: Any) -> None:
        pygame = self._pygame
        if pygame_event.type == pygame.MOUSEBUTTONDOWN and pygame_event.button == 1:
            if self._modal_ok_hitbox and self._modal_ok_hitbox.collidepoint(pygame_event.pos):
                self._dismiss_active_mission_report()
            return

        if pygame_event.type != pygame.KEYDOWN:
            return

        if pygame_event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
            self._dismiss_active_mission_report()

    def _confirm_character_name(self) -> None:
        if not self._has_valid_character_name():
            return

        self._character_name = self._character_name_input.strip()
        self._modal_ok_hitbox = None
        self._mode = "welcome_modal"

    def _enter_game(self) -> None:
        self._modal_ok_hitbox = None
        self._context_menu_hitboxes = {}
        self._unit_context_menu_hitboxes = {}
        self._planned_supply_route_source_id = None
        self._clear_right_mouse_hold()
        self._mode = "game"
        self._open_next_mission_report_if_needed()

    def _open_game_context_menu(self) -> None:
        self._unit_context_menu_hitboxes = {}
        self._planned_supply_route_source_id = None
        self._clear_right_mouse_hold()
        self._context_menu_hitboxes = {}
        self._mode = "game_context_menu"

    def _close_game_context_menu(self) -> None:
        self._context_menu_hitboxes = {}
        self._mode = "game"

    def _open_unit_context_menu(self, position: tuple[int, int]) -> None:
        self._context_menu_hitboxes = {}
        self._unit_context_menu_anchor = position
        self._unit_context_menu_hitboxes = {}
        self._clear_right_mouse_hold()
        self._mode = "game_unit_context_menu"

    def _close_unit_context_menu(self) -> None:
        self._unit_context_menu_hitboxes = {}
        self._mode = "game"

    def _begin_supply_route_planning(self) -> None:
        self._unit_context_menu_hitboxes = {}
        self._planned_supply_route_source_id = None
        self._clear_right_mouse_hold()
        self._mode = "game_supply_route_planning"

    def _cancel_supply_route_planning(self) -> None:
        self._planned_supply_route_source_id = None
        self._clear_right_mouse_hold()
        self._mode = "game"

    def _return_to_main_menu(self) -> None:
        self._context_menu_hitboxes = {}
        self._unit_context_menu_hitboxes = {}
        self._modal_ok_hitbox = None
        self._planned_supply_route_source_id = None
        self._active_mission_report = None
        self._clear_right_mouse_hold()
        self._mode = "menu"

    def _queue_mission_reports(self, reports: tuple[Any, ...]) -> None:
        for report in reports:
            report_id = getattr(report, "report_id", "")
            if not report_id or report_id in self._dismissed_mission_report_ids:
                continue
            queued_ids = {item[0] for item in self._mission_report_queue}
            if self._active_mission_report is not None:
                queued_ids.add(self._active_mission_report[0])
            if report_id in queued_ids:
                continue
            self._mission_report_queue.append((report_id, report.title_key, report.message_key))

    def _open_next_mission_report_if_needed(self) -> None:
        if self._active_mission_report is not None or not self._mission_report_queue:
            return
        self._active_mission_report = self._mission_report_queue.pop(0)
        self._modal_ok_hitbox = None
        self._context_menu_hitboxes = {}
        self._unit_context_menu_hitboxes = {}
        self._planned_supply_route_source_id = None
        self._clear_right_mouse_hold()
        self._mode = "game_report_modal"

    def _dismiss_active_mission_report(self) -> None:
        if self._active_mission_report is not None:
            self._dismissed_mission_report_ids.add(self._active_mission_report[0])
        self._active_mission_report = None
        self._modal_ok_hitbox = None
        self._mode = "game"
        self._open_next_mission_report_if_needed()

    def _supply_route_planning_state(self) -> dict[str, Any] | None:
        if self._mode != "game_supply_route_planning":
            return None

        if self._planned_supply_route_source_id is None:
            return {
                "candidate_ids": self._game_view.supply_route_source_candidates(),
                "instruction_key": "game.supply_route.planning.pickup",
                "chosen_source_id": None,
            }

        return {
            "candidate_ids": self._game_view.supply_route_destination_candidates(
                source_object_id=self._planned_supply_route_source_id,
            ),
            "instruction_key": "game.supply_route.planning.dropoff",
            "chosen_source_id": self._planned_supply_route_source_id,
        }

    def _has_valid_character_name(self) -> bool:
        return bool(self._character_name_input.strip())

    def _begin_right_mouse_hold(self, position: tuple[int, int]) -> None:
        self._right_mouse_hold_started_at = time.monotonic()
        self._right_mouse_hold_position = position
        self._right_mouse_hold_allows_menu = (
            self._game_view.selected_unit_can_create_supply_route()
            and self._game_view.selected_unit_contains_point(position)
        )

    def _clear_right_mouse_hold(self) -> None:
        self._right_mouse_hold_started_at = None
        self._right_mouse_hold_position = None
        self._right_mouse_hold_allows_menu = False

    def _update_mouse_holds(self) -> None:
        if self._mode != "game":
            return
        if self._right_mouse_hold_started_at is None or self._right_mouse_hold_position is None:
            return
        if not self._right_mouse_hold_allows_menu:
            return
        if not self._game_view.selected_unit_contains_point(self._right_mouse_hold_position):
            self._clear_right_mouse_hold()
            return
        if (time.monotonic() - self._right_mouse_hold_started_at) < _UNIT_CONTEXT_MENU_HOLD_SECONDS:
            return
        self._open_unit_context_menu(self._right_mouse_hold_position)

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

    def _draw_wrapped_text(
        self,
        text: str,
        font: Any,
        color: tuple[int, int, int],
        content_rect: Any,
        line_spacing: int = 2,
    ) -> None:
        words = text.split()
        if not words:
            return

        line_height = font.get_linesize()
        x = content_rect.left
        y = content_rect.top
        word_index = 0
        while word_index < len(words) and y + line_height <= content_rect.bottom:
            line = words[word_index]
            next_index = word_index + 1
            while next_index < len(words):
                candidate = f"{line} {words[next_index]}"
                if font.size(candidate)[0] > content_rect.width:
                    break
                line = candidate
                next_index += 1

            self._draw_text_at(line, font, color, x, y)
            word_index = next_index
            y += line_height + line_spacing

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
