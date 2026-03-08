from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

import ui.pygame_main_menu_view as pygame_view_module
from contracts.events import (
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
)


class _FakeClock:
    def __init__(self) -> None:
        self.ticks: list[int] = []

    def tick(self, fps: int) -> None:
        self.ticks.append(fps)


class _FakeTime:
    def __init__(self, clock: _FakeClock) -> None:
        self._clock = clock

    def Clock(self) -> _FakeClock:
        return self._clock


class _FakeDisplay:
    def __init__(self, screen: object) -> None:
        self._screen = screen
        self.caption: str | None = None
        self.flip_calls = 0

    def set_mode(self, _size: tuple[int, int]) -> object:
        return self._screen

    def set_caption(self, caption: str) -> None:
        self.caption = caption

    def flip(self) -> None:
        self.flip_calls += 1


class _FakeFontSurface:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_width(self) -> int:
        return len(self._text) * 8

    def get_height(self) -> int:
        return 20

    def get_rect(self, *, topleft: tuple[int, int]) -> "_FakeRect":
        return _FakeRect(topleft[0], topleft[1], self.get_width(), self.get_height())


class _FakeFont:
    def render(self, text: str, _antialias: bool, _color: tuple[int, int, int]) -> _FakeFontSurface:
        return _FakeFontSurface(text)

    def get_linesize(self) -> int:
        return 20

    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 20)


class _FakeFontModule:
    def SysFont(self, _name: str, _size: int, bold: bool = False) -> _FakeFont:
        _ = bold
        return _FakeFont()


class _FakeEventModule:
    def __init__(self) -> None:
        self.queue: list[SimpleNamespace] = []

    def get(self) -> list[SimpleNamespace]:
        current = list(self.queue)
        self.queue.clear()
        return current


class _FakeRect:
    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def centerx(self) -> int:
        return self.left + self.width // 2

    @property
    def topleft(self) -> tuple[int, int]:
        return (self.left, self.top)

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return self.left <= x <= self.right and self.top <= y <= self.bottom


class _FakeSurface:
    def __init__(self, size: tuple[int, int], flags: int | None = None) -> None:
        self.size = size
        self.flags = flags
        self.fill_calls: list[tuple[int, int, int, int]] = []

    def fill(self, color: tuple[int, int, int, int]) -> None:
        self.fill_calls.append(color)


class _FakeDraw:
    def __init__(self) -> None:
        self.rect_calls: list[tuple[tuple[int, int, int], _FakeRect]] = []
        self.line_calls = 0
        self.circle_calls = 0

    def rect(
        self,
        _screen: object,
        color: tuple[int, int, int],
        rect: _FakeRect,
        _width: int = 0,
        border_radius: int = 0,
    ) -> None:
        _ = border_radius
        self.rect_calls.append((color, rect))

    def line(
        self,
        _screen: object,
        _color: tuple[int, int, int],
        _start_pos: tuple[int, int],
        _end_pos: tuple[int, int],
        _width: int = 1,
    ) -> None:
        self.line_calls += 1

    def circle(
        self,
        _screen: object,
        _color: tuple[int, int, int],
        _center: tuple[int, int],
        _radius: int,
        _width: int = 0,
    ) -> None:
        self.circle_calls += 1


class _FakeScreen:
    def __init__(self) -> None:
        self.fill_calls: list[tuple[int, int, int]] = []
        self.blit_calls: list[tuple[object, object]] = []

    def get_size(self) -> tuple[int, int]:
        return (720, 420)

    def get_width(self) -> int:
        return 720

    def fill(self, color: tuple[int, int, int]) -> None:
        self.fill_calls.append(color)

    def blit(self, surface: object, position: object) -> None:
        self.blit_calls.append((surface, position))


