import pytest

from src.menu.main.controllers.main_menu_controller import (
    MainMenuController,
    MainMenuEventType,
)
from src.menu.main.views.main_menu_view import MainMenuView


class FakeMainMenuView(MainMenuView):
    def __init__(self, inputs: list[str]) -> None:
        self._inputs = inputs
        self.render_calls = 0
        self.invalid_calls = 0

    def render(self) -> None:
        self.render_calls += 1

    def read_choice(self) -> str:
        if not self._inputs:
            raise RuntimeError("Brak kolejnych inputów w FakeMainMenuView.")
        return self._inputs.pop(0)

    def render_invalid_choice(self) -> None:
        self.invalid_calls += 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", MainMenuEventType.NEW_GAME_REQUESTED),
        ("2", MainMenuEventType.LOAD_GAME_REQUESTED),
        ("3", MainMenuEventType.EXIT_REQUESTED),
    ],
)
def test_main_menu_controller_returns_expected_event(raw: str, expected: MainMenuEventType) -> None:
    view = FakeMainMenuView([raw])
    controller = MainMenuController(view)

    event = controller.run()

    assert event.type == expected
    assert view.render_calls == 1
    assert view.invalid_calls == 0


def test_main_menu_controller_reprompts_on_invalid_then_accepts_valid() -> None:
    view = FakeMainMenuView(["x", " ", "2"])  # dwa błędne, potem poprawne
    controller = MainMenuController(view)

    event = controller.run()

    assert event.type == MainMenuEventType.LOAD_GAME_REQUESTED
    assert view.invalid_calls == 2
    assert view.render_calls == 3
