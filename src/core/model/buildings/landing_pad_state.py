from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from .resource_store import SUPPLY_RESOURCE_ORDER, empty_resource_store
from .supply_transport_state import SupplyTransportState


@dataclass
class LandingPadState:
    object_id: str
    pad_size: str
    capacity: int
    secured_by_objective_id: str
    resources: dict[str, int] = field(default_factory=empty_resource_store)
    next_transport_eta_seconds: float | None = None
    active_transport: SupplyTransportState | None = None

    def is_secured(self, objective_status: Mapping[str, bool]) -> bool:
        if not self.secured_by_objective_id:
            return True
        return bool(objective_status.get(self.secured_by_objective_id, False))

    def total_stored(self, *, resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER) -> int:
        return sum(int(self.resources.get(resource_id, 0)) for resource_id in resource_order)

    def remaining_capacity(self, *, resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER) -> int:
        return max(0, int(self.capacity) - self.total_stored(resource_order=resource_order))

    def clear_supply_cycle(self) -> None:
        self.next_transport_eta_seconds = None
        self.active_transport = None

    def take_resources(
        self,
        amount: int,
        *,
        resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER,
    ) -> dict[str, int]:
        remaining = max(0, int(amount))
        taken = {resource_id: 0 for resource_id in resource_order}
        for resource_id in resource_order:
            if remaining <= 0:
                break
            available = max(0, int(self.resources.get(resource_id, 0)))
            transferred = min(available, remaining)
            self.resources[resource_id] = available - transferred
            taken[resource_id] = transferred
            remaining -= transferred
        return taken

    def apply_transport_delivery(
        self,
        cargo: Mapping[str, int],
        *,
        resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER,
    ) -> None:
        free_capacity = self.remaining_capacity(resource_order=resource_order)
        if free_capacity <= 0:
            return

        cargo_by_resource = {
            resource_id: int(cargo.get(resource_id, 0))
            for resource_id in resource_order
        }
        total_cargo = sum(cargo_by_resource.values())
        if total_cargo <= 0:
            return

        if total_cargo <= free_capacity:
            delivered_by_resource = cargo_by_resource
        else:
            delivered_by_resource = {resource_id: 0 for resource_id in resource_order}
            remainders: list[tuple[float, str]] = []
            used_capacity = 0
            for resource_id in resource_order:
                exact_allocation = (cargo_by_resource[resource_id] / total_cargo) * free_capacity
                base_allocation = min(cargo_by_resource[resource_id], int(math.floor(exact_allocation)))
                delivered_by_resource[resource_id] = base_allocation
                used_capacity += base_allocation
                remainders.append((exact_allocation - base_allocation, resource_id))

            remaining_capacity = free_capacity - used_capacity
            for _fraction, resource_id in sorted(remainders, reverse=True):
                if remaining_capacity <= 0:
                    break
                if delivered_by_resource[resource_id] >= cargo_by_resource[resource_id]:
                    continue
                delivered_by_resource[resource_id] += 1
                remaining_capacity -= 1

        for resource_id, delivered_amount in delivered_by_resource.items():
            self.resources[resource_id] = int(self.resources.get(resource_id, 0)) + delivered_amount

    def start_transport(
        self,
        *,
        transport_type_id: str,
        origin_position: tuple[float, float],
        destination_position: tuple[float, float],
        approach_seconds: float,
    ) -> None:
        self.active_transport = SupplyTransportState(
            transport_id=f"{self.object_id}_supply",
            transport_type_id=transport_type_id,
            target_object_id=self.object_id,
            phase="inbound",
            position=origin_position,
            seconds_remaining=approach_seconds,
            total_phase_seconds=approach_seconds,
            origin_position=origin_position,
            destination_position=destination_position,
        )

    def advance_transport(
        self,
        *,
        elapsed_seconds: float,
        unload_seconds: float,
        departure_seconds: float,
        delivery_cargo: Mapping[str, int],
        supply_interval_seconds: float,
        resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER,
    ) -> None:
        active_transport = self.active_transport
        if active_transport is None:
            return

        active_transport.spend(elapsed_seconds)
        if active_transport.phase == "inbound":
            active_transport.position = active_transport.progress_position()
            if active_transport.seconds_remaining > 0.0:
                return
            active_transport.begin_unloading(unload_seconds=unload_seconds)
            return

        if active_transport.phase == "unloading":
            active_transport.position = active_transport.destination_position
            if active_transport.seconds_remaining > 0.0:
                return
            self.apply_transport_delivery(delivery_cargo, resource_order=resource_order)
            active_transport.begin_outbound(departure_seconds=departure_seconds)
            return

        active_transport.position = active_transport.progress_position()
        if active_transport.seconds_remaining > 0.0:
            return

        self.active_transport = None
        if self.total_stored(resource_order=resource_order) < self.capacity:
            self.next_transport_eta_seconds = supply_interval_seconds

    def refresh_transport_geometry(
        self,
        *,
        destination_position: tuple[float, float],
        origin_position: tuple[float, float],
    ) -> None:
        if self.active_transport is None:
            return
        self.active_transport.refresh_geometry(
            destination_position=destination_position,
            origin_position=origin_position,
        )

    def update_supply(
        self,
        elapsed_seconds: float,
        *,
        is_secured: bool,
        supply_interval_seconds: float,
        refresh_transport_geometry: Callable[[], None],
        start_transport: Callable[[], None],
        advance_transport: Callable[[float], None],
        resource_order: Sequence[str] = SUPPLY_RESOURCE_ORDER,
    ) -> None:
        if not is_secured:
            self.clear_supply_cycle()
            return

        remaining_elapsed = max(0.0, elapsed_seconds)
        while True:
            if self.active_transport is not None:
                if remaining_elapsed <= 0.0:
                    refresh_transport_geometry()
                    return

                spent_seconds = min(remaining_elapsed, self.active_transport.seconds_remaining)
                remaining_elapsed -= spent_seconds
                advance_transport(spent_seconds)
                if remaining_elapsed <= 0.0:
                    return
                continue

            if self.total_stored(resource_order=resource_order) >= self.capacity:
                self.next_transport_eta_seconds = None
                return

            if self.next_transport_eta_seconds is None:
                self.next_transport_eta_seconds = supply_interval_seconds

            if remaining_elapsed <= 0.0:
                return

            next_transport_eta_seconds = self.next_transport_eta_seconds
            assert next_transport_eta_seconds is not None
            if remaining_elapsed < next_transport_eta_seconds:
                self.next_transport_eta_seconds = next_transport_eta_seconds - remaining_elapsed
                return

            remaining_elapsed -= next_transport_eta_seconds
            self.next_transport_eta_seconds = None
            start_transport()

