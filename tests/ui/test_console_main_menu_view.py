import pytest

from src.core.orders import ExitRequested, LoadGameRequested, NewGameRequested
from src.ui.console_main_menu_view import map_choice_to_order


@pytest.mark.parametrize(
    ("raw", "expected_type"),
    [
        ("1", NewGameRequested),
        ("2", LoadGameRequested),
        ("3", ExitRequested),
    ],
)
def test_map_choice_to_order_returns_expected_order(raw: str, expected_type: type) -> None:
    order = map_choice_to_order(raw)

    assert isinstance(order, expected_type)


@pytest.mark.parametrize("raw", ["", "0", "4", "x", " "])
def test_map_choice_to_order_returns_none_for_invalid_input(raw: str) -> None:
    assert map_choice_to_order(raw) is None
