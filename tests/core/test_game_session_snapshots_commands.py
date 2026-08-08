# ruff: noqa: F403, F405, I001
from tests.core.game_session_support import *

def test_snapshot_exposes_typed_contract_for_ui_sync() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()

    snapshot = session.snapshot()

    assert isinstance(snapshot, GameStateSnapshot)
    assert {map_object.object_id for map_object in snapshot.map_objects} == {
        "hq",
        "landing_pad",
        "recon_site_1",
        "recon_site_2",
        "recon_site_3",
        "recon_site_4",
    }
    assert snapshot.roads == session.roads_snapshot()
    assert {unit.unit_type_id for unit in snapshot.units} == {
        "infantry_squad",
        "mechanized_squad",
    }
    assert snapshot.objective_progress == (
        MissionObjectiveProgressSnapshot(
            objective_id="landing_pad_cleared",
            completed=False,
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
    )
    assert snapshot.landing_pads == (
        LandingPadSnapshot(
            object_id="landing_pad",
            pad_size="small",
            is_secured=False,
            capacity=90,
            total_stored=0,
            next_transport_seconds=None,
            active_transport_type_id=None,
            active_transport_phase=None,
            active_transport_seconds_remaining=None,
            resources=session.snapshot().landing_pads[0].resources,
        ),
    )
    assert snapshot.bases == (
        BaseSnapshot(
            object_id="hq",
            capacity=120,
            total_stored=0,
            resources=session.snapshot().bases[0].resources,
        ),
    )
    assert snapshot.supply_transports == ()
    assert snapshot.supply_routes == ()
    assert snapshot.enemy_groups == (
        ZombieGroupSnapshot(
            group_id="zulu_zombies",
            position=snapshot.enemy_groups[0].position,
            marker_size_px=22,
            name="Mala grupa zombie",
            personnel=7,
        ),
        ZombieGroupSnapshot(
            group_id="echo_zombies",
            position=snapshot.enemy_groups[1].position,
            marker_size_px=22,
            name="Wedrujaca grupa zombie",
            personnel=6,
        ),
    )
    assert snapshot.selected_unit_id is None
    assert snapshot.objective_definitions == (
        session.snapshot().objective_definitions[0].__class__(
            objective_id="landing_pad_cleared",
            description_key="mission.objective.landing_pad_cleared",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="supply_route_to_hq",
            description_key="mission.objective.supply_route_to_hq",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="find_first_missing_detachment",
            description_key="mission.objective.find_first_missing_detachment",
        ),
        session.snapshot().objective_definitions[0].__class__(
            objective_id="find_second_missing_detachment",
            description_key="mission.objective.find_second_missing_detachment",
        ),
    )

def test_snapshot_includes_selected_unit_and_pending_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    snapshot = session.snapshot()

    assert snapshot.selected_unit_id == "alpha_infantry"
    alpha = next(unit for unit in snapshot.units if unit.unit_id == "alpha_infantry")
    assert alpha.target == (840.0, 500.0)
    assert alpha.name == "1. Druzyna Alfa"
    assert alpha.commander == alpha.commander.__class__(
        name="sier. Anna Sowa",
        experience_level="basic",
    )
    assert alpha.experience_level == "basic"
    assert alpha.personnel == 10
    assert alpha.armament_key == "game.unit.armament.rifles_lmg"
    assert alpha.attack == 4
    assert alpha.defense == 5
    assert alpha.morale == 72
    assert alpha.ammo == 90
    assert alpha.rations == 18
    assert alpha.fuel == 0
    assert alpha.marker_size_px == UNIT_TYPE_SPECS["infantry_squad"].marker_size_px

def test_snapshot_returns_value_objects_independent_from_future_session_mutation() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    snapshot_before = session.snapshot()

    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    session.tick()

    snapshot_after = session.snapshot()

    assert snapshot_before != snapshot_after
    alpha_before = next(unit for unit in snapshot_before.units if unit.unit_id == "alpha_infantry")
    alpha_after = next(unit for unit in snapshot_after.units if unit.unit_id == "alpha_infantry")
    assert alpha_before.target is None
    assert alpha_after.target is not None

def test_sync_state_updates_dimensions_ticks_and_returns_snapshot() -> None:
    session = create_default_game_session()

    snapshot = session.sync_state(width=960, height=640)

    assert isinstance(snapshot, GameStateSnapshot)
    assert session._map_size == (960, 640)
    assert snapshot.map_objects
    assert snapshot.units
    assert snapshot == session.snapshot()

def test_left_click_selects_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))

    assert session.selected_unit_id() == "alpha_infantry"

def test_left_click_on_map_issues_order_for_selected_unit() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    assert updated_infantry["target"] is not None

def test_left_click_without_selection_does_not_issue_order() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    initial_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click((840, 500))
    for _ in range(60):
        session.tick()

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert updated_infantry["target"] is None
    assert updated_infantry["position"] == initial_infantry["position"]

def test_right_click_deselects_without_clearing_target() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    target_before = _unit_by_id(session.units_snapshot(), "alpha_infantry")["target"]

    session.handle_right_click((20, 20))

    updated_infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")
    assert session.selected_unit_id() is None
    assert updated_infantry["target"] == target_before

def test_right_click_without_selection_is_noop() -> None:
    session = create_default_game_session()

    session.handle_right_click((20, 20))

    assert session.selected_unit_id() is None

