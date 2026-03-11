from __future__ import annotations

from ui.game_views.units import UNIT_TYPES, create_unit_state


def test_unit_types_define_infantry_and_motorized_squad() -> None:
    assert "infantry_squad" in UNIT_TYPES
    assert "motorized_infantry_squad" in UNIT_TYPES
    assert UNIT_TYPES["infantry_squad"].speed_kmph < UNIT_TYPES["motorized_infantry_squad"].speed_kmph


def test_create_unit_state_uses_registered_unit_type() -> None:
    unit = create_unit_state(
        unit_id="unit-1",
        unit_type_id="motorized_infantry_squad",
        position=(100.0, 120.0),
    )

    assert unit.unit_id == "unit-1"
    assert unit.unit_type.type_id == "motorized_infantry_squad"
    assert unit.position == (100.0, 120.0)
    assert unit.target is None
