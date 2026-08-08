# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_find_unit_at_prefers_last_unit_when_bounds_overlap() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
        UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]

    clicked = session._find_unit_at((100, 100))

    assert clicked is not None
    assert clicked.unit_id == "u2"

def test_consume_combat_elapsed_seconds_clamps_negative_elapsed_and_updates_timestamp() -> None:
    clock = _FakeClock(start=10.0)
    session = create_default_game_session(time_provider=clock.now)

    assert session._consume_combat_elapsed_seconds() == 0.0
    clock.current = 5.0
    assert session._consume_combat_elapsed_seconds() == 0.0
    assert session._last_combat_update_at == 5.0

def test_enemy_group_starts_on_landing_pad_center() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    landing_pad = next(obj for obj in session.map_objects_snapshot() if obj["id"] == "landing_pad")
    left, top, right, bottom = landing_pad["bounds"]

    enemy_group = _enemy_group_snapshot(session)

    assert enemy_group.position == ((left + right) / 2.0, (top + bottom) / 2.0)

def test_collision_with_enemy_starts_combat_and_exposes_alert_snapshot() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    motorized = session._find_unit_by_id("bravo_mechanized")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert motorized is not None
    assert enemy_group is not None

    motorized.position = enemy_group.position
    motorized.target = (120.0, 120.0)
    motorized.path = ((120.0, 120.0),)

    session.tick()

    snapshot = session.snapshot()
    motorized_snapshot = next(unit for unit in snapshot.units if unit.unit_id == "bravo_mechanized")

    assert snapshot.combats == (
        CombatSnapshot(
            combat_id="bravo_mechanized:zulu_zombies",
            unit_id="bravo_mechanized",
            unit_name="2. Sekcja Bravo",
            enemy_group_id="zulu_zombies",
            enemy_group_name="Mala grupa zombie",
            seconds_remaining=24,
        ),
    )
    assert snapshot.combat_notifications == (
        CombatNotificationSnapshot(
            notification_id="bravo_mechanized:zulu_zombies:started",
            unit_name="2. Sekcja Bravo",
            enemy_group_name="Mala grupa zombie",
            phase="started",
            seconds_remaining=12,
        ),
    )
    assert motorized_snapshot.is_in_combat is True
    assert motorized_snapshot.combat_seconds_remaining == 24
    assert snapshot.enemy_groups[0].is_in_combat is True

def test_active_combat_stops_unit_movement_until_enemy_group_is_cleared() -> None:
    clock = _FakeClock()
    session = create_default_game_session(time_provider=clock.now)
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = session._find_unit_by_id("alpha_infantry")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert infantry is not None
    assert enemy_group is not None

    infantry.position = enemy_group.position
    infantry.target = (120.0, 120.0)
    infantry.path = ((120.0, 120.0),)

    session.tick()
    locked_position = infantry.position

    clock.advance(5)
    session.tick()

    assert infantry.position == locked_position
    assert session.combats_snapshot()[0].seconds_remaining == 37

    for _ in range(12):
        clock.advance(6)
        session.tick()
        if session.combats_snapshot() == ():
            break

    assert session.combats_snapshot() == ()
    assert tuple(group.group_id for group in session.enemy_groups_snapshot()) == ("echo_zombies",)

def test_start_combats_does_not_assign_enemy_group_to_second_unit_when_already_engaged() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    alpha = session._find_unit_by_id("alpha_infantry")
    bravo = session._find_unit_by_id("bravo_mechanized")
    enemy_group = session._find_enemy_group_by_id("zulu_zombies")

    assert alpha is not None
    assert bravo is not None
    assert enemy_group is not None

    alpha.position = enemy_group.position
    bravo.position = enemy_group.position
    session._combats = {
        "alpha_infantry:zulu_zombies": CombatState(
            combat_id="alpha_infantry:zulu_zombies",
            unit_id="alpha_infantry",
            enemy_group_id="zulu_zombies",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._start_combats_for_colliding_units()

    assert tuple(sorted(session._combats)) == ("alpha_infantry:zulu_zombies",)

def test_update_combats_continues_after_none_placeholder_and_updates_real_combat() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "a_placeholder": None,  # type: ignore[dict-item]
        "z_real": CombatState(
            combat_id="z_real",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=8.0)

    real_combat = session._combats["z_real"]
    assert isinstance(real_combat, CombatState)
    assert real_combat.seconds_remaining == 16.0
    assert real_combat.seconds_until_next_exchange == 4.0

def test_update_combats_removes_stale_combat_when_unit_or_enemy_disappears() -> None:
    session = create_default_game_session()
    session._combats = {
        "missing": CombatState(
            combat_id="missing",
            unit_id="ghost_unit",
            enemy_group_id="ghost_enemy",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=4.0)

    assert session._combats == {}

def test_update_combats_removes_combat_when_enemy_group_disappears_but_unit_still_exists() -> None:
    session = create_default_game_session()
    session._units = [UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0))]
    session._combats = {
        "missing-enemy": CombatState(
            combat_id="missing-enemy",
            unit_id="u1",
            enemy_group_id="ghost_enemy",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=4.0)

    assert session._combats == {}

def test_update_combats_waits_for_exchange_boundary_before_applying_attrition() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=5.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 19.0
    assert combat.seconds_until_next_exchange == 1.0
    assert enemy_group.personnel == 5
    assert unit.ammo == 30
    assert unit.morale == 20

def test_update_combats_resolves_on_enemy_elimination_even_when_time_remains() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=12,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=1)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    assert session._combats == {}
    assert session._enemy_groups == []
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="engagement:ended",
            unit_name="u1",
            enemy_group_name="e1",
            phase="ended",
            seconds_remaining=12,
        ),
    )

