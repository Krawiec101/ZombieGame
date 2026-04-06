from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LandingPadTypeSpec:
    size_id: str
    capacity: int
    transport_type_id: str

