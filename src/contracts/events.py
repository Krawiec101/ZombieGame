from __future__ import annotations

from dataclasses import dataclass

from contracts.game_state import GameStateSnapshot


@dataclass(frozen=True)
class UIEvent:
    pass


@dataclass(frozen=True)
class NewGameRequested(UIEvent):
    pass


@dataclass(frozen=True)
class LoadGameRequested(UIEvent):
    pass


@dataclass(frozen=True)
class ExitRequested(UIEvent):
    pass


@dataclass(frozen=True)
class GameFrameSyncRequested(UIEvent):
    width: int
    height: int


@dataclass(frozen=True)
class GameLeftClickRequested(UIEvent):
    position: tuple[int, int]


@dataclass(frozen=True)
class GameRightClickRequested(UIEvent):
    position: tuple[int, int]


@dataclass(frozen=True)
class GameSupplyRouteRequested(UIEvent):
    source_object_id: str
    destination_object_id: str


@dataclass(frozen=True)
class DomainEvent:
    pass


@dataclass(frozen=True)
class NewGameFlowRouted(DomainEvent):
    pass


@dataclass(frozen=True)
class LoadGameFlowRouted(DomainEvent):
    pass


@dataclass(frozen=True)
class ExitFlowRouted(DomainEvent):
    pass


@dataclass(frozen=True)
class GameStateSynced(DomainEvent):
    snapshot: GameStateSnapshot


@dataclass(frozen=True)
class UIEventIgnored(DomainEvent):
    pass
