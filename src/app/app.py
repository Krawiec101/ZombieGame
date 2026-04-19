from __future__ import annotations

from app.application_loop import run_main_menu_loop
from app.ui_event_handler import (
    handle_ui_event as _handle_ui_event,
)
from app.ui_event_handler import (
    should_keep_running_after as _route_domain_event,
)
from app.ui_event_handler import (
    sync_game_state as _sync_game_state_impl,
)
from contracts.main_menu_view import MainMenuView
from core.game_session import GameSession, create_default_game_session
from ui.menus.main_menu import create_view

route_domain_event = _route_domain_event
handle_ui_event = _handle_ui_event
_sync_game_state = _sync_game_state_impl


def run() -> None:
    game_session = create_default_game_session()
    view = create_view()
    _run_main_menu_loop(view, game_session)


def _run_main_menu_loop(view: MainMenuView, game_session: GameSession | None = None) -> None:
    run_main_menu_loop(
        view,
        game_session=game_session,
        create_default_game_session=create_default_game_session,
        handle_ui_event=lambda event, active_game_session: handle_ui_event(
            event,
            game_session=active_game_session,
        ),
        route_domain_event=route_domain_event,
    )
