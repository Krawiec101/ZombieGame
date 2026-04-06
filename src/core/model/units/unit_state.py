from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from .commander_state import CommanderState


@dataclass
class UnitState:
    unit_id: str
    unit_type_id: str
    position: tuple[float, float]
    target: tuple[float, float] | None = None
    path: tuple[tuple[float, float], ...] = ()
    carried_resources: dict[str, int] = field(default_factory=dict)
    name: str = ""
    commander: CommanderState = field(default_factory=CommanderState)
    experience_level: str = "basic"
    personnel: int = 0
    morale: int = 0
    ammo: int = 0
    rations: int = 0
    fuel: int = 0

    def set_movement_target(
        self,
        final_target: tuple[float, float],
        *,
        path: Sequence[tuple[float, float]],
        positions_match: Callable[[tuple[float, float], tuple[float, float]], bool],
    ) -> None:
        if positions_match(self.position, final_target):
            self.position = final_target
            self.clear_movement()
            return

        self.target = final_target
        self.path = tuple(path) if path else (final_target,)

    def clear_movement(self) -> None:
        self.target = None
        self.path = ()

    def advance_towards_target(
        self,
        *,
        speed_px_per_tick: float,
        clamp_position: Callable[[tuple[float, float]], tuple[float, float]],
    ) -> None:
        if self.target is None or speed_px_per_tick <= 0:
            return

        current_x, current_y = self.position
        next_waypoint = self.path[0] if self.path else self.target
        target_x, target_y = next_waypoint
        delta_x = target_x - current_x
        delta_y = target_y - current_y
        distance = math.hypot(delta_x, delta_y)

        if distance <= speed_px_per_tick:
            self.position = next_waypoint
            if self.path:
                self.path = self.path[1:]
            if not self.path:
                self.target = None
            return

        step = speed_px_per_tick / distance
        moved_x = current_x + delta_x * step
        moved_y = current_y + delta_y * step
        self.position = clamp_position((moved_x, moved_y))

    def bounds(self, *, marker_size_px: int) -> tuple[int, int, int, int]:
        left = int(self.position[0] - marker_size_px / 2)
        top = int(self.position[1] - marker_size_px / 2)
        right = left + marker_size_px
        bottom = top + marker_size_px
        return (left, top, right, bottom)

    def carried_supply_total(self, *, resource_order: Sequence[str]) -> int:
        return sum(int(self.carried_resources.get(resource_id, 0)) for resource_id in resource_order)

    def clear_supplies(self, *, resource_order: Sequence[str]) -> None:
        self.load_carried_resources({}, resource_order=resource_order)

    def load_supplies(
        self,
        cargo: Mapping[str, int],
        *,
        capacity: int,
        resource_order: Sequence[str],
    ) -> dict[str, int]:
        remaining_capacity = max(0, int(capacity) - self.carried_supply_total(resource_order=resource_order))
        loaded = {resource_id: 0 for resource_id in resource_order}
        updated_resources = {
            resource_id: max(0, int(self.carried_resources.get(resource_id, 0)))
            for resource_id in resource_order
        }
        for resource_id in resource_order:
            if remaining_capacity <= 0:
                break
            available = max(0, int(cargo.get(resource_id, 0)))
            transferred = min(available, remaining_capacity)
            updated_resources[resource_id] += transferred
            loaded[resource_id] = transferred
            remaining_capacity -= transferred
        self.carried_resources = updated_resources
        return loaded

    def unload_supplies(
        self,
        cargo: Mapping[str, int],
        *,
        resource_order: Sequence[str],
    ) -> dict[str, int]:
        unloaded = {resource_id: 0 for resource_id in resource_order}
        updated_resources = {
            resource_id: max(0, int(self.carried_resources.get(resource_id, 0)))
            for resource_id in resource_order
        }
        for resource_id in resource_order:
            requested = max(0, int(cargo.get(resource_id, 0)))
            transferred = min(updated_resources[resource_id], requested)
            updated_resources[resource_id] -= transferred
            unloaded[resource_id] = transferred
        self.carried_resources = updated_resources
        return unloaded

    def clear_carried_resources(self, *, resource_order: Sequence[str]) -> None:
        self.clear_supplies(resource_order=resource_order)

    def load_carried_resources(
        self,
        resources: Mapping[str, int],
        *,
        resource_order: Sequence[str],
    ) -> None:
        self.carried_resources = {
            resource_id: max(0, int(resources.get(resource_id, 0)))
            for resource_id in resource_order
        }

    def subtract_delivered_resources(
        self,
        delivered: Mapping[str, int],
        *,
        resource_order: Sequence[str],
    ) -> None:
        self.unload_supplies(delivered, resource_order=resource_order)

