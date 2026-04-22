from __future__ import annotations

from core.combat import CombatNotificationState, CombatResolver, CombatState, ZombieGroupState


def test_combat_package_exports_runtime_types() -> None:
    resolver = CombatResolver(
        min_duration_seconds=24.0,
        max_duration_seconds=60.0,
        exchange_interval_seconds=6.0,
        notification_duration_seconds=12.0,
    )
    combat = CombatState(
        combat_id="alpha:zulu",
        unit_id="alpha",
        enemy_group_id="zulu",
        seconds_remaining=24.0,
        total_seconds=24.0,
        seconds_until_next_exchange=6.0,
    )
    notification = CombatNotificationState(
        notification_id="alpha:zulu:started",
        unit_name="Alpha",
        enemy_group_name="Zulu",
        phase="started",
        seconds_remaining=12.0,
    )
    enemy_group = ZombieGroupState(group_id="zulu", position=(100.0, 120.0), personnel=7)

    assert resolver.max_notifications == 6
    assert combat.enemy_group_id == "zulu"
    assert notification.phase == "started"
    assert enemy_group.personnel == 7
