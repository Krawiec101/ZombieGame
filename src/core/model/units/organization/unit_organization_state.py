from __future__ import annotations

from dataclasses import dataclass

from .formation_level import FormationLevel


@dataclass(frozen=True)
class UnitOrganizationState:
    formation_level: str = FormationLevel.SQUAD
    parent_unit_id: str | None = None
    subordinate_unit_ids: tuple[str, ...] = ()
    max_subordinate_units: int = 0

    def can_attach_subordinate(self) -> bool:
        return len(self.subordinate_unit_ids) < max(0, int(self.max_subordinate_units))
