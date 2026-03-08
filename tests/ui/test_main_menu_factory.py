from __future__ import annotations

import builtins
import sys
from types import ModuleType

import pytest

from ui import main_menu as main_menu_module


class DummyConsoleView:
    pass


class DummyPygameView:
    pass


def test_create_view_prefers_console_when_env_requests_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAME_USE_CONSOLE_MENU", " YES ")
    monkeypatch.setattr(main_menu_module, "ConsoleMainMenuView", DummyConsoleView)

    view = main_menu_module.create_view()

    assert isinstance(view, DummyConsoleView)


def test_create_view_uses_pygame_view_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GAME_USE_CONSOLE_MENU", raising=False)
    monkeypatch.setattr(main_menu_module, "ConsoleMainMenuView", DummyConsoleView)

    fake_pygame_module = ModuleType("ui.pygame_main_menu_view")
    fake_pygame_module.PygameMainMenuView = DummyPygameView
    monkeypatch.setitem(sys.modules, "ui.pygame_main_menu_view", fake_pygame_module)

    view = main_menu_module.create_view()

    assert isinstance(view, DummyPygameView)


def test_create_view_falls_back_to_console_when_pygame_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GAME_USE_CONSOLE_MENU", raising=False)
    monkeypatch.setattr(main_menu_module, "ConsoleMainMenuView", DummyConsoleView)

    original_import = builtins.__import__

    def import_with_pygame_failure(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name in {"ui.pygame_main_menu_view", "src.ui.pygame_main_menu_view"}:
            raise ImportError("pygame unavailable")
        return original_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_pygame_failure)

    view = main_menu_module.create_view()

    assert isinstance(view, DummyConsoleView)


def test_create_view_falls_back_to_console_when_pygame_view_init_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GAME_USE_CONSOLE_MENU", raising=False)
    monkeypatch.setattr(main_menu_module, "ConsoleMainMenuView", DummyConsoleView)

    class RaisingPygameView:
        def __init__(self) -> None:
            raise RuntimeError("unexpected init failure")

    fake_pygame_module = ModuleType("ui.pygame_main_menu_view")
    fake_pygame_module.PygameMainMenuView = RaisingPygameView
    monkeypatch.setitem(sys.modules, "ui.pygame_main_menu_view", fake_pygame_module)

    view = main_menu_module.create_view()

    assert isinstance(view, DummyConsoleView)
