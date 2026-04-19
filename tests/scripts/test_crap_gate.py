from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


def find_script_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "scripts" / "ci" / "crap_gate.py"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate scripts/ci/crap_gate.py")


SCRIPT_PATH = find_script_path()
SCRIPT_SPEC = importlib.util.spec_from_file_location("crap_gate", SCRIPT_PATH)
assert SCRIPT_SPEC is not None
assert SCRIPT_SPEC.loader is not None
CRAP_GATE = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = CRAP_GATE
SCRIPT_SPEC.loader.exec_module(CRAP_GATE)


@contextmanager
def workspace_tmp_dir() -> Path:
    tmp_root = SCRIPT_PATH.parents[2] / ".codex-pytest-work"
    tmp_root.mkdir(exist_ok=True)
    tmp_path = tmp_root / f"crap-gate-{uuid4().hex}"
    tmp_path.mkdir()
    try:
        yield tmp_path
    finally:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import shutil, sys; shutil.rmtree(Path(sys.argv[1]), ignore_errors=True)",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )


def write_module(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def write_coverage_xml(path: Path, filename: str, line_hits: dict[int, int]) -> None:
    lines = "\n".join(
        f'          <line number="{line_number}" hits="{hits}"/>'
        for line_number, hits in sorted(line_hits.items())
    )
    content = f"""<?xml version="1.0" ?>
<coverage version="7.0">
  <packages>
    <package name="sample">
      <classes>
        <class name="sample_module.py" filename="{filename}">
          <lines>
{lines}
          </lines>
        </class>
      </classes>
    </package>
  </packages>
</coverage>
"""
    path.write_text(content, encoding="utf-8")


def run_crap_gate(source_dir: Path, coverage_xml: Path, summary_md: Path) -> subprocess.CompletedProcess[str]:
    pytest.importorskip("radon")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source-dir",
            str(source_dir),
            "--coverage-xml",
            str(coverage_xml),
            "--summary-md",
            str(summary_md),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_normalize_path_removes_src_prefix() -> None:
    assert CRAP_GATE.normalize_path("src/core/game_session.py") == "core/game_session.py"
    assert CRAP_GATE.normalize_path("core/game_session.py") == "core/game_session.py"


def test_load_complexity_blocks_deduplicates_radon_methods(monkeypatch) -> None:
    with workspace_tmp_dir() as tmp_path:
        source_dir = tmp_path / "src"
        source_dir.mkdir()

        duplicate_output = {
            "src/core/sample.py": [
                {
                    "type": "class",
                    "name": "Sample",
                    "lineno": 1,
                    "endline": 10,
                    "methods": [
                        {
                            "type": "method",
                            "name": "run",
                            "classname": "Sample",
                            "lineno": 2,
                            "endline": 4,
                            "complexity": 3,
                            "closures": [],
                        }
                    ],
                },
                {
                    "type": "method",
                    "name": "run",
                    "classname": "Sample",
                    "lineno": 2,
                    "endline": 4,
                    "complexity": 3,
                    "closures": [],
                },
            ]
        }

        def fake_run(*args, **kwargs):
            return SimpleNamespace(stdout=json.dumps(duplicate_output))

        monkeypatch.setattr(CRAP_GATE.subprocess, "run", fake_run)

        blocks = CRAP_GATE.load_complexity_blocks(source_dir)

        assert len(blocks) == 1
        assert blocks[0]["file_path"] == "core/sample.py"
        assert blocks[0]["name"] == "Sample.run"


def test_crap_gate_passes_for_fully_covered_low_complexity_function() -> None:
    with workspace_tmp_dir() as tmp_path:
        source_dir = tmp_path / "sample_src"
        module_path = source_dir / "healthy.py"
        write_module(
            module_path,
            """
            def healthy(value):
                if value > 0:
                    return value
                return -value
            """,
        )

        coverage_xml = tmp_path / "coverage.xml"
        write_coverage_xml(coverage_xml, "sample_src/healthy.py", {1: 1, 2: 1, 3: 1, 4: 1})
        summary_md = tmp_path / "crap-summary.md"

        result = run_crap_gate(source_dir, coverage_xml, summary_md)

        assert result.returncode == 0
        summary = summary_md.read_text(encoding="utf-8")
        assert "Status: **PASS**" in summary
        assert "Functions with `CRAP > 12.0`: **0**" in summary
        assert "`healthy`" in summary


def test_crap_gate_fails_when_function_exceeds_crap_threshold() -> None:
    with workspace_tmp_dir() as tmp_path:
        source_dir = tmp_path / "sample_src"
        module_path = source_dir / "risky.py"
        write_module(
            module_path,
            """
            def risky(value):
                if value == 0:
                    return 0
                if value == 1:
                    return 1
                if value == 2:
                    return 2
                if value == 3:
                    return 3
                if value == 4:
                    return 4
                if value == 5:
                    return 5
                return -1
            """,
        )

        coverage_xml = tmp_path / "coverage.xml"
        write_coverage_xml(
            coverage_xml,
            "sample_src/risky.py",
            {line_number: 0 for line_number in range(1, 14)},
        )
        summary_md = tmp_path / "crap-summary.md"

        result = run_crap_gate(source_dir, coverage_xml, summary_md)

        assert result.returncode == 1
        summary = summary_md.read_text(encoding="utf-8")
        assert "Status: **FAIL**" in summary
        assert "Functions with `CRAP > 12.0`: **1**" in summary
        assert "`risky`" in summary


def test_crap_gate_fails_for_high_complexity_function_with_low_coverage() -> None:
    with workspace_tmp_dir() as tmp_path:
        source_dir = tmp_path / "sample_src"
        module_path = source_dir / "complex_guard.py"
        write_module(
            module_path,
            """
            def complex_guard(value):
                if value == 0:
                    return 0
                if value == 1:
                    return 1
                if value == 2:
                    return 2
                if value == 3:
                    return 3
                if value == 4:
                    return 4
                if value == 5:
                    return 5
                if value == 6:
                    return 6
                if value == 7:
                    return 7
                if value == 8:
                    return 8
                if value == 9:
                    return 9
                if value == 10:
                    return 10
                if value == 11:
                    return 11
                if value == 12:
                    return 12
                if value == 13:
                    return 13
                if value == 14:
                    return 14
                return -1
            """,
        )

        coverage_xml = tmp_path / "coverage.xml"
        line_hits = {line_number: 1 for line_number in range(1, 24)}
        for line_number in range(19, 24):
            line_hits[line_number] = 0
        write_coverage_xml(coverage_xml, "sample_src/complex_guard.py", line_hits)
        summary_md = tmp_path / "crap-summary.md"

        result = run_crap_gate(source_dir, coverage_xml, summary_md)

        assert result.returncode == 1
        summary = summary_md.read_text(encoding="utf-8")
        assert "Status: **FAIL**" in summary
        assert "Functions with `CC >= 15` and coverage `< 80%`: **1**" in summary
        assert "`complex_guard`" in summary


def test_calculate_function_coverage_marks_missing_data() -> None:
    coverage, has_coverage_data = CRAP_GATE.calculate_function_coverage({}, 10, 20)

    assert coverage == 0.0
    assert has_coverage_data is False


def test_build_summary_reports_missing_coverage() -> None:
    thresholds = CRAP_GATE.CrapThresholds(
        max_crap_per_function=12.0,
        max_high_crap_functions=0,
        min_coverage_for_high_complexity=0.80,
        high_complexity_threshold=15,
    )
    metrics = [
        CRAP_GATE.FunctionMetric(
            file_path="core/sample.py",
            name="sample",
            lineno=1,
            endline=5,
            complexity=1,
            coverage=0.0,
            has_coverage_data=False,
            crap=1.0,
        )
    ]

    summary, failed = CRAP_GATE.build_summary(metrics, thresholds)

    assert failed is False
    assert "Functions without mapped coverage lines: **1**" in summary


def test_main_accepts_custom_threshold_arguments() -> None:
    pytest.importorskip("radon")
    with workspace_tmp_dir() as tmp_path:
        source_dir = tmp_path / "sample_src"
        module_path = source_dir / "moderate.py"
        write_module(
            module_path,
            """
            def moderate(value):
                if value == 0:
                    return 0
                if value == 1:
                    return 1
                if value == 2:
                    return 2
                if value == 3:
                    return 3
                return -1
            """,
        )

        coverage_xml = tmp_path / "coverage.xml"
        write_coverage_xml(coverage_xml, "sample_src/moderate.py", {line_number: 0 for line_number in range(1, 11)})
        summary_md = tmp_path / "crap-summary.md"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--source-dir",
                str(source_dir),
                "--coverage-xml",
                str(coverage_xml),
                "--summary-md",
                str(summary_md),
                "--max-crap-per-function",
                "5",
                "--max-high-crap-functions",
                "0",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1
        summary = summary_md.read_text(encoding="utf-8")
        assert "Functions with `CRAP > 5.0`: **1**" in summary
