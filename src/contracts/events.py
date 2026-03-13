from __future__ import annotations

from dataclasses import dataclass


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
    map_objects: tuple[dict[str, object], ...]
    units: tuple[dict[str, object], ...]
    selected_unit_id: str | None
    objective_definitions: tuple[dict[str, str], ...]
    objective_status: dict[str, bool]


@dataclass(frozen=True)
class UIEventIgnored(DomainEvent):
    pass
