from __future__ import annotations

from collections.abc import Sequence

from core.model.buildings import LandingPadState

from .logistics_port import LogisticsPort


class SupplyNetworkService:
    def __init__(
        self,
        *,
        supply_interval_seconds: float,
        supply_unload_seconds: float,
        supply_departure_seconds: float,
        resource_order: Sequence[str],
    ) -> None:
        self._supply_interval_seconds = supply_interval_seconds
        self._supply_unload_seconds = supply_unload_seconds
        self._supply_departure_seconds = supply_departure_seconds
        self._resource_order = tuple(resource_order)

    def update_network(self, port: LogisticsPort, *, elapsed_seconds: float) -> None:
        for landing_pad in port.landing_pads().values():
            self._update_landing_pad_supply(
                landing_pad,
                elapsed_seconds=max(0.0, elapsed_seconds),
                port=port,
            )

    def update_routes(self, port: LogisticsPort, *, elapsed_seconds: float) -> None:
        for route_id in port.supply_route_ids():
            route = port.supply_route_by_id(route_id)
            if route is None:
                continue

            unit = port.find_unit_by_id(route.unit_id)
            if unit is None:
                port.remove_supply_route(route_id)
                continue

            port.refresh_supply_route(route, elapsed_seconds=elapsed_seconds)

    def refresh_route_targets(self, port: LogisticsPort) -> None:
        for route_id in port.supply_route_ids():
            route = port.supply_route_by_id(route_id)
            if route is not None:
                port.refresh_supply_route(route)

    def _update_landing_pad_supply(
        self,
        landing_pad: LandingPadState,
        *,
        elapsed_seconds: float,
        port: LogisticsPort,
    ) -> None:
        landing_pad.update_supply(
            elapsed_seconds,
            is_secured=landing_pad.is_secured(port.objective_status()),
            supply_interval_seconds=self._supply_interval_seconds,
            refresh_transport_geometry=lambda: port.refresh_transport_geometry(landing_pad),
            start_transport=lambda: port.start_transport_for_landing_pad(landing_pad),
            advance_transport=lambda spent_seconds: port.advance_transport(landing_pad, spent_seconds),
            resource_order=self._resource_order,
        )

    def advance_transport(
        self,
        landing_pad: LandingPadState,
        *,
        elapsed_seconds: float,
        delivery_cargo: dict[str, int],
    ) -> None:
        active_transport = landing_pad.active_transport
        if active_transport is None:
            return
        landing_pad.advance_transport(
            elapsed_seconds=elapsed_seconds,
            unload_seconds=self._supply_unload_seconds,
            departure_seconds=self._supply_departure_seconds,
            delivery_cargo=delivery_cargo,
            supply_interval_seconds=self._supply_interval_seconds,
            resource_order=self._resource_order,
        )
