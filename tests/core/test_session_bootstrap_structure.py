from __future__ import annotations

from core.model.units import ReinforcementTemplate
from core.session_bootstrap import (
    SessionBootstrapper,
    SessionBootstrapState,
    commander_state_from_config,
    reinforcement_templates_from_config,
)


def test_session_bootstrap_module_exposes_runtime_construction_primitives() -> None:
    commander = commander_state_from_config({"name": "sier. Ada", "rank": "sergeant"})
    templates = reinforcement_templates_from_config(
        (
            {
                "unit_id": "alpha",
                "unit_type_id": "infantry_squad",
                "name": "Alpha",
                "commander": {"name": "sier. Ada"},
            },
        )
    )
    bootstrapper = SessionBootstrapper()
    state = SessionBootstrapState(units=[], enemy_groups=[])

    assert commander.rank == "sergeant"
    assert templates == (
        ReinforcementTemplate(
            unit_id="alpha",
            unit_type_id="infantry_squad",
            name="Alpha",
            commander=commander_state_from_config({"name": "sier. Ada"}),
        ),
    )
    assert isinstance(bootstrapper, SessionBootstrapper)
    assert state.units == []
