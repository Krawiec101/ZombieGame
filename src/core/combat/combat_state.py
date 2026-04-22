from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CombatState:
    combat_id: str
    unit_id: str
    enemy_group_id: str
    seconds_remaining: float
    total_seconds: float
    seconds_until_next_exchange: float


@dataclass
class CombatNotificationState:
    notification_id: str
    unit_name: str
    enemy_group_name: str
    phase: str
    seconds_remaining: float
