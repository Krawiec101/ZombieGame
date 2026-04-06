from __future__ import annotations

from core.model.units import UnitState


def test_load_supplies_respects_remaining_capacity_and_resource_order() -> None:
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        carried_resources={"fuel": 2, "mre": 1, "ammo": 0},
    )

    loaded = unit.load_supplies(
        {"fuel": 5, "mre": 5, "ammo": 5},
        capacity=6,
        resource_order=("fuel", "mre", "ammo"),
    )

    assert loaded == {"fuel": 3, "mre": 0, "ammo": 0}
    assert unit.carried_resources == {"fuel": 5, "mre": 1, "ammo": 0}


def test_unload_supplies_removes_only_available_resources() -> None:
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        carried_resources={"fuel": 4, "mre": 2, "ammo": 1},
    )

    unloaded = unit.unload_supplies(
        {"fuel": 3, "mre": 5, "ammo": 0},
        resource_order=("fuel", "mre", "ammo"),
    )

    assert unloaded == {"fuel": 3, "mre": 2, "ammo": 0}
    assert unit.carried_resources == {"fuel": 1, "mre": 0, "ammo": 1}


def test_clear_supplies_resets_carried_resources_to_zero() -> None:
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        carried_resources={"fuel": 4, "mre": 2, "ammo": 1},
    )

    unit.clear_supplies(resource_order=("fuel", "mre", "ammo"))

    assert unit.carried_resources == {"fuel": 0, "mre": 0, "ammo": 0}
