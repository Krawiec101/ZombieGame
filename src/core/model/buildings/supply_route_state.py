from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SupplyRouteState:
    route_id: str
    unit_id: str
    source_object_id: str
    destination_object_id: str
    phase: str
