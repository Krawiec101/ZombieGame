from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NameModalOutcome:
    confirm: bool = False
    exit_requested: bool = False
    next_value: str | None = None


def hitbox_action_at(hitboxes: Mapping[str, Any], position: tuple[int, int]) -> str | None:
    for action, hitbox in hitboxes.items():
        if hitbox.collidepoint(position):
            return action
    return None


def game_context_menu_action_from_key(pygame: Any, key: int) -> str | None:
    if key == pygame.K_ESCAPE:
        return "resume"
    if key in (pygame.K_1, pygame.K_KP1):
        return "resume"
    if key in (pygame.K_2, pygame.K_KP2):
        return "to_menu"
    if key in (pygame.K_3, pygame.K_KP3):
        return "exit"
    return None


def should_dismiss_modal_from_click(
    ok_hitbox: Any | None,
    *,
    position: tuple[int, int],
) -> bool:
    return bool(ok_hitbox and ok_hitbox.collidepoint(position))


def resolve_name_modal_input(
    pygame: Any,
    *,
    key: int,
    typed: str,
    current_value: str,
    max_length: int = 24,
) -> NameModalOutcome:
    if key == pygame.K_ESCAPE:
        return NameModalOutcome(exit_requested=True)
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return NameModalOutcome(confirm=True)
    if key == pygame.K_BACKSPACE:
        return NameModalOutcome(next_value=current_value[:-1])
    if typed and typed.isprintable():
        return NameModalOutcome(next_value=(current_value + typed)[:max_length])
    return NameModalOutcome(next_value=current_value)


def should_dismiss_report_modal(pygame: Any, *, key: int) -> bool:
    return key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER)