def test_units_snapshot_contains_expected_keys_marker_sizes_and_targets() -> None:
    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    session.tick()
    infantry = _unit_by_id(session.units_snapshot(), "alpha_infantry")

    session.handle_left_click(_unit_center(infantry))
    session.handle_left_click((840, 500))
    units = session.units_snapshot()

    assert units
    for unit in units:
        assert set(unit.keys()) == {
            "unit_id",
            "unit_type_id",
            "position",
            "target",
            "marker_size_px",
            "name",
            "commander",
            "experience_level",
            "personnel",
            "armament_key",
            "attack",
            "defense",
            "morale",
            "ammo",
            "rations",
            "fuel",
            "can_transport_supplies",
            "supply_capacity",
            "carried_supply_total",
            "active_supply_route_id",
            "is_in_combat",
            "combat_seconds_remaining",
        }
        assert unit["marker_size_px"] == UNIT_TYPE_SPECS[unit["unit_type_id"]].marker_size_px

    updated_infantry = _unit_by_id(units, "alpha_infantry")
    assert updated_infantry["target"] == (840.0, 500.0)
    assert updated_infantry["name"] == "1. Druzyna Alfa"
    assert updated_infantry["commander"] == {
        "name": "sier. Anna Sowa",
        "experience_level": "basic",
    }
    assert updated_infantry["experience_level"] == "basic"
    assert updated_infantry["personnel"] == 10
    assert updated_infantry["armament_key"] == "game.unit.armament.rifles_lmg"
    assert updated_infantry["attack"] == 4
    assert updated_infantry["defense"] == 5
    assert updated_infantry["morale"] == 72
    assert updated_infantry["ammo"] == 90
    assert updated_infantry["rations"] == 18
    assert updated_infantry["fuel"] == 0
    assert updated_infantry["is_in_combat"] is False
    assert updated_infantry["combat_seconds_remaining"] is None
    assert updated_infantry["can_transport_supplies"] is False
    assert updated_infantry["supply_capacity"] == 0
    assert updated_infantry["carried_supply_total"] == 0
    assert updated_infantry["active_supply_route_id"] is None

    updated_motorized = _unit_by_id(units, "bravo_mechanized")
    assert updated_motorized["name"] == "2. Sekcja Bravo"
    assert updated_motorized["commander"] == {
        "name": "sier. Marek Wolny",
        "experience_level": "basic",
    }
    assert updated_motorized["experience_level"] == "basic"
    assert updated_motorized["personnel"] == 8
    assert updated_motorized["armament_key"] == "game.unit.armament.apc_autocannon"
    assert updated_motorized["attack"] == 8
    assert updated_motorized["defense"] == 9
    assert updated_motorized["morale"] == 81
    assert updated_motorized["ammo"] == 120
    assert updated_motorized["rations"] == 24
    assert updated_motorized["fuel"] == 65
    assert updated_motorized["can_transport_supplies"] is True
    assert updated_motorized["supply_capacity"] == 24

def test_get_selected_unit_returns_unit_and_keeps_selection_when_found() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "u1"

    selected = session._get_selected_unit()

    assert selected is not None
    assert selected.unit_id == "u1"
    assert session._selected_unit_id == "u1"

def test_get_selected_unit_returns_none_and_clears_invalid_selection() -> None:
    session = create_default_game_session()
    session._units = [
        UnitState(unit_id="u1", unit_type_id="infantry_squad", position=(100.0, 100.0)),
    ]
    session._selected_unit_id = "missing"

    selected = session._get_selected_unit()

    assert selected is None
    assert session._selected_unit_id is None

def test_tick_passes_runtime_snapshots_and_elapsed_times_to_subsystems() -> None:
    class RecordingEvaluator:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def evaluate(self, **kwargs):
            self.calls.append(kwargs)
            return dict(kwargs["current_status"])

    session = create_default_game_session()
    session.update_map_dimensions(width=960, height=640)
    evaluator = RecordingEvaluator()
    session._mission_objectives_evaluator = evaluator
    recorded: dict[str, object] = {}

    session._consume_supply_elapsed_seconds = lambda: 7.5
    session._consume_combat_elapsed_seconds = lambda: 3.25
    session._update_combat_notifications = lambda *, elapsed_seconds: recorded.setdefault(
        "combat_notifications", elapsed_seconds
    )
    session._update_combats = lambda *, elapsed_seconds: recorded.setdefault("combats", elapsed_seconds)
    session._update_units_position = lambda: recorded.setdefault("units_position", True)
    session._start_combats_for_colliding_units = lambda: recorded.setdefault("start_combats", True)
    session._investigate_recon_sites = lambda: recorded.setdefault("investigate_recon_sites", True)
    session._update_main_objective_reports = lambda: recorded.setdefault("main_objective_reports", True)
    session._update_supply_network = lambda *, elapsed_seconds: recorded.setdefault(
        "supply_network", elapsed_seconds
    )
    session._update_supply_routes = lambda *, elapsed_seconds: recorded.setdefault("supply_routes", elapsed_seconds)

    session.tick()

    assert recorded == {
        "combat_notifications": 3.25,
        "combats": 3.25,
        "units_position": True,
        "start_combats": True,
        "investigate_recon_sites": True,
        "main_objective_reports": True,
        "supply_network": 7.5,
        "supply_routes": 7.5,
    }
    assert len(evaluator.calls) == 1
    assert evaluator.calls[0]["units"] == session.units_snapshot()
    assert evaluator.calls[0]["map_objects"] == session.map_objects_snapshot()
    assert evaluator.calls[0]["current_status"] == session.objective_status_snapshot()
    assert evaluator.calls[0]["supply_routes"] == session.supply_routes_state_snapshot()
    assert evaluator.calls[0]["enemy_groups"] == session.enemy_groups_state_snapshot()
    assert evaluator.calls[0]["discovered_reinforcements_count"] == 0

