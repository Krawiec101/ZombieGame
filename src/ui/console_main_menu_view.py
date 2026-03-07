from __future__ import annotations

try:
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
except ModuleNotFoundError:
    from src.contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        ExitRequested,
        LoadGameFlowRouted,
        LoadGameRequested,
        NewGameFlowRouted,
        NewGameRequested,
        UIEvent,
    )


class ConsoleMainMenuView:
    def render(self) -> None:
        print("\n=== MENU GLOWNE ===")
        print("1) Nowa gra")
        print("2) Wczytaj")
        print("3) Wyjdz")

    def poll_ui_events(self) -> list[UIEvent]:
        raw = input("Wybierz (1-3): ").strip()
        event = map_choice_to_ui_event(raw)
        if event is None:
            print("Niepoprawny wybor. Sprobuj ponownie.")
            return []
        return [event]

    def handle_domain_event(self, event: DomainEvent) -> None:
        if isinstance(event, NewGameFlowRouted):
            print("Szkic: przejscie do nowej gry")
        elif isinstance(event, LoadGameFlowRouted):
            print("Szkic: przejscie do wczytania gry")
        elif isinstance(event, ExitFlowRouted):
            print("Wyjscie z aplikacji")

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
