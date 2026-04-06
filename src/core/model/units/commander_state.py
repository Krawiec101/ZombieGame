from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommanderState:
    name: str = ""
    experience_level: str = "basic"

