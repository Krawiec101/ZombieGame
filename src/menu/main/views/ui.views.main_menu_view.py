from __future__ import annotations

class MainMenuView:
    def render(self) -> None:
        print("\n=== MENU GŁÓWNE ===")
        print("1) Nowa gra")
        print("2) Wczytaj")
        print("3) Wyjdź")

    def read_choice(self) -> str:
        return input("Wybierz (1-3): ").strip()

    def render_invalid_choice(self) -> None:
        print("Niepoprawny wybór. Spróbuj ponownie.")
