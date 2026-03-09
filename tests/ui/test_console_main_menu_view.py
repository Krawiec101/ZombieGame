import pytest

from contracts.events import ExitRequested, LoadGameRequested, NewGameRequested
from ui.menus.console_main_menu_view import map_choice_to_ui_event


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ("1", NewGameRequested),
        ("2", LoadGameRequested),
        ("3", ExitRequested),
    ],
)
def test_map_choice_to_order_returns_expected_order(raw: str, expected_type: type) -> None:
    order = map_choice_to_ui_event(raw)

    assert isinstance(order, expected_type)


@pytest.mark.parametrize("raw", ["", "0", "4", "x", " "])
def test_map_choice_to_order_returns_none_for_invalid_input(raw: str) -> None:
    assert map_choice_to_ui_event(raw) is None
