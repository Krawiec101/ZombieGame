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
class UIEventIgnored(DomainEvent):
    pass
