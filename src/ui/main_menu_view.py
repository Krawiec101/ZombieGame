from __future__ import annotations

try:
    from contracts.main_menu_view import MainMenuView
except ModuleNotFoundError:
    from src.contracts.main_menu_view import MainMenuView

__all__ = ["MainMenuView"]
