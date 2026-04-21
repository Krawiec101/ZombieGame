from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import ui.game_views.pygame_game_view as game_view_module
from contracts.game_state import (
    BaseSnapshot,
    CombatNotificationSnapshot,
    CombatSnapshot,
    GameStateSnapshot,
    LandingPadResourceSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    MissionObjectiveProgressSnapshot,
    RoadSnapshot,
    SupplyRouteEndpointSnapshot,
    SupplyRouteSnapshot,
    SupplyTransportSnapshot,
    UnitCommanderSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)


class _FakeRect:
    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return self.left <= x <= self.right and self.top <= y <= self.bottom


class _FakeFontSurface:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_width(self) -> int:
        return max(8, len(self._text) * 8)

    def get_height(self) -> int:
        return 20


class _FakeFont:
    def render(self, text: str, _antialias: bool, _color: tuple[int, int, int]) -> _FakeFontSurface:
        return _FakeFontSurface(text)


class _FakeScreen:
    def __init__(self) -> None:
        self.fill_calls: list[tuple[int, int, int]] = []
        self.blit_calls: list[tuple[object, tuple[int, int]]] = []

    def fill(self, color: tuple[int, int, int]) -> None:
        self.fill_calls.append(color)

    def blit(self, surface: object, position: tuple[int, int]) -> None:
        self.blit_calls.append((surface, position))

    def get_width(self) -> int:
        return 960

    def get_size(self) -> tuple[int, int]:
        return (960, 640)


class _FakeDraw:
    def __init__(self) -> None:
        self.rect_calls: list[tuple[tuple[int, int, int], _FakeRect]] = []
        self.line_records: list[tuple[tuple[int, int, int], tuple[int, int], tuple[int, int], int]] = []
        self.line_calls = 0
        self.circle_calls = 0

    def rect(
        self,
        _screen: object,
        color: tuple[int, int, int],
        rect: _FakeRect,
        _width: int = 0,
        border_radius: int = 0,
    ) -> None:
        _ = border_radius
        self.rect_calls.append((color, rect))

    def line(
        self,
        _screen: object,
        color: tuple[int, int, int],
        start_pos: tuple[int, int],
        end_pos: tuple[int, int],
        width: int = 1,
    ) -> None:
        self.line_records.append((color, start_pos, end_pos, width))
        self.line_calls += 1

    def circle(
        self,
        _screen: object,
        _color: tuple[int, int, int],
        _center: tuple[int, int],
        _radius: int,
        _width: int = 0,
    ) -> None:
        self.circle_calls += 1


class _FakeMouse:
    def __init__(self) -> None:
        self.position = (0, 0)

    def get_pos(self) -> tuple[int, int]:
        return self.position


class _FakeSurface:
    def __init__(self, size: tuple[int, int], flags: int | None = None) -> None:
        self.size = size
        self.flags = flags
        self.fill_calls: list[tuple[int, int, int, int]] = []

    def fill(self, color: tuple[int, int, int, int]) -> None:
        self.fill_calls.append(color)


class _FakePygame:
    SRCALPHA = 100

    def __init__(self) -> None:
        self.draw = _FakeDraw()
        self.mouse = _FakeMouse()
        self.surfaces: list[_FakeSurface] = []

    def Rect(self, left: int, top: int, width: int, height: int) -> _FakeRect:
        return _FakeRect(left, top, width, height)

    def Surface(self, size: tuple[int, int], flags: int | None = None) -> _FakeSurface:
        surface = _FakeSurface(size, flags)
        self.surfaces.append(surface)
        return surface


