from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ZombieGroupState:
    group_id: str
    position: tuple[float, float]
    name: str = ""
    personnel: int = 0
