from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import ui.game_views.pygame_game_view as game_view_module


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

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return self.left <= x <= self.right and self.top <= y <= self.bottom


class _FakeFontSurface:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_width(self) -> int:
        return max(8, len(self._text) * 8)

    def get_height(self) -> int:
        return 20


class _FakeFont:
    def render(self, text: str, _antialias: bool, _color: tuple[int, int, int]) -> _FakeFontSurface:
        return _FakeFontSurface(text)


class _FakeScreen:
    def __init__(self) -> None:
        self.fill_calls: list[tuple[int, int, int]] = []
        self.blit_calls: list[tuple[object, tuple[int, int]]] = []

    def fill(self, color: tuple[int, int, int]) -> None:
        self.fill_calls.append(color)

    def blit(self, surface: object, position: tuple[int, int]) -> None:
        self.blit_calls.append((surface, position))

    def get_width(self) -> int:
        return 960

    def get_size(self) -> tuple[int, int]:
        return (960, 640)


class _FakeDraw:
    def __init__(self) -> None:
        self.rect_calls: list[tuple[tuple[int, int, int], _FakeRect]] = []

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


class _FakeMouse:
    def __init__(self) -> None:
        self.position = (0, 0)

    def get_pos(self) -> tuple[int, int]:
        return self.position


class _FakePygame:
    def __init__(self) -> None:
        self.draw = _FakeDraw()
        self.mouse = _FakeMouse()

    def Rect(self, left: int, top: int, width: int, height: int) -> _FakeRect:
        return _FakeRect(left, top, width, height)


def _blitted_texts(screen: _FakeScreen) -> list[str]:
    return [
        surface._text
        for surface, _position in screen.blit_calls
        if hasattr(surface, "_text")
    ]


def _unit_by_id(view: game_view_module.PygameGameView, unit_id: str):
    return next(unit for unit in view._units if unit.unit_id == unit_id)


def _unit_by_type(view: game_view_module.PygameGameView, unit_type_id: str):
    return next(unit for unit in view._units if unit.unit_type.type_id == unit_type_id)


