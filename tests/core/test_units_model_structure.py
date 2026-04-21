from __future__ import annotations

from core.model.units import (
    CommanderState,
    ExperienceLevel,
    FormationLevel,
    ReinforcementTemplate,
    UnitEquipmentState,
    UnitOrganizationState,
    UnitTypeSpec,
    VehicleAssignmentState,
    VehicleTypeSpec,
)


def test_units_package_exports_new_domain_types() -> None:
    commander = CommanderState(name="sier. Anna Sowa", rank="sergeant", experience_level=ExperienceLevel.BASIC)
    equipment = UnitEquipmentState(primary_weapon_key="rifle", vest_key="plate")
    vehicles = (VehicleAssignmentState(vehicle_type_id="apc", count=1),)
    organization = UnitOrganizationState(
        formation_level=FormationLevel.SQUAD,
        subordinate_unit_ids=("alpha_fireteam",),
        max_subordinate_units=3,
    )
    template = ReinforcementTemplate(
        unit_id="alpha",
        unit_type_id="infantry_squad",
        name="1. Druzyna Alfa",
        commander=commander,
        equipment=equipment,
        vehicles=vehicles,
        organization=organization,
    )
    unit_spec = UnitTypeSpec(type_id="infantry_squad", speed_kmph=4.2, marker_size_px=18)
    vehicle_spec = VehicleTypeSpec(type_id="apc", transport_speed_bonus_kmph=12.0, attack_bonus=3, defense_bonus=2)

    assert template.commander.rank == "sergeant"
    assert template.equipment == equipment
    assert template.vehicles == vehicles
    assert template.organization == organization
    assert unit_spec.type_id == "infantry_squad"
    assert vehicle_spec.attack_bonus == 3


def test_organization_defaults_match_future_platoon_composition_direction() -> None:
    squad = UnitOrganizationState()
    platoon = UnitOrganizationState(
        formation_level=FormationLevel.PLATOON,
        subordinate_unit_ids=("alpha", "bravo", "charlie"),
        max_subordinate_units=3,
    )

    assert squad.formation_level == FormationLevel.SQUAD
    assert platoon.can_attach_subordinate() is False
