from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto

from src.menu.main.views.main_menu_view import MainMenuView


class MainMenuEventType(Enum):
    NEW_GAME_REQUESTED = auto()
    LOAD_GAME_REQUESTED = auto()
    EXIT_REQUESTED = auto()


@dataclass(frozen=True)
class MainMenuEvent:
    type: MainMenuEventType


class MainMenuController:
    def __init__(self, view: MainMenuView) -> None:
        self.view = view

    def run(self) -> MainMenuEvent:
        while True:
            self.view.render()
            raw = self.view.read_choice()

            match raw:
                case "1":
                    return MainMenuEvent(MainMenuEventType.NEW_GAME_REQUESTED)
                case "2":
                    return MainMenuEvent(MainMenuEventType.LOAD_GAME_REQUESTED)
                case "3":
                    return MainMenuEvent(MainMenuEventType.EXIT_REQUESTED)
                case _:
                    self.view.render_invalid_choice()
