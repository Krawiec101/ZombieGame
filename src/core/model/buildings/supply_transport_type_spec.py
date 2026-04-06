from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplyTransportTypeSpec:
    type_id: str
    cargo: dict[str, int]

