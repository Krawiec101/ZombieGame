from src.app.app import route_order
from src.core.orders import ExitRequested, LoadGameRequested, NewGameRequested


def test_route_order_exit_requested_stops_loop() -> None:
    assert route_order(ExitRequested()) is False


def test_route_order_new_game_requested_stops_menu() -> None:
    assert route_order(NewGameRequested()) is False


def test_route_order_load_game_requested_stops_menu() -> None:
    assert route_order(LoadGameRequested()) is False
