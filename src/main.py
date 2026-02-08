from __future__ import annotations

from src.menu.main.views.main_menu_view import MainMenuView
from src.menu.main.controllers.main_menu_controller import (
    MainMenuController,
    MainMenuEventType,
)

def main() -> None:
    view = MainMenuView()
    controller = MainMenuController(view)

    event = controller.run()

    match event.type:
        case MainMenuEventType.NEW_GAME_REQUESTED:
            print("Wybrano: Nowa gra (jeszcze bez akcji)")
        case MainMenuEventType.LOAD_GAME_REQUESTED:
            print("Wybrano: Wczytaj (jeszcze bez akcji)")
        case MainMenuEventType.EXIT_REQUESTED:
            print("Wybrano: Wyjdź")

if __name__ == "__main__":
    main()