from __future__ import annotations

import math
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass

from core.model.units import UnitState

from .combat_state import CombatNotificationState, CombatState
from .enemy_group_state import ZombieGroupState

CombatFinder = Callable[[str], CombatState | None]
EnemyGroupFinder = Callable[[str], ZombieGroupState | None]
EnemyGroupRemover = Callable[[str], None]
UnitAttackResolver = Callable[[UnitState], int]
UnitBoundsResolver = Callable[[UnitState], tuple[int, int, int, int]]
UnitDefenseResolver = Callable[[UnitState], int]
UnitFinder = Callable[[str], UnitState | None]
EnemyGroupBoundsResolver = Callable[[ZombieGroupState], tuple[int, int, int, int]]
BoundsOverlapChecker = Callable[
    [tuple[int, int, int, int], tuple[int, int, int, int]],
    bool,
]
UnitPositionClamp = Callable[[tuple[float, float], str], tuple[float, float]]


@dataclass(frozen=True)
class CombatResolver:
    min_duration_seconds: float
    max_duration_seconds: float
    exchange_interval_seconds: float
    notification_duration_seconds: float
    max_notifications: int = 6

    def update_notifications(
        self,
        notifications: Sequence[CombatNotificationState],
        *,
        elapsed_seconds: float,
    ) -> list[CombatNotificationState]:
        if elapsed_seconds <= 0.0:
            return list(notifications)

        updated_notifications: list[CombatNotificationState] = []
        for notification in notifications:
            notification.seconds_remaining = max(0.0, notification.seconds_remaining - elapsed_seconds)
            if notification.seconds_remaining > 0.0:
                updated_notifications.append(notification)
        return updated_notifications

    def start_combats_for_colliding_units(
        self,
        combats: MutableMapping[str, CombatState],
        notifications: list[CombatNotificationState],
        *,
        units: Sequence[UnitState],
        enemy_groups: Sequence[ZombieGroupState],
        combat_for_unit: CombatFinder,
        combat_for_enemy_group: CombatFinder,
        unit_bounds: UnitBoundsResolver,
        enemy_group_bounds: EnemyGroupBoundsResolver,
        bounds_overlap: BoundsOverlapChecker,
        unit_attack: UnitAttackResolver,
        clamp_unit_position: UnitPositionClamp,
    ) -> None:
        for enemy_group in enemy_groups:
            if combat_for_enemy_group(enemy_group.group_id) is not None:
                continue

            for unit in units:
                if combat_for_unit(unit.unit_id) is not None:
                    continue
                if not bounds_overlap(unit_bounds(unit), enemy_group_bounds(enemy_group)):
                    continue
                self.start_combat(
                    combats,
                    notifications,
                    unit=unit,
                    enemy_group=enemy_group,
                    unit_attack=unit_attack,
                    clamp_unit_position=clamp_unit_position,
                )
                break

    def start_combat(
        self,
        combats: MutableMapping[str, CombatState],
        notifications: list[CombatNotificationState],
        *,
        unit: UnitState,
        enemy_group: ZombieGroupState,
        unit_attack: UnitAttackResolver,
        clamp_unit_position: UnitPositionClamp,
    ) -> None:
        duration_seconds = self.combat_duration_seconds(
            unit,
            enemy_group,
            unit_attack=unit_attack,
        )
        combat = CombatState(
            combat_id=f"{unit.unit_id}:{enemy_group.group_id}",
            unit_id=unit.unit_id,
            enemy_group_id=enemy_group.group_id,
            seconds_remaining=duration_seconds,
            total_seconds=duration_seconds,
            seconds_until_next_exchange=min(self.exchange_interval_seconds, duration_seconds),
        )
        combats[combat.combat_id] = combat
        self.append_notification(
            notifications,
            notification_id=f"{combat.combat_id}:started",
            unit_name=unit.name or unit.unit_id,
            enemy_group_name=enemy_group.name or enemy_group.group_id,
            phase="started",
        )
        unit.position = clamp_unit_position(unit.position, unit.unit_type_id)

    def combat_duration_seconds(
        self,
        unit: UnitState,
        enemy_group: ZombieGroupState,
        *,
        unit_attack: UnitAttackResolver,
    ) -> float:
        enemy_strength = max(1, int(enemy_group.personnel))
        suppression = max(1, int(unit_attack(unit)) // 3)
        expected_exchanges = math.ceil(enemy_strength / suppression)
        return min(
            self.max_duration_seconds,
            max(self.min_duration_seconds, float(expected_exchanges * self.exchange_interval_seconds)),
        )

    def apply_combat_attrition(
        self,
        unit: UnitState,
        enemy_group: ZombieGroupState,
        *,
        unit_attack: UnitAttackResolver,
        unit_defense: UnitDefenseResolver,
    ) -> None:
        attack_strength = unit_attack(unit)
        suppression = max(1, int(attack_strength) // 3)
        enemy_group.personnel = max(0, enemy_group.personnel - suppression)
        unit.ammo = max(0, unit.ammo - max(4, attack_strength * 2))
        incoming_pressure = math.ceil(enemy_group.personnel / 5)
        defense_offset = max(0, unit_defense(unit) // 8)
        unit.morale = max(0, unit.morale - max(1, incoming_pressure - defense_offset))

    def update_combats(
        self,
        combats: MutableMapping[str, CombatState],
        notifications: list[CombatNotificationState],
        *,
        elapsed_seconds: float,
        find_unit_by_id: UnitFinder,
        find_enemy_group_by_id: EnemyGroupFinder,
        remove_enemy_group_by_id: EnemyGroupRemover,
        unit_attack: UnitAttackResolver,
        unit_defense: UnitDefenseResolver,
    ) -> None:
        for combat_id in list(sorted(combats)):
            combat = combats.get(combat_id)
            if combat is None:
                continue

            unit = find_unit_by_id(combat.unit_id)
            enemy_group = find_enemy_group_by_id(combat.enemy_group_id)
            if unit is None or enemy_group is None:
                combats.pop(combat_id, None)
                continue

            remaining_elapsed = max(0.0, elapsed_seconds)
            while remaining_elapsed > 0.0:
                step_seconds = min(
                    remaining_elapsed,
                    combat.seconds_remaining,
                    combat.seconds_until_next_exchange,
                )
                combat.seconds_remaining = max(0.0, combat.seconds_remaining - step_seconds)
                combat.seconds_until_next_exchange = max(0.0, combat.seconds_until_next_exchange - step_seconds)
                remaining_elapsed -= step_seconds

                if combat.seconds_until_next_exchange <= 0.0:
                    self.apply_combat_attrition(
                        unit,
                        enemy_group,
                        unit_attack=unit_attack,
                        unit_defense=unit_defense,
                    )
                    if enemy_group.personnel <= 0:
                        self.resolve_combat(
                            combats,
                            notifications,
                            combat=combat,
                            find_unit_by_id=find_unit_by_id,
                            find_enemy_group_by_id=find_enemy_group_by_id,
                            remove_enemy_group_by_id=remove_enemy_group_by_id,
                        )
                        break
                    if combat.seconds_remaining > 0.0:
                        combat.seconds_until_next_exchange = min(
                            self.exchange_interval_seconds,
                            combat.seconds_remaining,
                        )

                if combat.seconds_remaining <= 0.0:
                    self.resolve_combat(
                        combats,
                        notifications,
                        combat=combat,
                        find_unit_by_id=find_unit_by_id,
                        find_enemy_group_by_id=find_enemy_group_by_id,
                        remove_enemy_group_by_id=remove_enemy_group_by_id,
                    )
                    break

                if step_seconds <= 0.0:
                    break

    def resolve_combat(
        self,
        combats: MutableMapping[str, CombatState],
        notifications: list[CombatNotificationState],
        *,
        combat: CombatState,
        find_unit_by_id: UnitFinder,
        find_enemy_group_by_id: EnemyGroupFinder,
        remove_enemy_group_by_id: EnemyGroupRemover,
    ) -> None:
        combats.pop(combat.combat_id, None)
        unit = find_unit_by_id(combat.unit_id)
        enemy_group = find_enemy_group_by_id(combat.enemy_group_id)
        if unit is not None and enemy_group is not None:
            self.append_notification(
                notifications,
                notification_id=f"{combat.combat_id}:ended",
                unit_name=unit.name or unit.unit_id,
                enemy_group_name=enemy_group.name or enemy_group.group_id,
                phase="ended",
            )
        if enemy_group is None:
            return
        remove_enemy_group_by_id(enemy_group.group_id)

    def append_notification(
        self,
        notifications: list[CombatNotificationState],
        *,
        notification_id: str,
        unit_name: str,
        enemy_group_name: str,
        phase: str,
    ) -> None:
        notifications.append(
            CombatNotificationState(
                notification_id=notification_id,
                unit_name=unit_name,
                enemy_group_name=enemy_group_name,
                phase=phase,
                seconds_remaining=self.notification_duration_seconds,
            )
        )
        notifications[:] = notifications[-self.max_notifications :]
