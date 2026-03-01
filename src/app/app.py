from __future__ import annotations

from src.core.orders import ExitRequested, LoadGameRequested, NewGameRequested, Order
from src.ui.main_menu import create_view
from src.ui.main_menu_view import MainMenuView


def route_order(order: Order) -> bool:
    if isinstance(order, ExitRequested):
        return False

    if isinstance(order, NewGameRequested):
        print("Wybrano: Nowa gra")
        return False

    if isinstance(order, LoadGameRequested):
        print("Wybrano: Wczytaj")
        return False

    return True


def run() -> None:
    view = create_view()
    _run_main_menu_loop(view)


def _run_main_menu_loop(view: MainMenuView) -> None:
    keep_running = True
    try:
        while keep_running:
            view.render()
            orders = view.poll_orders()
            for order in orders:
                keep_running = route_order(order)
                if not keep_running:
                    break
    finally:
        view.close()
