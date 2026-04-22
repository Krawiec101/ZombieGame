from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from contracts.game_state import (
    BaseSnapshot,
    LandingPadSnapshot,
    MapObjectSnapshot,
    MissionObjectiveDefinitionSnapshot,
    UnitSnapshot,
    ZombieGroupSnapshot,
)

type TextResolver = Callable[..., str]

@dataclass(frozen=True)
class MissionObjectiveLine:
    text: str
    is_completed: bool
    color: tuple[int, int, int]


@dataclass(frozen=True)
class TooltipContent:
    title: str
    description: str
    detail_lines: tuple[str, ...]


_MAP_OBJECT_TEXT_KEYS: dict[str, tuple[str, str]] = {
    "hq": ("game.map.object.hq.name", "game.map.object.hq.description"),
    "landing_pad": ("game.map.object.landing_pad.name", "game.map.object.landing_pad.description"),
}
_UNIT_TYPE_TEXT_KEYS = {
    "infantry_squad": "game.unit.type.infantry_squad",
    "mechanized_squad": "game.unit.type.mechanized_squad",
}
_LANDING_PAD_SIZE_TEXT_KEYS = {
    "small": "game.map.object.landing_pad.size.small",
    "large": "game.map.object.landing_pad.size.large",
}
_RESOURCE_TEXT_KEYS = {
    "fuel": "resource.fuel",
    "mre": "resource.mre",
    "ammo": "resource.ammo",
}
_TRANSPORT_TYPE_TEXT_KEYS = {
    "light_supply_helicopter": "game.transport.type.light_supply_helicopter",
    "heavy_supply_helicopter": "game.transport.type.heavy_supply_helicopter",
}
_LANDING_PAD_TRANSPORT_STATUS_TEXT_KEYS = {
    "inbound": "game.map.object.landing_pad.status.inbound",
    "unloading": "game.map.object.landing_pad.status.unloading",
    "outbound": "game.map.object.landing_pad.status.outbound",
}
_RECON_SITE_TEXT_KEYS = ("game.map.object.recon_site.name", "game.map.object.recon_site.description")


def build_mission_objective_lines(
    objectives: tuple[MissionObjectiveDefinitionSnapshot, ...],
    objective_status: dict[str, bool],
    *,
    text: TextResolver,
) -> tuple[MissionObjectiveLine, ...]:
    lines: list[MissionObjectiveLine] = []
    for objective in objectives:
        is_completed = objective_status.get(objective.objective_id, False)
        checkbox = "[x]" if is_completed else "[ ]"
        line_color = (142, 150, 160) if is_completed else (212, 222, 232)
        lines.append(
            MissionObjectiveLine(
                text=f"{checkbox} {text(objective.description_key)}",
                is_completed=is_completed,
                color=line_color,
            )
        )
    return tuple(lines)


def map_object_text_keys(object_id: str) -> tuple[str, str] | None:
    if object_id.startswith("recon_site_"):
        return _RECON_SITE_TEXT_KEYS
    return _MAP_OBJECT_TEXT_KEYS.get(object_id)


def build_map_object_tooltip(
    map_object: MapObjectSnapshot,
    *,
    landing_pad: LandingPadSnapshot | None,
    base: BaseSnapshot | None,
    text: TextResolver,
) -> TooltipContent | None:
    keys = map_object_text_keys(map_object.object_id)
    if keys is None:
        return None

    detail_lines: tuple[str, ...] = ()
    if landing_pad is not None:
        detail_lines = landing_pad_detail_lines(landing_pad, text=text)
    elif base is not None:
        detail_lines = base_detail_lines(base, text=text)

    return TooltipContent(
        title=text(keys[0]),
        description=text(keys[1]),
        detail_lines=detail_lines,
    )


