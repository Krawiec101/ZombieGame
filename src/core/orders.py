from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    pass


@dataclass(frozen=True)
class NewGameRequested(Order):
    pass


@dataclass(frozen=True)
class LoadGameRequested(Order):
    pass


@dataclass(frozen=True)
class ExitRequested(Order):
    pass
