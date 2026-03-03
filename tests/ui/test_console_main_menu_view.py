from menu.main.views.main_menu_view import MainMenuView


def test_main_menu_view_read_choice_strips_whitespace(monkeypatch) -> None:
    view = MainMenuView()
    monkeypatch.setattr("builtins.input", lambda _: " 2  ")

    choice = view.read_choice()

    assert choice == "2"


def test_main_menu_view_render_prints_menu(capsys) -> None:
    view = MainMenuView()

    view.render()

    out = capsys.readouterr().out
    assert "=== MENU GLOWNE ===" in out
    assert "1) Nowa gra" in out
    assert "2) Wczytaj" in out
    assert "3) Wyjdz" in out


def test_main_menu_view_render_invalid_choice_prints_message(capsys) -> None:
    view = MainMenuView()

    view.render_invalid_choice()

    out = capsys.readouterr().out
    assert "Niepoprawny wybor. Sprobuj ponownie." in out
