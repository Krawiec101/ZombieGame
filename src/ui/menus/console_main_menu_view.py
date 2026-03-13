from __future__ import annotations

from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    ExitRequested,
    LoadGameFlowRouted,
    LoadGameRequested,
    NewGameFlowRouted,
    NewGameRequested,
    UIEvent,
)
from ui.i18n import text


_MENU_OPTION_LABEL_KEYS = {
    "1": "main_menu.option.new_game",
    "2": "main_menu.option.load_game",
    "3": "main_menu.option.exit",
}


class ConsoleMainMenuView:
    def render(self) -> None:
        print()
        print(text("console.menu.header"))
        for choice, label_key in _MENU_OPTION_LABEL_KEYS.items():
            print(
                text(
                    "console.menu.option",
                    choice=choice,
                    label=text(label_key),
                )
            )

    def poll_ui_events(self) -> list[UIEvent]:
        raw = input(text("main_menu.prompt.choice")).strip()
        event = map_choice_to_ui_event(raw)
        if event is None:
            print(text("main_menu.error.invalid_choice_retry"))
            return []
        return [event]

    def handle_domain_event(self, event: DomainEvent) -> None:
        if isinstance(event, NewGameFlowRouted):
            print(text("flow.new_game.stub"))
        elif isinstance(event, LoadGameFlowRouted):
            print(text("flow.load_game.stub"))
        elif isinstance(event, ExitFlowRouted):
            print(text("flow.exit"))

    def close(self) -> None:
        pass


def map_choice_to_ui_event(raw: str) -> UIEvent | None:
    if raw == "1":
        return NewGameRequested()
    if raw == "2":
        return LoadGameRequested()
    if raw == "3":
        return ExitRequested()
    return None


# Backward-compatible alias for previous function name.
map_choice_to_order = map_choice_to_ui_event
