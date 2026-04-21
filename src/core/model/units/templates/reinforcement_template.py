from __future__ import annotations

from dataclasses import dataclass, field

from ..commanders import CommanderState, ExperienceLevel
from ..equipment import UnitEquipmentState, VehicleAssignmentState
from ..organization import UnitOrganizationState


@dataclass(frozen=True)
class ReinforcementTemplate:
    unit_id: str
    unit_type_id: str
    name: str
    commander: CommanderState
    experience_level: str = ExperienceLevel.BASIC
    personnel: int = 0
    morale: int = 0
    ammo: int = 0
    rations: int = 0
    fuel: int = 0
    equipment: UnitEquipmentState = field(default_factory=UnitEquipmentState)
    vehicles: tuple[VehicleAssignmentState, ...] = ()
    organization: UnitOrganizationState = field(default_factory=UnitOrganizationState)
