from __future__ import annotations

from src.core.orders import ExitRequested, LoadGameRequested, NewGameRequested, Order


class ConsoleMainMenuView:
    def render(self) -> None:
        print("\n=== MENU GLOWNE ===")
        print("1) Nowa gra")
        print("2) Wczytaj")
        print("3) Wyjdz")

    def poll_orders(self) -> list[Order]:
        raw = input("Wybierz (1-3): ").strip()
        order = map_choice_to_order(raw)
        if order is None:
            print("Niepoprawny wybor. Sprobuj ponownie.")
            return []
        return [order]

    def close(self) -> None:
        pass


def map_choice_to_order(raw: str) -> Order | None:
    if raw == "1":
        return NewGameRequested()
    if raw == "2":
        return LoadGameRequested()
    if raw == "3":
        return ExitRequested()
    return None
