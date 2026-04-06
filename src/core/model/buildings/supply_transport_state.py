from __future__ import annotations

from dataclasses import dataclass

from .transport_geometry import interpolate_points


@dataclass
class SupplyTransportState:
    transport_id: str
    transport_type_id: str
    target_object_id: str
    phase: str
    position: tuple[float, float]
    seconds_remaining: float
    total_phase_seconds: float
    origin_position: tuple[float, float]
    destination_position: tuple[float, float]

    def progress_position(self) -> tuple[float, float]:
        if self.phase == "unloading":
            return self.destination_position

        progress = 1.0
        if self.total_phase_seconds > 0:
            progress = 1.0 - (self.seconds_remaining / self.total_phase_seconds)

        if self.phase == "outbound":
            return interpolate_points(self.destination_position, self.origin_position, progress)

        return interpolate_points(self.origin_position, self.destination_position, progress)

    def spend(self, elapsed_seconds: float) -> None:
        self.seconds_remaining = max(0.0, self.seconds_remaining - elapsed_seconds)

    def begin_unloading(self, *, unload_seconds: float) -> None:
        self.phase = "unloading"
        self.seconds_remaining = unload_seconds
        self.total_phase_seconds = unload_seconds
        self.position = self.destination_position

    def begin_outbound(self, *, departure_seconds: float) -> None:
        self.phase = "outbound"
        self.seconds_remaining = departure_seconds
        self.total_phase_seconds = departure_seconds
        self.position = self.progress_position()

    def refresh_geometry(
        self,
        *,
        destination_position: tuple[float, float],
        origin_position: tuple[float, float],
    ) -> None:
        self.destination_position = destination_position
        self.origin_position = origin_position
        self.position = self.progress_position()