@pytest.fixture
def game_view(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(game_view_module, "text", lambda key, **kwargs: key)
    fake_pygame = _FakePygame()
    fake_screen = _FakeScreen()
    view = game_view_module.PygameGameView(
        pygame_module=fake_pygame,
        screen=fake_screen,
        font_title=_FakeFont(),
        font_menu=_FakeFont(),
        font_hint=_FakeFont(),
    )
    return SimpleNamespace(view=view, pygame=fake_pygame, screen=fake_screen)


def test_render_builds_two_map_objects(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)

    object_ids = {map_object["id"] for map_object in game_view.view._map_objects}
    assert object_ids == {"hq", "landing_pad"}


def test_render_initializes_two_unit_classes(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)

    unit_type_ids = {unit.unit_type.type_id for unit in game_view.view._units}
    assert unit_type_ids == {"infantry_squad", "motorized_infantry_squad"}


def test_render_uses_fullscreen_map_area(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)

    map_rects = [rect for color, rect in game_view.pygame.draw.rect_calls if color == (23, 38, 45)]
    assert map_rects
    map_rect = map_rects[0]
    assert map_rect.left == 0
    assert map_rect.top == 0
    assert map_rect.width == 960
    assert map_rect.height == 640


def test_render_hides_game_mode_title(game_view) -> None:
    game_view.view.render(character_name="Kowalski", show_running_hint=True)

    assert "game.mode.title" not in _blitted_texts(game_view.screen)


def test_render_shows_tooltip_for_hovered_object(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    hq = next(map_object for map_object in game_view.view._map_objects if map_object["id"] == "hq")
    game_view.pygame.mouse.position = (hq["rect"].left + 2, hq["rect"].top + 2)
    game_view.screen.blit_calls.clear()

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" in texts
    assert "game.map.object.hq.description" in texts


def test_render_hides_tooltip_when_mouse_is_outside_objects(game_view) -> None:
    game_view.pygame.mouse.position = (8, 8)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" not in texts
    assert "game.map.object.hq.description" not in texts
    assert "game.map.object.landing_pad.name" not in texts
    assert "game.map.object.landing_pad.description" not in texts


def test_left_click_selects_unit(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    unit = _unit_by_id(game_view.view, "alpha_infantry")
    unit_rect = game_view.view._get_unit_rect(unit)
    click_pos = (unit_rect.left + 2, unit_rect.top + 2)

    game_view.view.handle_left_click(click_pos)
    assert game_view.view._selected_unit_id == unit.unit_id

    other_unit = _unit_by_id(game_view.view, "bravo_motorized")
    other_rect = game_view.view._get_unit_rect(other_unit)
    game_view.view.handle_left_click((other_rect.left + 2, other_rect.top + 2))
    assert game_view.view._selected_unit_id == other_unit.unit_id


def test_left_click_on_empty_map_issues_move_order_when_selected(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    unit = _unit_by_id(game_view.view, "alpha_infantry")
    unit_rect = game_view.view._get_unit_rect(unit)
    game_view.view.handle_left_click((unit_rect.left + 2, unit_rect.top + 2))
    assert game_view.view._selected_unit_id == unit.unit_id

    target = (840, 500)
    expected_target = game_view.view._clamp_point_to_map(target, unit=unit)
    game_view.view.handle_left_click(target)

    assert game_view.view._selected_unit_id == unit.unit_id
    assert unit.target == expected_target


def test_right_click_deselects_selected_unit_without_clearing_target(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    unit = _unit_by_id(game_view.view, "alpha_infantry")
    unit_rect = game_view.view._get_unit_rect(unit)
    game_view.view.handle_left_click((unit_rect.left + 2, unit_rect.top + 2))
    game_view.view.handle_left_click((840, 500))
    target_before_deselect = unit.target
    assert target_before_deselect is not None

    game_view.view.handle_right_click((840, 500))

    assert game_view.view._selected_unit_id is None
    assert unit.target == target_before_deselect

    for _ in range(3000):
        game_view.view.render(character_name="", show_running_hint=False)
        if unit.target is None:
            break

    assert unit.target is None


def test_left_click_without_selection_does_not_issue_move_order(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    unit = _unit_by_id(game_view.view, "alpha_infantry")
    start_position = unit.position

    game_view.view.handle_left_click((840, 500))
    for _ in range(60):
        game_view.view.render(character_name="", show_running_hint=False)

    assert unit.target is None
    assert unit.position == start_position


def test_left_click_move_order_reaches_target(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    unit = _unit_by_id(game_view.view, "alpha_infantry")
    unit_rect = game_view.view._get_unit_rect(unit)
    game_view.view.handle_left_click((unit_rect.left + 2, unit_rect.top + 2))

    target = (840, 500)
    expected_target = game_view.view._clamp_point_to_map(target, unit=unit)
    game_view.view.handle_left_click(target)

    for _ in range(3000):
        game_view.view.render(character_name="", show_running_hint=False)
        if unit.target is None:
            break

    assert unit.target is None
    assert unit.position == expected_target


def test_left_click_move_order_uses_strategic_speed_profile(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)
    infantry = _unit_by_type(game_view.view, "infantry_squad")
    motorized = _unit_by_type(game_view.view, "motorized_infantry_squad")

    infantry_rect = game_view.view._get_unit_rect(infantry)
    motorized_rect = game_view.view._get_unit_rect(motorized)
    target = (40, 40)

    game_view.view.handle_left_click((infantry_rect.left + 2, infantry_rect.top + 2))
    game_view.view.handle_left_click(target)
    game_view.view.handle_left_click((motorized_rect.left + 2, motorized_rect.top + 2))
    game_view.view.handle_left_click(target)

    infantry_start_position = infantry.position
    motorized_start_position = motorized.position

    for _ in range(120):
        game_view.view.render(character_name="", show_running_hint=False)

    infantry_moved_distance = math.hypot(
        infantry.position[0] - infantry_start_position[0],
        infantry.position[1] - infantry_start_position[1],
    )
    motorized_moved_distance = math.hypot(
        motorized.position[0] - motorized_start_position[0],
        motorized.position[1] - motorized_start_position[1],
    )

    assert infantry_moved_distance < 100.0
    assert motorized_moved_distance > infantry_moved_distance * 2
