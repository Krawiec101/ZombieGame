from __future__ import annotations

from src.menu.main.controllers.main_menu_controller import (
    MainMenuController,
    MainMenuEventType,
)
from src.menu.main.views.main_menu_view import MainMenuView
from src.menu.main.views.pygame_main_menu_view import PygameMainMenuView


def _create_view() -> MainMenuView:
    try:
        return PygameMainMenuView()
    except Exception:
        return MainMenuView()


def main() -> None:
    view = _create_view()
    try:
        controller = MainMenuController(view)
        event = controller.run()

        match event.type:
            case MainMenuEventType.NEW_GAME_REQUESTED:
                view.show_selection_info("Wybrano: Nowa gra")
            case MainMenuEventType.LOAD_GAME_REQUESTED:
                view.show_selection_info("Wybrano: Wczytaj")
            case MainMenuEventType.EXIT_REQUESTED:
                view.show_selection_info("Wybrano: Wyjdz")
    finally:
        view.close()


if __name__ == "__main__":
    main()
