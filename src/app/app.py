from __future__ import annotations

try:
    from contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        LoadGameFlowRouted,
    )
    from contracts.main_menu_view import MainMenuView
    from core.main_menu import handle_main_menu_ui_event
    from ui.main_menu import create_view
except ModuleNotFoundError:
    from src.contracts.events import (
        DomainEvent,
        ExitFlowRouted,
        LoadGameFlowRouted,
    )
    from src.contracts.main_menu_view import MainMenuView
    from src.core.main_menu import handle_main_menu_ui_event
    from src.ui.main_menu import create_view


def route_domain_event(event: DomainEvent) -> bool:
    if isinstance(event, (ExitFlowRouted, LoadGameFlowRouted)):
        return False
    return True


def run() -> None:
    view = create_view()
    _run_main_menu_loop(view)


def _run_main_menu_loop(view: MainMenuView) -> None:
    keep_running = True
    try:
        while keep_running:
            view.render()
            for ui_event in view.poll_ui_events():
                domain_event = handle_main_menu_ui_event(ui_event)
                view.handle_domain_event(domain_event)
                keep_running = route_domain_event(domain_event)
                if not keep_running:
                    break  # pragma: no mutate
    finally:
        view.close()