def _sample_game_state(
    *,
    objective_completed: bool = False,
    combat_active: bool = False,
    notification_phase: str | None = None,
) -> GameStateSnapshot:
    return GameStateSnapshot(
        map_objects=(
            MapObjectSnapshot(object_id="hq", bounds=(160, 200, 244, 256)),
            MapObjectSnapshot(object_id="landing_pad", bounds=(700, 170, 772, 218)),
            MapObjectSnapshot(object_id="recon_site_1", bounds=(396, 118, 454, 162)),
        ),
        roads=(
            RoadSnapshot(
                road_id="main_supply_road",
                points=((202.0, 228.0), (312.0, 340.0), (486.0, 316.0), (620.0, 250.0), (736.0, 194.0)),
            ),
        ),
        units=(
            UnitSnapshot(
                unit_id="alpha_infantry",
                unit_type_id="infantry_squad",
                position=(210.0, 238.0),
                target=None,
                marker_size_px=18,
                name="1. Druzyna Alfa",
                commander=UnitCommanderSnapshot(name="sier. Anna Sowa", experience_level="basic"),
                experience_level="basic",
                personnel=10,
                armament_key="game.unit.armament.rifles_lmg",
                attack=4,
                defense=5,
                morale=72,
                ammo=90,
                rations=18,
                fuel=0,
                can_transport_supplies=False,
                supply_capacity=0,
                carried_supply_total=0,
                active_supply_route_id=None,
                is_in_combat=False,
                combat_seconds_remaining=None,
            ),
            UnitSnapshot(
                unit_id="bravo_mechanized",
                unit_type_id="mechanized_squad",
                position=(250.0, 238.0),
                target=None,
                marker_size_px=20,
                name="2. Sekcja Bravo",
                commander=UnitCommanderSnapshot(name="sier. Marek Wolny", experience_level="basic"),
                experience_level="basic",
                personnel=8,
                armament_key="game.unit.armament.apc_autocannon",
                attack=7,
                defense=8,
                morale=81,
                ammo=120,
                rations=24,
                fuel=65,
                can_transport_supplies=True,
                supply_capacity=24,
                carried_supply_total=0,
                active_supply_route_id="bravo_mechanized:landing_pad->hq",
                is_in_combat=combat_active,
                combat_seconds_remaining=32 if combat_active else None,
            ),
        ),
        enemy_groups=(
            ZombieGroupSnapshot(
                group_id="zulu_zombies",
                position=(736.0, 194.0),
                marker_size_px=22,
                name="Mala grupa zombie",
                personnel=7,
                is_in_combat=combat_active,
            ),
        ),
        selected_unit_id="alpha_infantry",
        objective_definitions=(
            MissionObjectiveDefinitionSnapshot(
                objective_id="landing_pad_cleared",
                description_key="mission.objective.landing_pad_cleared",
            ),
            MissionObjectiveDefinitionSnapshot(
                objective_id="supply_route_to_hq",
                description_key="mission.objective.supply_route_to_hq",
            ),
            MissionObjectiveDefinitionSnapshot(
                objective_id="find_first_missing_detachment",
                description_key="mission.objective.find_first_missing_detachment",
            ),
            MissionObjectiveDefinitionSnapshot(
                objective_id="find_second_missing_detachment",
                description_key="mission.objective.find_second_missing_detachment",
            ),
        ),
        objective_progress=(
            MissionObjectiveProgressSnapshot(
                objective_id="landing_pad_cleared",
                completed=objective_completed,
            ),
            MissionObjectiveProgressSnapshot(
                objective_id="supply_route_to_hq",
                completed=False,
            ),
            MissionObjectiveProgressSnapshot(
                objective_id="find_first_missing_detachment",
                completed=False,
            ),
            MissionObjectiveProgressSnapshot(
                objective_id="find_second_missing_detachment",
                completed=False,
            ),
        ),
        landing_pads=(
            LandingPadSnapshot(
                object_id="landing_pad",
                pad_size="small",
                is_secured=True,
                capacity=90,
                total_stored=30,
                next_transport_seconds=45,
                active_transport_type_id="light_supply_helicopter",
                active_transport_phase="inbound",
                active_transport_seconds_remaining=4,
                resources=(
                    LandingPadResourceSnapshot(resource_id="fuel", amount=12),
                    LandingPadResourceSnapshot(resource_id="mre", amount=8),
                    LandingPadResourceSnapshot(resource_id="ammo", amount=10),
                ),
            ),
        ),
        bases=(
            BaseSnapshot(
                object_id="hq",
                capacity=120,
                total_stored=24,
                resources=(
                    LandingPadResourceSnapshot(resource_id="fuel", amount=12),
                    LandingPadResourceSnapshot(resource_id="mre", amount=6),
                    LandingPadResourceSnapshot(resource_id="ammo", amount=6),
                ),
            ),
        ),
        supply_route_endpoints=(
            SupplyRouteEndpointSnapshot(
                object_id="hq",
                location_type="base",
                can_dispatch_supplies=False,
                can_receive_supplies=True,
                is_active=True,
            ),
            SupplyRouteEndpointSnapshot(
                object_id="landing_pad",
                location_type="landing_pad",
                can_dispatch_supplies=True,
                can_receive_supplies=False,
                is_active=True,
            ),
        ),
        supply_transports=(
            SupplyTransportSnapshot(
                transport_id="landing_pad_supply",
                transport_type_id="light_supply_helicopter",
                phase="inbound",
                position=(804.0, 122.0),
                target_object_id="landing_pad",
            ),
        ),
        supply_routes=(
            SupplyRouteSnapshot(
                route_id="bravo_mechanized:landing_pad->hq",
                unit_id="bravo_mechanized",
                source_object_id="landing_pad",
                destination_object_id="hq",
                phase="to_dropoff",
                carried_total=12,
                capacity=24,
            ),
        ),
        combats=(
            CombatSnapshot(
                combat_id="bravo_mechanized:zulu_zombies",
                unit_id="bravo_mechanized",
                unit_name="2. Sekcja Bravo",
                enemy_group_id="zulu_zombies",
                enemy_group_name="Mala grupa zombie",
                seconds_remaining=32,
            ),
        )
        if combat_active
        else (),
        combat_notifications=(
            CombatNotificationSnapshot(
                notification_id=f"bravo_mechanized:zulu_zombies:{notification_phase}",
                unit_name="2. Sekcja Bravo",
                enemy_group_name="Mala grupa zombie",
                phase=notification_phase,
                seconds_remaining=12,
            ),
        )
        if notification_phase is not None
        else (),
    )


