from __future__ import annotations

from ui.menus.input_helpers import (
    game_context_menu_action_from_key,
    hitbox_action_at,
    resolve_name_modal_input,
    should_dismiss_modal_from_click,
    should_dismiss_report_modal,
)


class _FakePygame:
    K_ESCAPE = 1
    K_1 = 2
    K_KP1 = 3
    K_2 = 4
    K_KP2 = 5
    K_3 = 6
    K_KP3 = 7
    K_RETURN = 8
    K_KP_ENTER = 9
    K_BACKSPACE = 10


class _Hitbox:
    def __init__(self, should_hit: bool) -> None:
        self._should_hit = should_hit

    def collidepoint(self, _position: tuple[int, int]) -> bool:
        return self._should_hit


def test_hitbox_action_at_returns_first_matching_action() -> None:
    assert hitbox_action_at({"resume": _Hitbox(False), "exit": _Hitbox(True)}, (5, 5)) == "exit"
    assert hitbox_action_at({"resume": _Hitbox(False)}, (5, 5)) is None


def test_game_context_menu_action_from_key_maps_shortcuts() -> None:
    assert game_context_menu_action_from_key(_FakePygame, _FakePygame.K_ESCAPE) == "resume"
    assert game_context_menu_action_from_key(_FakePygame, _FakePygame.K_2) == "to_menu"
    assert game_context_menu_action_from_key(_FakePygame, _FakePygame.K_KP3) == "exit"
    assert game_context_menu_action_from_key(_FakePygame, 999) is None


def test_resolve_name_modal_input_handles_exit_confirm_edit_and_passthrough() -> None:
    assert resolve_name_modal_input(_FakePygame, key=_FakePygame.K_ESCAPE, typed="", current_value="AB").exit_requested
    assert resolve_name_modal_input(_FakePygame, key=_FakePygame.K_RETURN, typed="", current_value="AB").confirm
    assert resolve_name_modal_input(
        _FakePygame,
        key=_FakePygame.K_BACKSPACE,
        typed="",
        current_value="AB",
    ).next_value == "A"
    assert resolve_name_modal_input(_FakePygame, key=999, typed="C", current_value="AB").next_value == "ABC"
    assert resolve_name_modal_input(_FakePygame, key=999, typed="\n", current_value="AB").next_value == "AB"


def test_modal_dismiss_helpers_require_matching_hitbox_or_key() -> None:
    assert should_dismiss_modal_from_click(_Hitbox(True), position=(1, 2)) is True
    assert should_dismiss_modal_from_click(_Hitbox(False), position=(1, 2)) is False
    assert should_dismiss_modal_from_click(None, position=(1, 2)) is False
    assert should_dismiss_report_modal(_FakePygame, key=_FakePygame.K_KP_ENTER) is True
    assert should_dismiss_report_modal(_FakePygame, key=999) is False
