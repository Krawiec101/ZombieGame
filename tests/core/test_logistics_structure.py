from __future__ import annotations

from core.logistics import LogisticsPort, SupplyNetworkService, SupplyRouteEndpoint, SupplyRouteManager


def test_logistics_package_exports_route_manager_and_service_contracts() -> None:
    manager = SupplyRouteManager()
    service = SupplyNetworkService(
        supply_interval_seconds=45.0,
        supply_unload_seconds=14.0,
        supply_departure_seconds=6.0,
        resource_order=("fuel", "mre", "ammo"),
    )
    endpoint = SupplyRouteEndpoint(
        object_id="lp_alpha",
        location_type="landing_pad",
        can_dispatch_supplies=True,
        can_receive_supplies=False,
        is_active=True,
    )

    assert isinstance(manager, SupplyRouteManager)
    assert isinstance(service, SupplyNetworkService)
    assert endpoint.location_type == "landing_pad"
    assert LogisticsPort is not None