def test_update_combats_keeps_engagement_active_when_enemy_survives_and_timer_stays_above_zero() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="infantry_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=20,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=10)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=10.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=8.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 2.0
    assert session._enemy_groups[0].personnel == 9
    assert combat.seconds_until_next_exchange == 2.0

def test_update_combats_keeps_engagement_active_when_attrition_leaves_one_enemy_remaining() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=20,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=3)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=12.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 11.0
    assert combat.seconds_until_next_exchange == 6.0
    assert enemy_group.personnel == 1

def test_update_combats_applies_final_exchange_when_timer_hits_zero_on_exchange_boundary() -> None:
    session = create_default_game_session()
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(50.0, 50.0),
        ammo=40,
        morale=12,
    )
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=2)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=6.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=6.0)

    assert session._combats == {}
    assert session._enemy_groups == []
    assert unit.ammo == 26
    assert unit.morale == 11
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="engagement:ended",
            unit_name="u1",
            enemy_group_name="e1",
            phase="ended",
            seconds_remaining=12,
        ),
    )

def test_update_combats_continues_after_resolving_earlier_combat() -> None:
    session = create_default_game_session()
    first_unit = UnitState(unit_id="u1", unit_type_id="mechanized_squad", position=(50.0, 50.0), ammo=40, morale=20)
    second_unit = UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(60.0, 60.0), ammo=30, morale=20)
    first_enemy = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=1)
    second_enemy = ZombieGroupState(group_id="e2", position=(60.0, 60.0), personnel=5)
    session._units = [first_unit, second_unit]
    session._enemy_groups = [first_enemy, second_enemy]
    session._combats = {
        "a_first": CombatState(
            combat_id="a_first",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=1.0,
        ),
        "z_second": CombatState(
            combat_id="z_second",
            unit_id="u2",
            enemy_group_id="e2",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=2.0)

    assert "a_first" not in session._combats
    assert session._combats["z_second"].seconds_remaining == 22.0
    assert session._combats["z_second"].seconds_until_next_exchange == 4.0

def test_update_combats_keeps_combat_alive_for_last_second_after_exchange() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=10)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=7.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=6.0)

    combat = session._combats["engagement"]
    assert combat.seconds_remaining == 1.0
    assert combat.seconds_until_next_exchange == 1.0
    assert enemy_group.personnel == 9

def test_update_combats_resolves_when_timer_reaches_zero_between_exchanges() -> None:
    session = create_default_game_session()
    unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    enemy_group = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    session._units = [unit]
    session._enemy_groups = [enemy_group]
    session._combats = {
        "engagement": CombatState(
            combat_id="engagement",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=1.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        )
    }

    session._update_combats(elapsed_seconds=1.0)

    assert session._combats == {}
    assert session._enemy_groups == []

