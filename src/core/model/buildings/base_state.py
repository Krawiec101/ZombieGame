from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .resource_store import SUPPLY_RESOURCE_ORDER, empty_resource_store


@dataclass
class BaseState:
    object_id: str
    capacity: int
    resources: dict[str, int] = field(default_factory=empty_resource_store)

    def total_stored(self, *, resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER) -> int:
        return sum(int(self.resources.get(resource_id, 0)) for resource_id in resource_order)

    def free_capacity(self, *, resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER) -> int:
        return max(0, int(self.capacity) - self.total_stored(resource_order=resource_order))

    def store_resources(
        self,
        cargo: Mapping[str, int],
        *,
        resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER,
    ) -> dict[str, int]:
        remaining_capacity = self.free_capacity(resource_order=resource_order)
        stored = {resource_id: 0 for resource_id in resource_order}
        for resource_id in resource_order:
            if remaining_capacity <= 0:
                break
            available = max(0, int(cargo.get(resource_id, 0)))
            transferred = min(available, remaining_capacity)
            self.resources[resource_id] = int(self.resources.get(resource_id, 0)) + transferred
            stored[resource_id] = transferred
            remaining_capacity -= transferred
        return stored