class _FakePygame(ModuleType):
    QUIT = 0
    MOUSEBUTTONDOWN = 1
    KEYDOWN = 2
    K_1 = 11
    K_KP1 = 12
    K_2 = 13
    K_KP2 = 14
    K_3 = 15
    K_KP3 = 16
    K_ESCAPE = 17
    K_RETURN = 18
    K_KP_ENTER = 19
    K_BACKSPACE = 20
    SRCALPHA = 100

    def __init__(self) -> None:
        super().__init__("pygame")
        self._screen = _FakeScreen()
        self._clock = _FakeClock()
        self.time = _FakeTime(self._clock)
        self.event = _FakeEventModule()
        self.display = _FakeDisplay(self._screen)
        self.font = _FakeFontModule()
        self.draw = _FakeDraw()
        self.init_calls = 0
        self.quit_calls = 0
        self.surfaces: list[_FakeSurface] = []

    def init(self) -> None:
        self.init_calls += 1

    def quit(self) -> None:
        self.quit_calls += 1

    def Rect(self, left: int, top: int, width: int, height: int) -> _FakeRect:
        return _FakeRect(left, top, width, height)

    def Surface(self, size: tuple[int, int], flags: int | None = None) -> _FakeSurface:
        surface = _FakeSurface(size, flags)
        self.surfaces.append(surface)
        return surface


class _AlwaysHitbox:
    def collidepoint(self, _pos: tuple[int, int]) -> bool:
        return True


def _event(event_type: int, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(type=event_type, **kwargs)


@pytest.fixture
def pygame_view(monkeypatch: pytest.MonkeyPatch):
    fake_pygame = _FakePygame()
    monkeypatch.setitem(sys.modules, "pygame", fake_pygame)
    monkeypatch.setattr(pygame_view_module, "text", lambda key, **kwargs: key)
    view = pygame_view_module.PygameMainMenuView()
    return view, fake_pygame


@pytest.mark.parametrize(
    ("key", "expected_type"),
    [
        (_FakePygame.K_1, NewGameRequested),
        (_FakePygame.K_KP1, NewGameRequested),
        (_FakePygame.K_2, LoadGameRequested),
        (_FakePygame.K_KP2, LoadGameRequested),
        (_FakePygame.K_3, ExitRequested),
        (_FakePygame.K_KP3, ExitRequested),
        (_FakePygame.K_ESCAPE, ExitRequested),
    ],
)
def test_poll_ui_events_maps_menu_keyboard_shortcuts(
    key: int,
    expected_type: type,
    pygame_view,
) -> None:
    view, fake_pygame = pygame_view
    view._mode = "menu"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=key, unicode="")]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], expected_type)
    assert fake_pygame._clock.ticks == [60]


def test_poll_ui_events_sets_hint_for_unknown_menu_key(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "menu"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=999, unicode="")]

    events = view.poll_ui_events()

    assert events == []
    assert view._last_hint == "main_menu.hint.invalid_choice_keys"


def test_poll_ui_events_maps_menu_mouse_click_to_event(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "menu"
    view._menu_hitboxes = {"1": _AlwaysHitbox()}
    fake_pygame.event.queue = [_event(fake_pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5))]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], NewGameRequested)


def test_poll_ui_events_maps_quit_to_exit_requested(pygame_view) -> None:
    view, fake_pygame = pygame_view
    fake_pygame.event.queue = [_event(fake_pygame.QUIT)]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], ExitRequested)


def test_poll_ui_events_name_modal_typing_and_enter_confirms_character_name(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    fake_pygame.event.queue = [
        _event(fake_pygame.KEYDOWN, key=101, unicode="A"),
        _event(fake_pygame.KEYDOWN, key=102, unicode="l"),
        _event(fake_pygame.KEYDOWN, key=fake_pygame.K_RETURN, unicode=""),
    ]

    events = view.poll_ui_events()

    assert events == []
    assert view._character_name == "Al"
    assert view._mode == "welcome_modal"


def test_poll_ui_events_name_modal_mouse_confirm_uses_ok_hitbox(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    view._character_name_input = "Kowalski"
    view._modal_ok_hitbox = _AlwaysHitbox()
    fake_pygame.event.queue = [_event(fake_pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))]

    events = view.poll_ui_events()

    assert events == []
    assert view._character_name == "Kowalski"
    assert view._mode == "welcome_modal"


def test_poll_ui_events_name_modal_escape_requests_exit(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=fake_pygame.K_ESCAPE, unicode="")]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], ExitRequested)


def test_poll_ui_events_welcome_modal_enter_starts_game_mode(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "welcome_modal"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=fake_pygame.K_RETURN, unicode="")]

    events = view.poll_ui_events()

    assert events == []
    assert view._mode == "game"