def test_update_combats_zero_step_on_one_combat_does_not_block_later_combats() -> None:
    session = create_default_game_session()
    first_unit = UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(50.0, 50.0), ammo=30, morale=20)
    second_unit = UnitState(unit_id="u2", unit_type_id="infantry_squad", position=(60.0, 60.0), ammo=30, morale=20)
    first_enemy = ZombieGroupState(group_id="e1", position=(50.0, 50.0), personnel=5)
    second_enemy = ZombieGroupState(group_id="e2", position=(60.0, 60.0), personnel=5)
    session._units = [first_unit, second_unit]
    session._enemy_groups = [first_enemy, second_enemy]
    session._combats = {
        "a_first": CombatState(
            combat_id="a_first",
            unit_id="u1",
            enemy_group_id="e1",
            seconds_remaining=5.0,
            total_seconds=24.0,
            seconds_until_next_exchange=0.0,
        ),
        "z_second": CombatState(
            combat_id="z_second",
            unit_id="u2",
            enemy_group_id="e2",
            seconds_remaining=24.0,
            total_seconds=24.0,
            seconds_until_next_exchange=6.0,
        ),
    }

    session._update_combats(elapsed_seconds=2.0)

    assert session._combats["a_first"].seconds_until_next_exchange == 5.0
    assert first_enemy.personnel == 4
    assert session._combats["z_second"].seconds_remaining == 22.0
    assert session._combats["z_second"].seconds_until_next_exchange == 4.0

def test_combat_notifications_expire_after_display_window() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=3.0,
        )
    ]

    session._update_combat_notifications(elapsed_seconds=1.0)
    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=2,
        ),
    )

    session._update_combat_notifications(elapsed_seconds=2.5)
    assert session.combat_notifications_snapshot() == ()

def test_combat_notifications_snapshot_keeps_zero_seconds_without_fallback_to_one() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=0.0,
        )
    ]

    assert session.combat_notifications_snapshot() == (
        CombatNotificationSnapshot(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=0,
        ),
    )

def test_apply_combat_attrition_uses_expected_suppression_for_infantry_and_mechanized_units() -> None:
    session = create_default_game_session()
    infantry = UnitState(
        unit_id="alpha",
        unit_type_id="infantry_squad",
        position=(0.0, 0.0),
        ammo=90,
        morale=72,
    )
    infantry_enemy = ZombieGroupState(group_id="e1", position=(0.0, 0.0), personnel=7)

    session._apply_combat_attrition(infantry, infantry_enemy)

    assert infantry_enemy.personnel == 6
    assert infantry.ammo == 82
    assert infantry.morale == 70

    mechanized = UnitState(
        unit_id="bravo",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        ammo=120,
        morale=81,
        vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),),
    )
    mechanized_enemy = ZombieGroupState(group_id="e2", position=(0.0, 0.0), personnel=7)

    session._apply_combat_attrition(mechanized, mechanized_enemy)

    assert mechanized_enemy.personnel == 5
    assert mechanized.ammo == 104
    assert mechanized.morale == 80

def test_bounds_overlap_requires_axis_overlap_in_each_direction() -> None:
    session = create_default_game_session()

    assert session._bounds_overlap((0, 0, 10, 10), (5, 5, 15, 15)) is True
    assert session._bounds_overlap((0, 0, 10, 10), (11, 0, 20, 10)) is False
    assert session._bounds_overlap((11, 0, 20, 10), (0, 0, 10, 10)) is False
    assert session._bounds_overlap((0, 0, 10, 10), (0, 11, 10, 20)) is False
    assert session._bounds_overlap((0, 11, 10, 20), (0, 0, 10, 10)) is False

def test_enemy_groups_state_snapshot_exposes_exact_keys_for_objective_evaluation() -> None:
    session = create_default_game_session()
    session._enemy_groups = [
        ZombieGroupState(
            group_id="z1",
            position=(120.0, 230.0),
            name="Patrol",
            personnel=5,
        )
    ]

    assert session.enemy_groups_state_snapshot() == [
        {
            "group_id": "z1",
            "position": (120.0, 230.0),
            "name": "Patrol",
            "personnel": 5,
        }
    ]

def test_reset_clears_internal_combat_notifications_list() -> None:
    session = create_default_game_session()
    session._combat_notifications = [
        CombatNotificationState(
            notification_id="notice",
            unit_name="alpha",
            enemy_group_name="zulu",
            phase="started",
            seconds_remaining=2.0,
        )
    ]

    session.reset()

    assert session._combat_notifications == []
    assert session.combat_notifications_snapshot() == ()

def test_reset_clears_enemy_groups_and_mission_reports_collections() -> None:
    session = create_default_game_session()
    session._enemy_groups = [
        ZombieGroupState(group_id="z1", position=(10.0, 10.0), name="patrol", personnel=4)
    ]
    session._mission_reports = [
        MissionReportSnapshot(
            report_id="report",
            title_key="title",
            message_key="message",
        )
    ]

    session.reset()

    assert session._enemy_groups == []
    assert session._mission_reports == []

