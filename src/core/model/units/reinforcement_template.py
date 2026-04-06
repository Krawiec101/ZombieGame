from __future__ import annotations

from dataclasses import dataclass

from .commander_state import CommanderState


@dataclass(frozen=True)
class ReinforcementTemplate:
    unit_id: str
    unit_type_id: str
    name: str
    commander: CommanderState
    experience_level: str
    personnel: int
    morale: int
    ammo: int
    rations: int
    fuel: int

