from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol


class SupportsMovement(Protocol):
    position: tuple[float, float]
    target: tuple[float, float] | None
    path: tuple[tuple[float, float], ...]

    def set_movement_target(
        self,
        final_target: tuple[float, float],
        *,
        path: Sequence[tuple[float, float]],
        positions_match: Callable[[tuple[float, float], tuple[float, float]], bool],
    ) -> None: ...

    def clear_movement(self) -> None: ...

    def advance_towards_target(
        self,
        *,
        speed_px_per_tick: float,
        clamp_position: Callable[[tuple[float, float]], tuple[float, float]],
    ) -> None: ...

    def bounds(self, *, marker_size_px: int) -> tuple[int, int, int, int]: ...


class SupportsCargo(Protocol):
    carried_resources: dict[str, int]

    def carried_supply_total(self, *, resource_order: Sequence[str]) -> int: ...

    def clear_carried_resources(self, *, resource_order: Sequence[str]) -> None: ...

    def load_carried_resources(
        self,
        resources: Mapping[str, int],
        *,
        resource_order: Sequence[str],
    ) -> None: ...

    def subtract_delivered_resources(
        self,
        delivered: Mapping[str, int],
        *,
        resource_order: Sequence[str],
    ) -> None: ...

