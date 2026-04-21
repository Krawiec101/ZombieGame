from __future__ import annotations

import pytest

from core.model.units import (
    CommanderState,
    FormationLevel,
    UnitEquipmentState,
    UnitOrganizationState,
    UnitState,
    VehicleAssignmentState,
)


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


def test_unit_state_requires_commander_instance() -> None:
    with pytest.raises(ValueError):
        UnitState(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(0.0, 0.0),
            commander=None,  # type: ignore[arg-type]
        )


def test_unit_state_can_store_equipment_vehicles_and_organization() -> None:
    unit = UnitState(
        unit_id="u1",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        commander=CommanderState(name="sier. Ada", rank="sergeant", experience_level="trained"),
        equipment=UnitEquipmentState(
            primary_weapon_key="game.unit.weapon.rifle",
            support_weapon_key="game.unit.weapon.lmg",
            vest_key="game.unit.vest.plate",
        ),
        vehicles=(
            VehicleAssignmentState(vehicle_type_id="apc", count=2),
            VehicleAssignmentState(vehicle_type_id="truck", count=1),
        ),
        organization=UnitOrganizationState(
            formation_level=FormationLevel.SQUAD,
            subordinate_unit_ids=("fireteam_alpha", "fireteam_bravo"),
            max_subordinate_units=3,
        ),
    )

    assert unit.equipment.primary_weapon_key == "game.unit.weapon.rifle"
    assert unit.equipment.vest_key == "game.unit.vest.plate"
    assert unit.total_assigned_vehicles() == 3
    assert unit.organization.can_attach_subordinate() is True
