from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import get_type_hints

from pytestarch import Rule, get_evaluable_architecture

from contracts.game_state import GameStateSnapshot
from ui.game_views.pygame_game_view import PygameGameView


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _architecture(*, exclude_external_libraries: bool = True):
    root_dir = _root_dir()
    return get_evaluable_architecture(
        str(root_dir),
        str(root_dir / "src"),
        exclude_external_libraries=exclude_external_libraries,
    )


def _module_prefix() -> str:
    return f"{_root_dir().name}.src"


def _module_alias_regex(*module_roots: str) -> str:
    escaped_roots = sorted({re.escape(root) for root in module_roots})
    roots_group = "|".join(escaped_roots)
    prefix = re.escape(_module_prefix())
    return rf"^(?:{prefix}\.(?:{roots_group})|src\.(?:{roots_group})|(?:{roots_group}))(?:\..*)?$"


def _source_module_roots() -> set[str]:
    src_dir = _root_dir() / "src"
    roots: set[str] = set()
    for entry in src_dir.iterdir():
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        if entry.is_dir():
            roots.add(entry.name)
        elif entry.suffix == ".py":
            roots.add(entry.stem)
    return roots


def _parse_module(relative_path: str) -> ast.AST:
    source = (_root_dir() / relative_path).read_text(encoding="utf-8")
    return ast.parse(source, filename=relative_path)


def _attribute_call_names(relative_path: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_parse_module(relative_path)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _uses_module_not_found_fallback(relative_path: str) -> bool:
    for node in ast.walk(_parse_module(relative_path)):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if isinstance(handler.type, ast.Name) and handler.type.id == "ModuleNotFoundError":
                return True
    return False


def test_core_does_not_depend_on_ui() -> None:
    prefix = _module_prefix()
    Rule().modules_that().are_sub_modules_of(f"{prefix}.core").should_not().import_modules_that().have_name_matching(
        _module_alias_regex("ui")
    ).assert_applies(_architecture(exclude_external_libraries=False))


def test_core_does_not_depend_on_pygame() -> None:
    prefix = _module_prefix()
    Rule().modules_that().are_sub_modules_of(f"{prefix}.core").should_not().import_modules_that().have_name_matching(
        r"^pygame(\..*)?$"
    ).assert_applies(_architecture(exclude_external_libraries=False))


def test_ui_does_not_depend_on_core_services() -> None:
    prefix = _module_prefix()
    Rule().modules_that().are_sub_modules_of(f"{prefix}.ui").should_not().import_modules_that().have_name_matching(
        _module_alias_regex("core")
    ).assert_applies(_architecture(exclude_external_libraries=False))


def test_app_only_depends_on_app_core_ui_or_contracts_internally() -> None:
    prefix = _module_prefix()
    disallowed_internal_roots = _source_module_roots() - {"app", "core", "ui", "contracts"}
    if not disallowed_internal_roots:
        return

    Rule().modules_that().are_sub_modules_of(f"{prefix}.app").should_not().import_modules_that().have_name_matching(
        _module_alias_regex(*sorted(disallowed_internal_roots))
    ).assert_applies(_architecture(exclude_external_libraries=False))


def test_mission_objectives_logic_lives_in_core_not_ui() -> None:
    root_dir = _root_dir()
    assert (root_dir / "src" / "core" / "mission_objectives.py").exists()
    assert not (root_dir / "src" / "ui" / "game_views" / "mission_objectives.py").exists()


def test_game_session_and_units_logic_lives_in_core_not_ui() -> None:
    root_dir = _root_dir()
    assert (root_dir / "src" / "core" / "game_session.py").exists()
    assert not (root_dir / "src" / "ui" / "game_views" / "units.py").exists()


def test_ui_game_view_consumes_typed_game_state_snapshot() -> None:
    _ = inspect.signature(PygameGameView.apply_game_state)
    assert get_type_hints(PygameGameView.apply_game_state)["snapshot"] is GameStateSnapshot


def test_ui_game_view_does_not_invoke_core_session_methods_directly() -> None:
    forbidden_calls = {
        "handle_left_click",
        "handle_right_click",
        "handle_supply_route",
        "sync_state",
        "update_map_dimensions",
    }
    assert not (_attribute_call_names("src/ui/game_views/pygame_game_view.py") & forbidden_calls)


def test_pygame_menu_view_emits_game_events_instead_of_service_calls() -> None:
    forbidden_calls = {
        "handle_left_click",
        "handle_right_click",
        "handle_supply_route",
        "sync_state",
        "update_map_dimensions",
    }
    assert not (_attribute_call_names("src/ui/menus/pygame_main_menu_view.py") & forbidden_calls)


def test_source_modules_do_not_use_module_path_fallback_imports() -> None:
    fallback_files = [
        path.relative_to(_root_dir()).as_posix()
        for path in (_root_dir() / "src").rglob("*.py")
        if _uses_module_not_found_fallback(path.relative_to(_root_dir()).as_posix())
    ]
    assert fallback_files == []
