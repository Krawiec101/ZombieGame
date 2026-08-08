# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_game_session_initializes_map_objects_and_units() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    map_object_ids = {obj["id"] for obj in session.map_objects_snapshot()}
    unit_type_ids = {unit["unit_type_id"] for unit in session.units_snapshot()}
    assert map_object_ids == {"hq", "landing_pad", "recon_site_1", "recon_site_2", "recon_site_3", "recon_site_4"}
    assert unit_type_ids == {"infantry_squad", "mechanized_squad"}
    assert session.enemy_groups_snapshot() == (
        ZombieGroupSnapshot(
            group_id="zulu_zombies",
            position=session.enemy_groups_snapshot()[0].position,
            marker_size_px=22,
            name="Mala grupa zombie",
            personnel=7,
        ),
        ZombieGroupSnapshot(
            group_id="echo_zombies",
            position=session.enemy_groups_snapshot()[1].position,
            marker_size_px=22,
            name="Wedrujaca grupa zombie",
            personnel=6,
        ),
    )

def test_commander_state_from_config_coerces_values_and_applies_basic_default() -> None:
    assert _commander_state_from_config({"name": 17}) == CommanderState(
        name="17",
        experience_level="basic",
    )
    assert _commander_state_from_config(
        {"name": "sier. Ada", "rank": "sergeant", "experience_level": 2}
    ) == CommanderState(
        name="sier. Ada",
        rank="sergeant",
        experience_level="2",
    )

def test_commander_state_from_config_uses_empty_name_when_field_is_missing() -> None:
    assert _commander_state_from_config({}) == CommanderState(
        name="",
        experience_level="basic",
    )

def test_equipment_state_from_config_coerces_known_fields_and_defaults() -> None:
    assert _equipment_state_from_config({}) == UnitEquipmentState()
    assert _equipment_state_from_config(
        {
            "primary_weapon_key": 17,
            "support_weapon_key": 18,
            "vest_key": 19,
        }
    ) == UnitEquipmentState(
        primary_weapon_key="17",
        support_weapon_key="18",
        vest_key="19",
    )

def test_vehicle_assignments_from_config_skips_invalid_items_and_coerces_counts() -> None:
    assert _vehicle_assignments_from_config(None) == ()
    assert _vehicle_assignments_from_config(
        [
            {"vehicle_type_id": "wheeled_apc", "count": "2"},
            "ignored",
            {"vehicle_type_id": 7},
        ]
    ) == (
        VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=2),
        VehicleAssignmentState(vehicle_type_id="7", count=0),
    )

def test_organization_state_from_config_applies_defaults_and_optional_parent() -> None:
    assert _organization_state_from_config({}) == UnitOrganizationState()
    assert _organization_state_from_config(
        {
            "formation_level": "platoon",
            "parent_unit_id": 12,
            "subordinate_unit_ids": [1, "two"],
            "max_subordinate_units": "3",
        }
    ) == UnitOrganizationState(
        formation_level="platoon",
        parent_unit_id="12",
        subordinate_unit_ids=("1", "two"),
        max_subordinate_units=3,
    )
    assert _organization_state_from_config({"parent_unit_id": None}).parent_unit_id is None

def test_build_map_objects_preserves_configured_object_sizes() -> None:
    session = create_default_game_session()

    objects = session._build_map_objects(960, 640)
    layout_by_id = {obj["id"]: obj["bounds"] for obj in objects}

    hq_left, hq_top, hq_right, hq_bottom = layout_by_id["hq"]
    assert (hq_right - hq_left, hq_bottom - hq_top) == (84, 56)

    pad_left, pad_top, pad_right, pad_bottom = layout_by_id["landing_pad"]
    assert (pad_right - pad_left, pad_bottom - pad_top) == (72, 48)

def test_vehicle_assignments_increase_unit_speed_attack_and_defense() -> None:
    session = create_default_game_session()
    session._map_size = (960, 640)
    mechanized = UnitState(
        unit_id="bravo",
        unit_type_id="mechanized_squad",
        position=(0.0, 0.0),
        vehicles=(VehicleAssignmentState(vehicle_type_id="wheeled_apc", count=1),),
    )

    assert session._unit_speed_kmph(mechanized) == 24.0
    assert session._unit_attack(mechanized) == 8
    assert session._unit_defense(mechanized) == 9
    assert session._unit_movement_pixels_per_tick(mechanized) > session._movement_pixels_per_tick("mechanized_squad")

