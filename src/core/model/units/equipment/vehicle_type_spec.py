from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleTypeSpec:
    type_id: str
    transport_speed_bonus_kmph: float = 0.0
    attack_bonus: int = 0
    defense_bonus: int = 0
    cargo_capacity_bonus: int = 0
