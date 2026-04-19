from __future__ import annotations

import os

from contracts.main_menu_view import MainMenuView
from ui.menus.console_main_menu_view import ConsoleMainMenuView

_USE_CONSOLE_VALUES = {"1", "true", "yes", "on"}


def create_view() -> MainMenuView:
    if os.getenv("GAME_USE_CONSOLE_MENU", "").strip().lower() in _USE_CONSOLE_VALUES:
        return ConsoleMainMenuView()

    try:
        from ui.menus.pygame_main_menu_view import PygameMainMenuView
        return PygameMainMenuView()
    except ImportError:
        return ConsoleMainMenuView()
    except Exception:
        return ConsoleMainMenuView()
