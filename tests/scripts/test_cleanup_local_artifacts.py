from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


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
REAL_RMTREE = shutil.rmtree


@contextmanager
def workspace_tmp_dir() -> Iterator[Path]:
    tmp_root = SCRIPT_PATH.parents[1] / ".codex-pytest-work"
    tmp_root.mkdir(exist_ok=True)
    tmp_path = tmp_root / f"cleanup-script-{uuid4().hex}"
    tmp_path.mkdir()
    try:
        yield tmp_path
    finally:
        REAL_RMTREE(tmp_path, ignore_errors=True)


def test_collect_cleanup_targets_finds_known_artifacts_and_skips_virtualenv() -> None:
    with workspace_tmp_dir() as tmp_path:
        tracked_paths = [
            tmp_path / "src" / "__pycache__",
            tmp_path / "tests" / "unit" / "__pycache__",
            tmp_path / ".pytest_cache",
            tmp_path / ".ruff_cache",
            tmp_path / ".tmp-pip-audit",
            tmp_path / "cleanup-test-temp",
            tmp_path / "ci_tmp_pytest",
            tmp_path / "local-pytest-temp",
            tmp_path / "pytest-cache-files-abc123",
            tmp_path / "pytest-temp-run-1",
            tmp_path / "tmp3cgk2n_2",
        ]
        for path in tracked_paths:
            path.mkdir(parents=True)

        (tmp_path / "coverage.xml").write_text("", encoding="utf-8")
        (tmp_path / "mypy-report.txt").write_text("", encoding="utf-8")
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
        assert "cleanup-test-temp" in relative_targets
        assert "ci_tmp_pytest" in relative_targets
        assert "local-pytest-temp" in relative_targets
        assert "pytest-cache-files-abc123" in relative_targets
        assert "pytest-temp-run-1" in relative_targets
        assert "tmp3cgk2n_2" in relative_targets
        assert "coverage.xml" in relative_targets
        assert "mypy-report.txt" in relative_targets
        assert "mutmut-results.txt" in relative_targets
        assert ".venv/Lib/site-packages/__pycache__" not in relative_targets


def test_cli_dry_run_lists_targets_without_deleting_them() -> None:
    with workspace_tmp_dir() as tmp_path:
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


def test_remove_targets_skips_paths_with_access_errors(monkeypatch) -> None:
    with workspace_tmp_dir() as tmp_path:
        removable = tmp_path / "coverage.xml"
        blocked = tmp_path / ".pytest_cache"
        removable.write_text("", encoding="utf-8")
        blocked.mkdir()

        original_rmtree = CLEANUP.shutil.rmtree

        def fake_rmtree(path: Path) -> None:
            if Path(path) == blocked:
                raise PermissionError("denied")
            original_rmtree(path)

        monkeypatch.setattr(CLEANUP.shutil, "rmtree", fake_rmtree)

        removed, missing, failed = CLEANUP.remove_targets([removable, blocked])

        assert removed == 1
        assert missing == 0
        assert failed == [blocked]
        assert blocked.exists()


def test_remove_targets_uses_docker_fallback_for_windows_permission_errors(monkeypatch) -> None:
    with workspace_tmp_dir() as tmp_path:
        blocked = tmp_path / "pytest-cache-files-abc123"
        blocked.mkdir()
        (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

        def fake_rmtree(path: Path) -> None:
            if Path(path) == blocked:
                raise PermissionError("denied")
            raise AssertionError(f"Unexpected path: {path}")

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            assert command[:7] == ["docker", "compose", "run", "--rm", "app", "python", "-c"]
            assert command[-1] == "/app/pytest-cache-files-abc123"
            assert kwargs["cwd"] == tmp_path
            blocked.rmdir()
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(CLEANUP.shutil, "rmtree", fake_rmtree)
        monkeypatch.setattr(CLEANUP.subprocess, "run", fake_run)
        monkeypatch.setattr(CLEANUP.sys, "platform", "win32")

        removed, missing, failed = CLEANUP.remove_targets([blocked], root=tmp_path)

        assert removed == 1
        assert missing == 0
        assert failed == []
        assert not blocked.exists()
