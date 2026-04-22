from __future__ import annotations

from core.combat import ZombieGroupState
from core.model.units import UnitState, UnitTypeSpec
from core.snapshots import GameStateSnapshotBuilder


def test_snapshot_package_exports_builder_for_ui_projections() -> None:
    builder = GameStateSnapshotBuilder()
    unit = UnitState(unit_id="alpha", unit_type_id="infantry_squad", position=(10.0, 20.0))
    enemy_group = ZombieGroupState(group_id="zulu", position=(30.0, 40.0), personnel=5)
    unit_specs = {"infantry_squad": UnitTypeSpec(type_id="infantry_squad", speed_kmph=4.2, marker_size_px=18)}

    units = builder.units(
        [unit],
        unit_type_specs=unit_specs,
        unit_armament_key=lambda _: "rifle",
        unit_attack=lambda _: 4,
        unit_defense=lambda _: 5,
        resource_order=("fuel", "mre", "ammo"),
        supply_route_id_for_unit=lambda _unit_id: None,
        combat_for_unit=lambda _unit_id: None,
        combat_seconds_remaining_for_unit=lambda _unit_id: None,
        display_seconds=lambda value: None if value is None else int(value),
    )
    enemy_groups = builder.enemy_groups(
        [enemy_group],
        marker_size_px=22,
        combat_for_enemy_group=lambda _group_id: None,
    )

    assert units[0]["unit_id"] == "alpha"
    assert units[0]["marker_size_px"] == 18
    assert enemy_groups[0].group_id == "zulu"
