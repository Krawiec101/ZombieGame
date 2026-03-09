from __future__ import annotations

import os

try:
    from ui.menus.console_main_menu_view import ConsoleMainMenuView
    from contracts.main_menu_view import MainMenuView
except ModuleNotFoundError:
    from src.ui.menus.console_main_menu_view import ConsoleMainMenuView
    from src.contracts.main_menu_view import MainMenuView


_USE_CONSOLE_VALUES = {"1", "true", "yes", "on"}


def create_view() -> MainMenuView:
    if os.getenv("GAME_USE_CONSOLE_MENU", "").strip().lower() in _USE_CONSOLE_VALUES:
        return ConsoleMainMenuView()

    try:
        try:
            from ui.menus.pygame_main_menu_view import PygameMainMenuView
        except ModuleNotFoundError:
            from src.ui.menus.pygame_main_menu_view import PygameMainMenuView

        return PygameMainMenuView()
    except ImportError:
        return ConsoleMainMenuView()
    except Exception:
        return ConsoleMainMenuView()
