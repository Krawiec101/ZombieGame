from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitEquipmentState:
    primary_weapon_key: str = ""
    support_weapon_key: str = ""
    vest_key: str = ""
