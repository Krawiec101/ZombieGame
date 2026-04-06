from __future__ import annotations


SUPPLY_RESOURCE_ORDER = ("fuel", "mre", "ammo")


def empty_resource_store() -> dict[str, int]:
    return {resource_id: 0 for resource_id in SUPPLY_RESOURCE_ORDER}

