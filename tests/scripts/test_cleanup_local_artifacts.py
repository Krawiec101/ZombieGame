from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def find_script_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "cleanup_local_artifacts.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate scripts/cleanup_local_artifacts.py")


SCRIPT_PATH = find_script_path()
SCRIPT_SPEC = importlib.util.spec_from_file_location("cleanup_local_artifacts", SCRIPT_PATH)
assert SCRIPT_SPEC is not None
assert SCRIPT_SPEC.loader is not None
CLEANUP = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = CLEANUP
SCRIPT_SPEC.loader.exec_module(CLEANUP)


def test_collect_cleanup_targets_finds_known_artifacts_and_skips_virtualenv(tmp_path: Path) -> None:
    tracked_paths = [
        tmp_path / "src" / "__pycache__",
        tmp_path / "tests" / "unit" / "__pycache__",
        tmp_path / ".pytest_cache",
        tmp_path / ".ruff_cache",
        tmp_path / ".tmp-pip-audit",
        tmp_path / "pytest-temp-run-1",
    ]
    for path in tracked_paths:
        path.mkdir(parents=True)

    (tmp_path / "coverage.xml").write_text("", encoding="utf-8")
    (tmp_path / "mutmut-results.txt").write_text("", encoding="utf-8")

    ignored_path = tmp_path / ".venv" / "Lib" / "site-packages" / "__pycache__"
    ignored_path.mkdir(parents=True)

    targets = CLEANUP.collect_cleanup_targets(tmp_path)
    relative_targets = {path.relative_to(tmp_path).as_posix() for path in targets}

    assert "src/__pycache__" in relative_targets
    assert "tests/unit/__pycache__" in relative_targets
    assert ".pytest_cache" in relative_targets
    assert ".ruff_cache" in relative_targets
    assert ".tmp-pip-audit" in relative_targets
    assert "pytest-temp-run-1" in relative_targets
    assert "coverage.xml" in relative_targets
    assert "mutmut-results.txt" in relative_targets
    assert ".venv/Lib/site-packages/__pycache__" not in relative_targets


def test_cli_dry_run_lists_targets_without_deleting_them(tmp_path: Path) -> None:
    (tmp_path / "src" / "__pycache__").mkdir(parents=True)
    (tmp_path / "coverage.xml").write_text("", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--root",
            str(tmp_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "src/__pycache__" in result.stdout
    assert "coverage.xml" in result.stdout
    assert (tmp_path / "src" / "__pycache__").exists()
    assert (tmp_path / "coverage.xml").exists()
