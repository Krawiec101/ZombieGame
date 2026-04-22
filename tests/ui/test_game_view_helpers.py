from __future__ import annotations

from contracts.game_state import (
    BaseSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    RoadSnapshot,
    SupplyRouteSnapshot,
    UnitCommanderSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)
from ui.game_views.geometry import first_map_object_at, polyline_midpoint, supply_route_points
from ui.game_views.view_content import (
    build_enemy_group_tooltip,
    build_map_object_tooltip,
    build_mission_objective_lines,
    build_unit_tooltip,
    landing_pad_status_line,
    map_object_text_keys,
)


def _text(key: str, /, **_kwargs: object) -> str:
    return key


def test_build_mission_objective_lines_marks_completed_and_pending() -> None:
    lines = build_mission_objective_lines(
        (
            MissionObjectiveDefinitionSnapshot(
                objective_id="o1",
                description_key="objective.first",
            ),
            MissionObjectiveDefinitionSnapshot(
                objective_id="o2",
                description_key="objective.second",
            ),
        ),
        {"o1": True, "o2": False},
        text=_text,
    )

    assert lines[0].text == "[x] objective.first"
    assert lines[0].is_completed is True
    assert lines[1].text == "[ ] objective.second"
    assert lines[1].is_completed is False


def test_build_map_object_tooltip_uses_landing_pad_details() -> None:
    tooltip = build_map_object_tooltip(
        MapObjectSnapshot(object_id="landing_pad", bounds=(1, 2, 3, 4)),
        landing_pad=LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="small",
            is_secured=True,
            capacity=90,
            total_stored=12,
            next_transport_seconds=45,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=(LandingPadResourceSnapshot(resource_id="fuel", amount=12),),
        ),
        base=None,
        text=_text,
    )

    assert tooltip is not None
    assert tooltip.title == "game.map.object.landing_pad.name"
    assert "game.map.object.landing_pad.capacity" in tooltip.detail_lines


def test_build_map_object_tooltip_uses_base_details() -> None:
    tooltip = build_map_object_tooltip(
        MapObjectSnapshot(object_id="hq", bounds=(1, 2, 3, 4)),
        landing_pad=None,
        base=BaseSnapshot(
            object_id="hq",
            capacity=120,
            total_stored=20,
            resources=(LandingPadResourceSnapshot(resource_id="ammo", amount=20),),
        ),
        text=_text,
    )

    assert tooltip is not None
    assert tooltip.title == "game.map.object.hq.name"
    assert "game.map.object.hq.capacity" in tooltip.detail_lines


def test_build_unit_and_enemy_group_tooltips_expose_expected_labels() -> None:
    unit_tooltip = build_unit_tooltip(
        UnitSnapshot(
            unit_id="u1",
            unit_type_id="infantry_squad",
            position=(10.0, 20.0),
            target=None,
            marker_size_px=18,
            name="Alpha",
            commander=UnitCommanderSnapshot(name="Dowodca", experience_level="basic"),
            experience_level="basic",
            personnel=10,
            armament_key="game.unit.armament.rifles_lmg",
            attack=4,
            defense=5,
            morale=70,
            ammo=90,
            rations=10,
            fuel=0,
            is_in_combat=True,
            combat_seconds_remaining=12,
        ),
        text=_text,
    )
    enemy_tooltip = build_enemy_group_tooltip(
        ZombieGroupSnapshot(
            group_id="z1",
            position=(5.0, 6.0),
            marker_size_px=22,
            name="Zombie",
            personnel=7,
            is_in_combat=False,
        ),
        text=_text,
    )

    assert unit_tooltip.description == "game.unit.type.infantry_squad"
    assert "game.unit.commander" in unit_tooltip.detail_lines
    assert enemy_tooltip.description == "game.enemy_group.type.zombies"
    assert "game.enemy_group.personnel" in enemy_tooltip.detail_lines


def test_landing_pad_status_line_prefers_transport_phase_over_timer() -> None:
    status = landing_pad_status_line(
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="small",
            is_secured=True,
            capacity=90,
            total_stored=12,
            next_transport_seconds=45,
            active_transport_type_id="light_supply_helicopter",
            active_transport_phase="inbound",
            active_transport_seconds_remaining=4,
            resources=(),
        ),
        text=_text,
    )

    assert status == "game.map.object.landing_pad.status.inbound"


def test_map_object_text_keys_support_recon_sites() -> None:
    assert map_object_text_keys("recon_site_1") == (
        "game.map.object.recon_site.name",
        "game.map.object.recon_site.description",
    )


def test_supply_route_points_follow_available_road_and_fallback_to_direct_line() -> None:
    route = SupplyRouteSnapshot(
        route_id="r1",
        unit_id="u1",
        source_object_id="landing_pad",
        destination_object_id="hq",
        phase="to_pickup",
        carried_total=0,
        capacity=24,
    )
    map_objects = (
        MapObjectSnapshot(object_id="hq", bounds=(180, 200, 220, 240)),
        MapObjectSnapshot(object_id="landing_pad", bounds=(680, 180, 720, 220)),
    )
    roads = (
        RoadSnapshot(
            road_id="road",
            points=((200.0, 220.0), (400.0, 260.0), (700.0, 200.0)),
        ),
    )

    assert supply_route_points(route, map_objects=map_objects, roads=roads) == (
        (700.0, 200.0),
        (400.0, 260.0),
        (200.0, 220.0),
    )
    assert supply_route_points(route, map_objects=map_objects, roads=()) == (
        (700.0, 200.0),
        (200.0, 220.0),
    )


def test_polyline_midpoint_and_first_map_object_at_cover_edge_cases() -> None:
    assert polyline_midpoint(()) == (0.0, 0.0)
    assert polyline_midpoint(((5.0, 6.0),)) == (5.0, 6.0)
    assert first_map_object_at((50, 50), [MapObjectSnapshot(object_id="hq", bounds=(1, 1, 10, 10))]) is None
