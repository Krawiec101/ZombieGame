from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure top-level imports like `app.*`, `core.*`, `ui.*` resolve from `src/`.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def pytest_configure(config: pytest.Config) -> None:
    config.option.basetemp = config.rootpath / ".test-tmp"
