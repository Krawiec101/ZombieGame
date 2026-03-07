from __future__ import annotations

try:
    from contracts.events import ExitRequested, LoadGameRequested, NewGameRequested, UIEvent
except ModuleNotFoundError:
    from src.contracts.events import ExitRequested, LoadGameRequested, NewGameRequested, UIEvent


# Backward-compatible alias. New code should use contracts.events.UIEvent directly.
Order = UIEvent

__all__ = ["Order", "NewGameRequested", "LoadGameRequested", "ExitRequested"]
