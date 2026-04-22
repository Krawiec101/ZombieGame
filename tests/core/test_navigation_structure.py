from __future__ import annotations

from core.model.units import UnitState
from core.navigation import NavigationService


def test_navigation_package_exports_service_for_pathing_and_speed() -> None:
    service = NavigationService(
        simulation_seconds_per_tick=8.0,
        map_width_km=20.0,
    )
    unit = UnitState(unit_id="alpha", unit_type_id="infantry_squad", position=(10.0, 10.0))
    roads = ({"id": "road", "points": ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0))},)

    assert service.primary_road_points(roads) == ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0))
    assert service.road_mode_for_unit("mechanized_squad", can_unit_type_create_convoy=lambda _: True) == "prefer"
    assert (
        service.unit_movement_pixels_per_tick(
            unit,
            map_width_px=1000,
            unit_speed_kmph=lambda _: 4.0,
        )
        > 0.0
    )
