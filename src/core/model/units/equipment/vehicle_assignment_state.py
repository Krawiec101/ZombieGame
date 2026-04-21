from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleAssignmentState:
    vehicle_type_id: str
    count: int = 0
