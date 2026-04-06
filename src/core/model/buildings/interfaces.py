from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol


class ResourceStore(Protocol):
    capacity: int
    resources: dict[str, int]

    def total_stored(self, *, resource_order: Sequence[str]) -> int: ...

    def free_capacity(self, *, resource_order: Sequence[str]) -> int: ...


class SupportsTransportCycle(Protocol):
    next_transport_eta_seconds: float | None

    def clear_supply_cycle(self) -> None: ...

    def refresh_transport_geometry(
        self,
        *,
        destination_position: tuple[float, float],
        origin_position: tuple[float, float],
    ) -> None: ...

    def update_supply(
        self,
        elapsed_seconds: float,
        *,
        is_secured: bool,
        supply_interval_seconds: float,
        refresh_transport_geometry: Callable[[], None],
        start_transport: Callable[[], None],
        advance_transport: Callable[[float], None],
        resource_order: Sequence[str],
    ) -> None: ...