def _replace_landing_pad(state: GameStateSnapshot, **changes) -> LandingPadSnapshot:
    return replace(state.landing_pads[0], **changes)


def _blitted_texts(screen: _FakeScreen) -> list[str]:
    return [surface._text for surface, _position in screen.blit_calls if hasattr(surface, "_text")]


@pytest.fixture
def game_view(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(game_view_module, "text", lambda key, **kwargs: key)
    fake_pygame = _FakePygame()
    fake_screen = _FakeScreen()
    view = game_view_module.PygameGameView(
        pygame_module=fake_pygame,
        screen=fake_screen,
        font_title=_FakeFont(),
        font_menu=_FakeFont(),
        font_hint=_FakeFont(),
    )
    return SimpleNamespace(view=view, pygame=fake_pygame, screen=fake_screen)


def test_render_uses_fullscreen_map_area(game_view) -> None:
    game_view.view.render(character_name="", show_running_hint=False)

    map_rects = [rect for color, rect in game_view.pygame.draw.rect_calls if color == (23, 38, 45)]
    assert map_rects
    map_rect = map_rects[0]
    assert map_rect.left == 0
    assert map_rect.top == 0
    assert map_rect.width == 960
    assert map_rect.height == 640


def test_apply_game_state_updates_cached_state(game_view) -> None:
    state = _sample_game_state(combat_active=True, notification_phase="started")

    game_view.view.apply_game_state(snapshot=state)

    assert {obj.object_id for obj in game_view.view._map_objects} == {"hq", "landing_pad", "recon_site_1"}
    assert [road.road_id for road in game_view.view._roads] == ["main_supply_road"]
    assert set(game_view.view._bases) == {"hq"}
    assert set(game_view.view._landing_pads) == {"landing_pad"}
    assert [route.route_id for route in game_view.view._supply_routes] == ["bravo_mechanized:landing_pad->hq"]
    assert [transport.transport_id for transport in game_view.view._supply_transports] == ["landing_pad_supply"]
    assert {unit.unit_type_id for unit in game_view.view._units} == {
        "infantry_squad",
        "mechanized_squad",
    }
    assert [enemy_group.group_id for enemy_group in game_view.view._enemy_groups] == ["zulu_zombies"]
    assert [combat.combat_id for combat in game_view.view._combats] == ["bravo_mechanized:zulu_zombies"]
    assert [notification.phase for notification in game_view.view._combat_notifications] == ["started"]
    assert game_view.view._selected_unit_id == "alpha_infantry"


def test_render_draws_mission_objectives_panel(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "mission.objectives.title" in texts
    assert "[ ] mission.objective.supply_route_to_hq" in texts
    assert "[ ] mission.objective.find_first_missing_detachment" in texts


def test_render_draws_strikethrough_for_completed_objective(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(objective_completed=True))
    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "[x] mission.objective.landing_pad_cleared" in texts
    assert game_view.pygame.draw.line_calls >= 1


def test_render_shows_tooltip_for_hovered_object(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (170, 210)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" in texts
    assert "game.map.object.hq.description" in texts
    assert "game.map.object.hq.capacity" in texts
    assert "game.map.object.hq.resource_line" in texts


def test_render_shows_landing_pad_supply_details_in_tooltip(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (710, 180)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.landing_pad.name" in texts
    assert "game.map.object.landing_pad.status.inbound" in texts
    assert "game.map.object.landing_pad.capacity" in texts
    assert "game.map.object.landing_pad.resource_line" in texts


def test_render_shows_recon_site_tooltip_when_hovered(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (400, 130)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.recon_site.name" in texts
    assert "game.map.object.recon_site.description" in texts


def test_render_shows_unit_tooltip_when_hovering_over_unit(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (210, 238)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "1. Druzyna Alfa" in texts
    assert "game.unit.type.infantry_squad" in texts
    assert "game.unit.commander" in texts
    assert "game.unit.experience" in texts
    assert "game.unit.morale" in texts
    assert "game.unit.ammo" in texts
    assert "game.map.object.hq.name" not in texts


def test_render_shows_enemy_group_tooltip_when_hovering_over_zombies(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (736, 194)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "Mala grupa zombie" in texts
    assert "game.enemy_group.type.zombies" in texts
    assert "game.enemy_group.personnel" in texts
    assert "game.map.object.landing_pad.name" not in texts


def test_render_draws_supply_transport_marker(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(character_name="", show_running_hint=False)

    helicopter_rects = [
        rect
        for color, rect in game_view.pygame.draw.rect_calls
        if color == (167, 196, 142)
    ]
    assert helicopter_rects
    assert helicopter_rects[0].width == 30
    assert helicopter_rects[0].height == 12


def test_render_draws_enemy_group_marker(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(character_name="", show_running_hint=False)

    enemy_rects = [rect for color, rect in game_view.pygame.draw.rect_calls if color == (146, 74, 74)]
    assert enemy_rects
    assert enemy_rects[0].width == 22
    assert enemy_rects[0].height == 22


def test_render_draws_combat_alert_panel_in_corner(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(combat_active=True, notification_phase="started"))

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.combat.alert.header" in texts
    assert "2. Sekcja Bravo" in texts
    assert "game.combat.alert.action.started" in texts


def test_render_draws_combat_end_alert_panel_in_corner(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(notification_phase="ended"))

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.combat.alert.header" in texts
    assert "2. Sekcja Bravo" in texts
    assert "game.combat.alert.action.ended" in texts


def test_render_marks_unit_that_is_currently_in_combat(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(combat_active=True))

    game_view.view.render(character_name="", show_running_hint=False)

    combat_rects = [rect for color, rect in game_view.pygame.draw.rect_calls if color == (214, 124, 74)]
    assert combat_rects
    assert combat_rects[0].width > 20


def test_render_draws_supply_route_marker(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(character_name="", show_running_hint=False)

    assert game_view.pygame.draw.line_calls >= 4
    assert game_view.pygame.draw.circle_calls >= 2


def test_render_draws_supply_route_along_road_polyline(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(character_name="", show_running_hint=False)

    route_segments = [
        record
        for record in game_view.pygame.draw.line_records
        if record[0] == (216, 182, 104) and record[3] == 4
    ]

    assert len(route_segments) == 4
    assert any(start[1] != end[1] for _color, start, end, _width in route_segments)
    assert route_segments[0][1] == (736, 194)
    assert route_segments[-1][2] == (202, 228)


def test_render_draws_curved_road_segments(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(character_name="", show_running_hint=False)

    road_segments = [
        record
        for record in game_view.pygame.draw.line_records
        if record[0] == (86, 74, 62) and record[3] == 14
    ]
    assert road_segments
    assert any(start[1] != end[1] for _color, start, end, _width in road_segments)


def test_render_shows_outbound_transport_status_in_tooltip(game_view) -> None:
    state = _sample_game_state()
    outbound_landing_pad = _replace_landing_pad(
        state,
        next_transport_seconds=None,
        active_transport_type_id="light_supply_helicopter",
        active_transport_phase="outbound",
        active_transport_seconds_remaining=6,
    )
    outbound_transport = state.supply_transports[0].__class__(
        transport_id=state.supply_transports[0].transport_id,
        transport_type_id=state.supply_transports[0].transport_type_id,
        phase="outbound",
        position=state.supply_transports[0].position,
        target_object_id=state.supply_transports[0].target_object_id,
    )
    game_view.view.apply_game_state(
        snapshot=GameStateSnapshot(
            map_objects=state.map_objects,
            units=state.units,
            selected_unit_id=state.selected_unit_id,
            objective_definitions=state.objective_definitions,
            objective_progress=state.objective_progress,
            landing_pads=(outbound_landing_pad,),
            supply_transports=(outbound_transport,),
        )
    )
    game_view.pygame.mouse.position = (710, 180)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.landing_pad.status.outbound" in texts


@pytest.mark.parametrize(
    ("landing_pad", "expected_status_key"),
    [
        (
            {
                "is_secured": False,
            },
            "game.map.object.landing_pad.status.unsecured",
        ),
        (
            {
                "next_transport_seconds": None,
                "active_transport_phase": "unloading",
                "active_transport_seconds_remaining": 3,
            },
            "game.map.object.landing_pad.status.unloading",
        ),
        (
            {
                "active_transport_phase": None,
                "active_transport_type_id": None,
                "active_transport_seconds_remaining": None,
                "total_stored": 90,
                "next_transport_seconds": None,
            },
            "game.map.object.landing_pad.status.full",
        ),
        (
            {
                "active_transport_phase": None,
                "active_transport_type_id": None,
                "active_transport_seconds_remaining": None,
                "next_transport_seconds": 45,
            },
            "game.map.object.landing_pad.status.next_transport",
        ),
        (
            {
                "active_transport_phase": None,
                "active_transport_type_id": None,
                "active_transport_seconds_remaining": None,
                "next_transport_seconds": None,
            },
            "game.map.object.landing_pad.status.awaiting",
        ),
    ],
)
def test_landing_pad_status_line_selects_expected_status(game_view, landing_pad, expected_status_key) -> None:
    state = _sample_game_state()

    status = game_view.view._landing_pad_status_line(_replace_landing_pad(state, **landing_pad))

    assert status == expected_status_key


def test_render_hides_tooltip_when_mouse_is_outside_objects(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())
    game_view.pygame.mouse.position = (8, 8)

    game_view.view.render(character_name="", show_running_hint=False)

    texts = _blitted_texts(game_view.screen)
    assert "game.map.object.hq.name" not in texts
    assert "game.map.object.hq.description" not in texts


def test_clear_game_state_clears_cached_state(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state(combat_active=True, notification_phase="started"))
    assert game_view.view._map_objects
    assert game_view.view._roads

    game_view.view.clear_game_state()

    assert game_view.view._map_objects == []
    assert game_view.view._roads == []
    assert game_view.view._bases == {}
    assert game_view.view._landing_pads == {}
    assert game_view.view._supply_routes == []
    assert game_view.view._supply_transports == []
    assert game_view.view._units == []
    assert game_view.view._enemy_groups == []
    assert game_view.view._combats == []
    assert game_view.view._combat_notifications == []
    assert game_view.view._selected_unit_id is None


def test_selected_unit_can_create_supply_route_reflects_snapshot_flags(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    assert game_view.view.selected_unit_can_create_supply_route() is False
    assert game_view.view.selected_unit_contains_point((210, 238)) is True
    assert game_view.view.selected_unit_contains_point((250, 238)) is False
    assert game_view.view.selected_unit() is not None
    assert game_view.view.map_object_at((710, 180)).object_id == "landing_pad"
    assert game_view.view.map_object_at((10, 10)) is None
    assert game_view.view.supply_route_source_candidates() == ("landing_pad",)
    assert game_view.view.supply_route_destination_candidates(source_object_id="landing_pad") == ("hq",)
    assert game_view.view.supply_route_destination_candidates(source_object_id="hq") == ()


def test_supply_route_candidates_use_generic_endpoint_capabilities(game_view) -> None:
    state = _sample_game_state()
    generic_state = replace(
        state,
        supply_route_endpoints=state.supply_route_endpoints
        + (
            SupplyRouteEndpointSnapshot(
                object_id="field_depot",
                location_type="field_depot",
                can_dispatch_supplies=True,
                can_receive_supplies=True,
                is_active=True,
            ),
        ),
    )

    game_view.view.apply_game_state(snapshot=generic_state)

    assert game_view.view.supply_route_source_candidates() == ("field_depot", "landing_pad")
    assert game_view.view.supply_route_destination_candidates(source_object_id="landing_pad") == (
        "field_depot",
        "hq",
    )
    assert game_view.view.supply_route_destination_candidates(source_object_id="field_depot") == ("hq",)


def test_selected_unit_can_create_supply_route_only_for_mechanized_unit(game_view) -> None:
    state = _sample_game_state()
    mechanized_unit = state.units[1].__class__(
        unit_id=state.units[1].unit_id,
        unit_type_id=state.units[1].unit_type_id,
        position=state.units[1].position,
        target=state.units[1].target,
        marker_size_px=state.units[1].marker_size_px,
        can_transport_supplies=True,
        supply_capacity=24,
        carried_supply_total=0,
        active_supply_route_id=None,
    )
    mechanized_selected = GameStateSnapshot(
        map_objects=state.map_objects,
        units=(state.units[0], mechanized_unit),
        selected_unit_id="bravo_mechanized",
        objective_definitions=state.objective_definitions,
        objective_progress=state.objective_progress,
        landing_pads=state.landing_pads,
        bases=state.bases,
        supply_transports=state.supply_transports,
        supply_routes=(),
    )
    game_view.view.apply_game_state(snapshot=mechanized_selected)

    assert game_view.view.selected_unit_can_create_supply_route() is True


def test_selected_unit_can_create_supply_route_uses_transport_flag_not_unit_type(game_view) -> None:
    state = _sample_game_state()
    transport_capable_infantry = state.units[0].__class__(
        unit_id=state.units[0].unit_id,
        unit_type_id=state.units[0].unit_type_id,
        position=state.units[0].position,
        target=state.units[0].target,
        marker_size_px=state.units[0].marker_size_px,
        can_transport_supplies=True,
        supply_capacity=24,
        carried_supply_total=0,
        active_supply_route_id=None,
    )
    infantry_selected = GameStateSnapshot(
        map_objects=state.map_objects,
        units=(transport_capable_infantry, state.units[1]),
        selected_unit_id="alpha_infantry",
        objective_definitions=state.objective_definitions,
        objective_progress=state.objective_progress,
        landing_pads=state.landing_pads,
        bases=state.bases,
        supply_transports=state.supply_transports,
        supply_routes=(),
    )
    game_view.view.apply_game_state(snapshot=infantry_selected)

    assert game_view.view.selected_unit_can_create_supply_route() is True


def test_render_draws_supply_route_planning_overlay(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(
        character_name="",
        show_running_hint=False,
        supply_route_planning={
            "candidate_ids": ("landing_pad",),
            "instruction_key": "game.supply_route.planning.pickup",
            "chosen_source_id": None,
        },
    )

    assert game_view.pygame.surfaces
    assert game_view.pygame.surfaces[-1].fill_calls[-1] == (7, 11, 18, 138)
    assert "game.supply_route.planning.pickup" in _blitted_texts(game_view.screen)


def test_render_supply_route_planning_overlay_highlights_selected_source(game_view) -> None:
    game_view.view.apply_game_state(snapshot=_sample_game_state())

    game_view.view.render(
        character_name="",
        show_running_hint=False,
        supply_route_planning={
            "candidate_ids": ("hq",),
            "instruction_key": "game.supply_route.planning.dropoff",
            "chosen_source_id": "hq",
        },
    )

    highlighted_rects = [color for color, _rect in game_view.pygame.draw.rect_calls if color == (168, 134, 74)]
    assert highlighted_rects
    assert "game.supply_route.planning.dropoff" in _blitted_texts(game_view.screen)
