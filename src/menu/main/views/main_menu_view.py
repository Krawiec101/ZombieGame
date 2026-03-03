from __future__ import annotations


class MainMenuView:
    def render(self) -> None:
        print("\n=== MENU GLOWNE ===")
        print("1) Nowa gra")
        print("2) Wczytaj")
        print("3) Wyjdz")

    def read_choice(self) -> str:
        return input("Wybierz (1-3): ").strip()

    def render_invalid_choice(self) -> None:
        print("Niepoprawny wybor. Sprobuj ponownie.")

    def show_selection_info(self, message: str) -> None:
        print(message)

    def close(self) -> None:
        pass
