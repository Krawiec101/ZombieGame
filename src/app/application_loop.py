from __future__ import annotations

from collections.abc import Callable

from contracts.events import DomainEvent, UIEvent
from contracts.main_menu_view import MainMenuView
from app.ui_event_handler import GameSessionPort

type UIEventHandler = Callable[[UIEvent, GameSessionPort], tuple[DomainEvent, ...]]
type DomainEventRouter = Callable[[DomainEvent], bool]
type GameSessionFactory = Callable[[], GameSessionPort]


def run_main_menu_loop(
    view: MainMenuView,
    *,
    game_session: GameSessionPort | None,
    create_default_game_session: GameSessionFactory,
    handle_ui_event: UIEventHandler,
    route_domain_event: DomainEventRouter,
) -> None:
    active_game_session = game_session if game_session is not None else create_default_game_session()
    keep_running = True
    try:
        while keep_running:
            view.render()
            for ui_event in view.poll_ui_events():
                domain_events = handle_ui_event(ui_event, active_game_session)
                for domain_event in domain_events:
                    view.handle_domain_event(domain_event)
                    keep_running = route_domain_event(domain_event)
                    if not keep_running:
                        break  # pragma: no mutate
                if not keep_running:
                    break  # pragma: no mutate
    finally:
        view.close()