def build_unit_tooltip(unit: UnitSnapshot, *, text: TextResolver) -> TooltipContent:
    combat_details = combat_detail_lines_for_unit(unit, text=text)
    return TooltipContent(
        title=unit.name or unit.unit_id,
        description=text(_UNIT_TYPE_TEXT_KEYS.get(unit.unit_type_id, "game.unit.type.unknown")),
        detail_lines=(
            *combat_details,
            text(
                "game.unit.commander",
                name=unit.commander.name,
                experience=text(f"game.experience.{unit.commander.experience_level}"),
            ),
            text(
                "game.unit.experience",
                experience=text(f"game.experience.{unit.experience_level}"),
            ),
            text("game.unit.personnel", value=unit.personnel),
            text("game.unit.armament", value=text(unit.armament_key)),
            text("game.unit.attack", value=unit.attack),
            text("game.unit.defense", value=unit.defense),
            text("game.unit.morale", value=unit.morale),
            text("game.unit.ammo", value=unit.ammo),
            text("game.unit.rations", value=unit.rations),
            text("game.unit.fuel", value=unit.fuel),
        ),
    )


def build_enemy_group_tooltip(enemy_group: ZombieGroupSnapshot, *, text: TextResolver) -> TooltipContent:
    return TooltipContent(
        title=enemy_group.name or enemy_group.group_id,
        description=text("game.enemy_group.type.zombies"),
        detail_lines=(
            text("game.enemy_group.status.engaged")
            if enemy_group.is_in_combat
            else text("game.enemy_group.status.idle"),
            text("game.enemy_group.personnel", value=enemy_group.personnel),
        ),
    )


def combat_detail_lines_for_unit(unit: UnitSnapshot, *, text: TextResolver) -> tuple[str, ...]:
    if not unit.is_in_combat:
        return ()
    return (
        text(
            "game.unit.status.engaged",
            seconds=unit.combat_seconds_remaining or 0,
        ),
    )


def base_detail_lines(base: BaseSnapshot, *, text: TextResolver) -> tuple[str, ...]:
    lines = [
        text("game.map.object.hq.status"),
        text(
            "game.map.object.hq.capacity",
            stored=base.total_stored,
            capacity=base.capacity,
        ),
    ]
    for resource in base.resources:
        lines.append(
            text(
                "game.map.object.hq.resource_line",
                label=text(_RESOURCE_TEXT_KEYS.get(resource.resource_id, resource.resource_id)),
                amount=resource.amount,
            )
        )
    return tuple(lines)


def landing_pad_detail_lines(landing_pad: LandingPadSnapshot, *, text: TextResolver) -> tuple[str, ...]:
    lines = [
        landing_pad_status_line(landing_pad, text=text),
        text(
            "game.map.object.landing_pad.size",
            size=text(
                _LANDING_PAD_SIZE_TEXT_KEYS.get(
                    landing_pad.pad_size,
                    "game.map.object.landing_pad.size.small",
                )
            ),
        ),
        text(
            "game.map.object.landing_pad.capacity",
            stored=landing_pad.total_stored,
            capacity=landing_pad.capacity,
        ),
    ]
    for resource in landing_pad.resources:
        lines.append(
            text(
                "game.map.object.landing_pad.resource_line",
                label=text(_RESOURCE_TEXT_KEYS.get(resource.resource_id, resource.resource_id)),
                amount=resource.amount,
            )
        )
    return tuple(lines)


def landing_pad_status_line(landing_pad: LandingPadSnapshot, *, text: TextResolver) -> str:
    if not landing_pad.is_secured:
        return text("game.map.object.landing_pad.status.unsecured")

    transport_phase = landing_pad.active_transport_phase
    transport_status_key = (
        _LANDING_PAD_TRANSPORT_STATUS_TEXT_KEYS.get(transport_phase) if transport_phase is not None else None
    )
    if transport_status_key is not None:
        return text(
            transport_status_key,
            helicopter=transport_type_label(landing_pad.active_transport_type_id, text=text),
            seconds=landing_pad.active_transport_seconds_remaining or 0,
        )

    if landing_pad.total_stored >= landing_pad.capacity:
        return text("game.map.object.landing_pad.status.full")

    if landing_pad.next_transport_seconds is not None:
        return text(
            "game.map.object.landing_pad.status.next_transport",
            seconds=landing_pad.next_transport_seconds,
        )

    return text("game.map.object.landing_pad.status.awaiting")


def transport_type_label(transport_type_id: str | None, *, text: TextResolver) -> str:
    if transport_type_id is None:
        return text("game.transport.type.unknown")
    return text(_TRANSPORT_TYPE_TEXT_KEYS.get(transport_type_id, "game.transport.type.unknown"))
