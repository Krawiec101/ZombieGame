from __future__ import annotations

from dataclasses import dataclass

from .experience_level import ExperienceLevel


@dataclass(frozen=True)
class CommanderState:
    name: str = ""
    rank: str = ""
    experience_level: str = ExperienceLevel.BASIC
