from __future__ import annotations

from typing import Protocol

from contracts.events import (
    DomainEvent,
    ExitFlowRouted,
    GameFrameSyncRequested,
    GameLeftClickRequested,
    GameRightClickRequested,
    GameStateSynced,
    GameSupplyRouteRequested,
    NewGameFlowRouted,
    UIEvent,
    UIEventIgnored,
)
from contracts.game_state import GameStateSnapshot
from core.main_menu import handle_main_menu_ui_event


class GameSessionPort(Protocol):
    def reset(self) -> None:
        ...

    def sync_state(self, *, width: int, height: int) -> GameStateSnapshot:
        ...

    def handle_left_click(self, position: tuple[int, int]) -> None:
        ...

    def handle_right_click(self, position: tuple[int, int]) -> None:
        ...

    def handle_supply_route(self, *, source_object_id: str, destination_object_id: str) -> None:
        ...


def should_keep_running_after(event: DomainEvent) -> bool:
    return not isinstance(event, ExitFlowRouted)


def sync_game_state(
    game_session: GameSessionPort,
    *,
    width: int,
    height: int,
) -> GameStateSynced:
    return GameStateSynced(snapshot=game_session.sync_state(width=width, height=height))


def handle_ui_event(
    event: UIEvent,
    *,
    game_session: GameSessionPort,
) -> tuple[DomainEvent, ...]:
    routed_event = handle_main_menu_ui_event(event)
    if not isinstance(routed_event, UIEventIgnored):
        if isinstance(routed_event, NewGameFlowRouted):
            game_session.reset()
        return (routed_event,)

    if isinstance(event, GameFrameSyncRequested):
        return (sync_game_state(game_session, width=event.width, height=event.height),)

    if isinstance(event, GameLeftClickRequested):
        game_session.handle_left_click(event.position)
        return ()

    if isinstance(event, GameRightClickRequested):
        game_session.handle_right_click(event.position)
        return ()

    if isinstance(event, GameSupplyRouteRequested):
        game_session.handle_supply_route(
            source_object_id=event.source_object_id,
            destination_object_id=event.destination_object_id,
        )
        return ()

    return (routed_event,)
