from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.game_state import (
    GameStateSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    UnitSnapshot,
)
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
        self.line_calls = 0

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


def _sample_game_state(*, objective_completed: bool = False) -> GameStateSnapshot:
    return GameStateSnapshot(
        map_objects=(
            MapObjectSnapshot(object_id="hq", bounds=(160, 200, 244, 256)),
            MapObjectSnapshot(object_id="landing_pad", bounds=(700, 170, 772, 218)),
        ),
        units=(
            UnitSnapshot(
                unit_id="alpha_infantry",
                unit_type_id="infantry_squad",
                position=(210.0, 238.0),
                target=None,
                marker_size_px=18,
            ),
            UnitSnapshot(
                unit_id="bravo_motorized",
                unit_type_id="motorized_infantry_squad",
                position=(250.0, 238.0),
                target=None,
                marker_size_px=20,
            ),
        ),
        selected_unit_id="alpha_infantry",
        objective_definitions=(
            MissionObjectiveDefinitionSnapshot(
                objective_id="motorized_to_landing_pad",
                description_key="mission.objective.motorized_to_landing_pad",
            ),
        ),
        objective_progress=(
            MissionObjectiveProgressSnapshot(
                objective_id="motorized_to_landing_pad",
                completed=objective_completed,
            ),
        ),
    )


def _blitted_texts(screen: _FakeScreen) -> list[str]:
    return [surface._text for surface, _position in screen.blit_calls if hasattr(surface, "_text")]


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


def test_render_uses_fullscreen_map_area(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)

    map_rects = [rect for color, rect in game_view.pygame.draw.rect_calls if color == (23, 38, 45)]
    assert map_rects
    map_rect = map_rects[0]
    assert map_rect.left == 0
    assert map_rect.top == 0
    assert map_rect.width == 960
    assert map_rect.height == 640


def test_apply_game_state_updates_cached_state(game_view) -> None:
    state = _sample_game_state()

    game_view.view.apply_game_state(snapshot=state)

    assert {obj.object_id for obj in game_view.view._map_objects} == {"hq", "landing_pad"}
    assert {unit.unit_type_id for unit in game_view.view._units} == {
        "infantry_squad",
        "motorized_infantry_squad",
    }
    assert game_view.view._selected_unit_id == "alpha_infantry"


def test_render_draws_mission_objectives_panel(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "mission.objectives.title" in texts
    assert "[ ] mission.objective.motorized_to_landing_pad" in texts


def test_render_draws_strikethrough_for_completed_objective(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(objective_completed=True))
    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "[x] mission.objective.motorized_to_landing_pad" in texts
    assert game_view.pygame.draw.line_calls >= 1


def test_render_shows_tooltip_for_hovered_object(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (170, 210)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" in texts
    assert "game.map.object.hq.description" in texts


def test_render_hides_tooltip_when_mouse_is_outside_objects(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (8, 8)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" not in texts
    assert "game.map.object.hq.description" not in texts


def test_clear_game_state_clears_cached_state(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    assert game_view.view._map_objects

    game_view.view.clear_game_state()

    assert game_view.view._map_objects == []
    assert game_view.view._units == []
    assert game_view.view._selected_unit_id is None