def test_poll_ui_events_game_mode_escape_requests_exit(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "game"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=fake_pygame.K_ESCAPE, unicode="")]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], ExitRequested)


def test_handle_domain_event_transitions_and_hints(pygame_view) -> None:
    view, _fake_pygame = pygame_view
    view._character_name = "Old"
    view._character_name_input = "Tmp"
    view._modal_ok_hitbox = _AlwaysHitbox()
    view._last_hint = "old-hint"
    view._mode = "menu"

    view.handle_domain_event(NewGameFlowRouted())

    assert view._character_name == ""
    assert view._character_name_input == ""
    assert view._modal_ok_hitbox is None
    assert view._last_hint is None
    assert view._mode == "name_modal"

    view.handle_domain_event(LoadGameFlowRouted())
    assert view._last_hint == "flow.load_game.stub"

    view.handle_domain_event(ExitFlowRouted())
    assert view._last_hint == "flow.exit"


def test_close_is_idempotent(pygame_view) -> None:
    view, fake_pygame = pygame_view

    view.close()
    view.close()

    assert fake_pygame.quit_calls == 1


def test_render_menu_draws_items_and_hint_and_flips_display(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "menu"
    view._last_hint = "hint-text"

    view.render()

    assert fake_pygame.display.flip_calls == 1
    assert set(view._menu_hitboxes) == {"1", "2", "3"}
    assert fake_pygame._screen.fill_calls[-1] == (18, 22, 34)


def test_render_game_clears_menu_hitboxes_and_draws_game_background(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "game"
    view._character_name = "Ranger"
    view._menu_hitboxes = {"1": _AlwaysHitbox()}

    view.render()

    assert view._menu_hitboxes == {}
    assert fake_pygame.display.flip_calls == 1
    assert fake_pygame._screen.fill_calls[-1] == (14, 18, 28)


def test_render_name_modal_assigns_ok_hitbox_and_draws_overlay(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    view._character_name_input = ""

    view.render()

    assert isinstance(view._modal_ok_hitbox, _FakeRect)
    assert view._modal_ok_hitbox.width == 124
    assert fake_pygame.surfaces
    assert fake_pygame.surfaces[-1].fill_calls[-1] == (5, 8, 14, 176)


def test_render_welcome_modal_draws_frame_and_sets_ok_hitbox(
    pygame_view,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view, fake_pygame = pygame_view
    monkeypatch.setattr(
        pygame_view_module,
        "text",
        lambda key, **kwargs: "witaj nowy bohaterze w swiecie gry"
        if key == "modal.welcome.message"
        else key,
    )
    view._mode = "welcome_modal"
    view._character_name = "Ranger"

    view.render()

    assert isinstance(view._modal_ok_hitbox, _FakeRect)
    assert fake_pygame.draw.line_calls >= 2
    assert fake_pygame.draw.circle_calls >= 1


def test_poll_ui_events_name_modal_backspace_and_non_printable_input(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    view._character_name_input = "AB"
    fake_pygame.event.queue = [
        _event(fake_pygame.KEYDOWN, key=fake_pygame.K_BACKSPACE, unicode=""),
        _event(fake_pygame.KEYDOWN, key=999, unicode="\n"),
        _event(fake_pygame.KEYDOWN, key=998, unicode="C"),
    ]

    events = view.poll_ui_events()

    assert events == []
    assert view._character_name_input == "AC"


def test_poll_ui_events_name_modal_ignores_non_key_non_click_events(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    view._character_name_input = "AB"
    fake_pygame.event.queue = [_event(fake_pygame.MOUSEBUTTONDOWN, button=2, pos=(1, 1))]

    events = view.poll_ui_events()

    assert events == []
    assert view._character_name_input == "AB"


def test_poll_ui_events_name_modal_enter_without_valid_name_keeps_modal(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "name_modal"
    view._character_name_input = "  "
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=fake_pygame.K_RETURN, unicode="")]

    events = view.poll_ui_events()

    assert events == []
    assert view._mode == "name_modal"
    assert view._character_name == ""


def test_poll_ui_events_welcome_modal_click_without_hitbox_keeps_modal(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "welcome_modal"
    view._modal_ok_hitbox = None
    fake_pygame.event.queue = [_event(fake_pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))]

    events = view.poll_ui_events()

    assert events == []
    assert view._mode == "welcome_modal"


def test_poll_ui_events_welcome_modal_ignores_non_key_non_click_events(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "welcome_modal"
    fake_pygame.event.queue = [_event(fake_pygame.MOUSEBUTTONDOWN, button=2, pos=(1, 1))]

    events = view.poll_ui_events()

    assert events == []
    assert view._mode == "welcome_modal"


def test_poll_ui_events_welcome_modal_escape_requests_exit(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "welcome_modal"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=fake_pygame.K_ESCAPE, unicode="")]

    events = view.poll_ui_events()

    assert len(events) == 1
    assert isinstance(events[0], ExitRequested)


def test_poll_ui_events_game_mode_non_escape_key_returns_no_events(pygame_view) -> None:
    view, fake_pygame = pygame_view
    view._mode = "game"
    fake_pygame.event.queue = [_event(fake_pygame.KEYDOWN, key=999, unicode="")]

    events = view.poll_ui_events()

    assert events == []


def test_draw_wrapped_text_around_rect_returns_early_for_empty_text(pygame_view) -> None:
    view, fake_pygame = pygame_view
    calls: list[tuple[str, int, int]] = []

    def capture_draw_text_at(
        text: str,
        _font: _FakeFont,
        _color: tuple[int, int, int],
        x: int,
        y: int,
    ) -> None:
        calls.append((text, x, y))

    view._draw_text_at = capture_draw_text_at
    content_rect = fake_pygame.Rect(0, 0, 160, 80)
    obstacle_rect = fake_pygame.Rect(20, 0, 40, 40)

    view._draw_wrapped_text_around_rect("", view._font_hint, (1, 2, 3), content_rect, obstacle_rect)

    assert calls == []


def test_draw_wrapped_text_around_rect_skips_obstacle_when_line_has_no_space(pygame_view) -> None:
    view, fake_pygame = pygame_view
    calls: list[tuple[str, int, int]] = []

    def capture_draw_text_at(
        text: str,
        _font: _FakeFont,
        _color: tuple[int, int, int],
        x: int,
        y: int,
    ) -> None:
        calls.append((text, x, y))

    view._draw_text_at = capture_draw_text_at
    content_rect = fake_pygame.Rect(0, 0, 120, 70)
    obstacle_rect = fake_pygame.Rect(80, 0, 40, 26)

    view._draw_wrapped_text_around_rect(
        "to jest testowy tekst",
        view._font_hint,
        (1, 2, 3),
        content_rect,
        obstacle_rect,
    )

    assert calls
    assert calls[0][2] >= obstacle_rect.bottom + 2


def test_draw_wrapped_text_around_rect_breaks_when_not_overlapping_and_too_narrow(pygame_view) -> None:
    view, fake_pygame = pygame_view
    calls: list[tuple[str, int, int]] = []

    def capture_draw_text_at(
        text: str,
        _font: _FakeFont,
        _color: tuple[int, int, int],
        x: int,
        y: int,
    ) -> None:
        calls.append((text, x, y))

    view._draw_text_at = capture_draw_text_at
    content_rect = fake_pygame.Rect(0, 40, 10, 20)
    obstacle_rect = fake_pygame.Rect(0, 0, 10, 10)

    view._draw_wrapped_text_around_rect(
        "za wasko",
        view._font_hint,
        (1, 2, 3),
        content_rect,
        obstacle_rect,
    )

    assert calls == []


@pytest.mark.parametrize(
    ("choice", "expected_type"),
    [
        ("1", NewGameRequested),
        ("2", LoadGameRequested),
        ("3", ExitRequested),
    ],
)
def test_map_choice_to_ui_event_returns_expected_event_type(choice: str, expected_type: type) -> None:
    mapped = pygame_view_module._map_choice_to_ui_event(choice)

    assert isinstance(mapped, expected_type)


@pytest.mark.parametrize("choice", ["", "0", "4", "x"])
def test_map_choice_to_ui_event_returns_none_for_invalid_choice(choice: str) -> None:
    assert pygame_view_module._map_choice_to_ui_event(choice) is None
