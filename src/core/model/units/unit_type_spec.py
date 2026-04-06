from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitTypeSpec:
    type_id: str
    speed_kmph: float
    marker_size_px: int
    armament_key: str = ""
    attack: int = 0
    defense: int = 0
    can_transport_supplies: bool = False
    supply_capacity: int = 0

