from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitType:
    type_id: str
    display_name_key: str
    speed_kmph: float
    marker_color: tuple[int, int, int]
    marker_border_color: tuple[int, int, int]
    marker_size_px: int = 18


@dataclass
class UnitState:
    unit_id: str
    unit_type: UnitType
    position: tuple[float, float]
    target: tuple[float, float] | None = None


UNIT_TYPES: dict[str, UnitType] = {
    "infantry_squad": UnitType(
        type_id="infantry_squad",
        display_name_key="unit.type.infantry_squad",
        speed_kmph=4.2,
        marker_color=(208, 186, 104),
        marker_border_color=(78, 66, 28),
        marker_size_px=18,
    ),
    "motorized_infantry_squad": UnitType(
        type_id="motorized_infantry_squad",
        display_name_key="unit.type.motorized_infantry_squad",
        speed_kmph=18.0,
        marker_color=(138, 173, 112),
        marker_border_color=(42, 74, 38),
        marker_size_px=20,
    ),
}


def create_unit_state(*, unit_id: str, unit_type_id: str, position: tuple[float, float]) -> UnitState:
    unit_type = UNIT_TYPES[unit_type_id]
    return UnitState(unit_id=unit_id, unit_type=unit_type, position=position)
