from __future__ import annotations

import re
from pathlib import Path

from pytestarch import Rule, get_evaluable_architecture


def _architecture(*, exclude_external_libraries: bool = True):
    root_dir = Path(__file__).resolve().parents[2]
    return get_evaluable_architecture(
        str(root_dir),
        str(root_dir / "src"),
        exclude_external_libraries=exclude_external_libraries,
    )


def _module_prefix() -> str:
    root_dir = Path(__file__).resolve().parents[2]
    return f"{root_dir.name}.src"


def _module_alias_regex(*module_roots: str) -> str:
    escaped_roots = sorted({re.escape(root) for root in module_roots})
    roots_group = "|".join(escaped_roots)
    prefix = re.escape(_module_prefix())
    return rf"^(?:{prefix}\.(?:{roots_group})|src\.(?:{roots_group})|(?:{roots_group}))(?:\..*)?$"


def _source_module_roots() -> set[str]:
    src_dir = Path(__file__).resolve().parents[2] / "src"
    roots: set[str] = set()
    for entry in src_dir.iterdir():
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        if entry.is_dir():
            roots.add(entry.name)
        elif entry.suffix == ".py":
            roots.add(entry.stem)
    return roots


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
    root_dir = Path(__file__).resolve().parents[2]
    assert (root_dir / "src" / "core" / "mission_objectives.py").exists()
    assert not (root_dir / "src" / "ui" / "game_views" / "mission_objectives.py").exists()


def test_game_session_and_units_logic_lives_in_core_not_ui() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    assert (root_dir / "src" / "core" / "game_session.py").exists()
    assert not (root_dir / "src" / "ui" / "game_views" / "units.py").exists()


def test_ui_game_view_is_state_driven_without_core_service_reference() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    source = (root_dir / "src" / "ui" / "game_views" / "pygame_game_view.py").read_text(
        encoding="utf-8"
    )
    assert "game_session" not in source


def test_pygame_menu_view_emits_game_events_instead_of_service_calls() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    source = (root_dir / "src" / "ui" / "menus" / "pygame_main_menu_view.py").read_text(
        encoding="utf-8"
    )
    assert "handle_left_click(" not in source
    assert "handle_right_click(" not in source
