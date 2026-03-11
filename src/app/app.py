from __future__ import annotations

try:
    from contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        GameFrameSyncRequested,
        GameLeftClickRequested,
        GameRightClickRequested,
        GameStateSynced,
        LoadGameFlowRouted,
        UIEvent,
        UIEventIgnored,
    )
    from contracts.main_menu_view import MainMenuView
    from core.game_session import GameSession, create_default_game_session
    from core.main_menu import handle_main_menu_ui_event
    from ui.menus.main_menu import create_view
except ModuleNotFoundError:
    from src.contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        GameFrameSyncRequested,
        GameLeftClickRequested,
        GameRightClickRequested,
        GameStateSynced,
        LoadGameFlowRouted,
        UIEvent,
        UIEventIgnored,
    )
    from src.contracts.main_menu_view import MainMenuView
    from src.core.game_session import GameSession, create_default_game_session
    from src.core.main_menu import handle_main_menu_ui_event
    from src.ui.menus.main_menu import create_view


def route_domain_event(event: DomainEvent) -> bool:
    if isinstance(event, (ExitFlowRouted, LoadGameFlowRouted)):
        return False
    return True


def run() -> None:
    game_session = create_default_game_session()
    view = create_view()
    _run_main_menu_loop(view, game_session)


def _sync_game_state(
    game_session: GameSession,
    *,
    width: int,
    height: int,
) -> GameStateSynced:
    game_session.update_map_dimensions(width=width, height=height)
    game_session.tick()
    return GameStateSynced(
        map_objects=tuple(game_session.map_objects_snapshot()),
        units=tuple(game_session.units_snapshot()),
        selected_unit_id=game_session.selected_unit_id(),
        objective_definitions=game_session.objective_definitions_snapshot(),
        objective_status=game_session.objective_status_snapshot(),
    )


def handle_ui_event(
    event: UIEvent,
    *,
    game_session: GameSession,
) -> tuple[DomainEvent, ...]:
    routed_event = handle_main_menu_ui_event(event)
    if not isinstance(routed_event, UIEventIgnored):
        if not isinstance(routed_event, (ExitFlowRouted, LoadGameFlowRouted)):
            game_session.reset()
        return (routed_event,)

    if isinstance(event, GameFrameSyncRequested):
        return (_sync_game_state(game_session, width=event.width, height=event.height),)

    if isinstance(event, GameLeftClickRequested):
        game_session.handle_left_click(event.position)
        return ()

    if isinstance(event, GameRightClickRequested):
        game_session.handle_right_click(event.position)
        return ()

    return (routed_event,)


def _run_main_menu_loop(view: MainMenuView, game_session: GameSession | None = None) -> None:
    active_game_session = game_session if game_session is not None else create_default_game_session()
    keep_running = True
    try:
        while keep_running:
            view.render()
            for ui_event in view.poll_ui_events():
                domain_events = handle_ui_event(ui_event, game_session=active_game_session)
                for domain_event in domain_events:
                    view.handle_domain_event(domain_event)
                    keep_running = route_domain_event(domain_event)
                    if not keep_running:
                        break  # pragma: no mutate
                if not keep_running:
                    break  # pragma: no mutate
    finally:
        view.close()
