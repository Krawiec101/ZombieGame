from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

# Ensure top-level imports like `app.*`, `core.*`, `ui.*` resolve from `src/`.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is not None:
        return

    configured_tmp_root = os.environ.get("ZOMBIEGAME_TEST_TMP_ROOT")
    tmp_root = Path(configured_tmp_root) if configured_tmp_root else config.rootpath / ".test-tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = tmp_root / f"pytest-{uuid4().hex}"
