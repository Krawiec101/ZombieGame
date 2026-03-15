from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

MAX_CRAP_PER_FUNCTION = 30.0
MAX_HIGH_CRAP_FUNCTIONS = 0
MIN_COVERAGE_FOR_HIGH_COMPLEXITY = 0.80
HIGH_COMPLEXITY_THRESHOLD = 15
TOP_FUNCTIONS_LIMIT = 10


@dataclass(frozen=True)
class FunctionMetric:
    file_path: str
    name: str
    lineno: int
    endline: int
    complexity: int
    coverage: float
    crap: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CRAP quality gate.")
    parser.add_argument("--coverage-xml", default="coverage.xml", help="Path to the coverage XML report.")
    parser.add_argument("--source-dir", default="src", help="Directory to analyze with radon.")
    parser.add_argument("--summary-md", default="crap-summary.md", help="Markdown summary output path.")
    return parser.parse_args()


def normalize_path(path_text: str) -> str:
    path = Path(path_text)

    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            pass

    normalized = path.as_posix().lstrip("./")
    if normalized.startswith("src/"):
        return normalized.removeprefix("src/")
    return normalized


def load_coverage_lines(coverage_xml_path: Path) -> dict[str, dict[int, int]]:
    if not coverage_xml_path.exists():
        raise FileNotFoundError(f"Coverage report not found: {coverage_xml_path}")

    root = ET.parse(coverage_xml_path).getroot()
    coverage_lines: dict[str, dict[int, int]] = {}

    for class_node in root.findall(".//class"):
        filename = class_node.get("filename")
        if not filename:
            continue

        normalized_filename = normalize_path(filename)
        file_lines = coverage_lines.setdefault(normalized_filename, {})
        lines_node = class_node.find("lines")
        if lines_node is None:
            continue

        for line_node in lines_node.findall("line"):
            line_number = line_node.get("number")
            hits = line_node.get("hits")
            if line_number is None or hits is None:
                continue

            file_lines[int(line_number)] = int(hits)

    return coverage_lines


def load_complexity_blocks(source_dir: Path) -> list[dict[str, object]]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    command = [sys.executable, "-m", "radon", "cc", "-j", str(source_dir)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if getattr(result, "returncode", 0) != 0:
        return load_complexity_blocks_with_ast(source_dir)

    complexity_data = json.loads(result.stdout or "{}")
    blocks: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str, int, int]] = set()

    for file_path, entries in complexity_data.items():
        normalized_file_path = normalize_path(file_path)
        for block in flatten_complexity_entries(normalized_file_path, entries):
            block_key = (
                str(block["file_path"]),
                str(block["name"]),
                int(block["lineno"]),
                int(block["endline"]),
            )
            if block_key in seen_keys:
                continue
            seen_keys.add(block_key)
            blocks.append(block)

    return blocks


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.blocks: list[dict[str, object]] = []
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.blocks.append(self._build_block(node))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.blocks.append(self._build_block(node))
        self.generic_visit(node)

    def _build_block(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, object]:
        qualified_name = node.name
        if self._class_stack:
            qualified_name = f"{self._class_stack[-1]}.{node.name}"

        return {
            "name": qualified_name,
            "lineno": int(node.lineno),
            "endline": int(getattr(node, "end_lineno", node.lineno)),
            "complexity": calculate_ast_complexity(node),
        }


def calculate_ast_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    complexity = 1
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.IfExp,
        ast.Try,
        ast.ExceptHandler,
        ast.BoolOp,
        ast.Match,
    )

    for child in ast.walk(node):
        if isinstance(child, branch_nodes):
            if isinstance(child, ast.BoolOp):
                complexity += max(1, len(child.values) - 1)
            elif isinstance(child, ast.Try):
                complexity += 1
            else:
                complexity += 1

    return complexity


def load_complexity_blocks_with_ast(source_dir: Path) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []

    for path in sorted(source_dir.rglob("*.py")):
        normalized_file_path = normalize_path(path)
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = ComplexityVisitor()
        visitor.visit(module)
        for block in visitor.blocks:
            blocks.append(
                {
                    "file_path": normalized_file_path,
                    "name": str(block["name"]),
                    "lineno": int(block["lineno"]),
                    "endline": int(block["endline"]),
                    "complexity": int(block["complexity"]),
                }
            )

    return blocks


def flatten_complexity_entries(file_path: str, entries: list[dict[str, object]]) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []

    for entry in entries:
        block_type = entry.get("type")
        block_name = str(entry.get("name", "<unknown>"))

        if block_type == "class":
            for method in entry.get("methods", []):
                method_entry = dict(method)
                method_entry.setdefault("classname", block_name)
                blocks.extend(flatten_complexity_entries(file_path, [method_entry]))
            continue

        qualified_name = block_name
        if block_type == "method":
            class_name = entry.get("classname")
            if class_name:
                qualified_name = f"{class_name}.{block_name}"

        if block_type in {"function", "method"}:
            blocks.append(
                {
                    "file_path": file_path,
                    "name": qualified_name,
                    "lineno": int(entry["lineno"]),
                    "endline": int(entry["endline"]),
                    "complexity": int(entry["complexity"]),
                }
            )

        closures = entry.get("closures", [])
        if closures:
            blocks.extend(flatten_complexity_entries(file_path, closures))

    return blocks


def calculate_function_coverage(file_lines: dict[int, int], lineno: int, endline: int) -> float:
    executable_lines = [hits for line_number, hits in file_lines.items() if lineno <= line_number <= endline]
    if not executable_lines:
        return 0.0

    covered_lines = sum(1 for hits in executable_lines if hits > 0)
    return covered_lines / len(executable_lines)


def calculate_crap(complexity: int, coverage: float) -> float:
    return complexity**2 * (1 - coverage) ** 3 + complexity


def build_metrics(
    coverage_lines: dict[str, dict[int, int]],
    complexity_blocks: list[dict[str, object]],
) -> list[FunctionMetric]:
    metrics: list[FunctionMetric] = []

    for block in complexity_blocks:
        file_path = str(block["file_path"])
        lineno = int(block["lineno"])
        endline = int(block["endline"])
        complexity = int(block["complexity"])
        coverage = calculate_function_coverage(coverage_lines.get(file_path, {}), lineno, endline)

        metrics.append(
            FunctionMetric(
                file_path=file_path,
                name=str(block["name"]),
                lineno=lineno,
                endline=endline,
                complexity=complexity,
                coverage=coverage,
                crap=calculate_crap(complexity, coverage),
            )
        )

    metrics.sort(key=lambda metric: metric.crap, reverse=True)
    return metrics


def build_summary(metrics: list[FunctionMetric]) -> tuple[str, bool]:
    high_crap_functions = [metric for metric in metrics if metric.crap > MAX_CRAP_PER_FUNCTION]
    undercovered_high_complexity_functions = [
        metric
        for metric in metrics
        if metric.complexity >= HIGH_COMPLEXITY_THRESHOLD and metric.coverage < MIN_COVERAGE_FOR_HIGH_COMPLEXITY
    ]
    failed = len(high_crap_functions) > MAX_HIGH_CRAP_FUNCTIONS or bool(undercovered_high_complexity_functions)
    status = "FAIL" if failed else "PASS"

    lines = [
        "## CRAP quality gate",
        "",
        f"Status: **{status}**",
        "",
        f"Analyzed functions/methods: **{len(metrics)}**",
        "",
        "### Thresholds",
        "",
        f"- `max_crap_per_function`: `{MAX_CRAP_PER_FUNCTION:.1f}`",
        f"- `max_high_crap_functions`: `{MAX_HIGH_CRAP_FUNCTIONS}`",
        f"- `min_coverage_for_high_complexity`: `{MIN_COVERAGE_FOR_HIGH_COMPLEXITY:.0%}`",
        f"- `high_complexity_threshold`: `{HIGH_COMPLEXITY_THRESHOLD}`",
        "",
        "### Counts",
        "",
        f"- Functions with `CRAP > {MAX_CRAP_PER_FUNCTION:.1f}`: **{len(high_crap_functions)}**",
        (
            f"- Functions with `CC >= {HIGH_COMPLEXITY_THRESHOLD}` and coverage "
            f"`< {MIN_COVERAGE_FOR_HIGH_COMPLEXITY:.0%}`: **{len(undercovered_high_complexity_functions)}**"
        ),
        "",
        f"### Top {min(TOP_FUNCTIONS_LIMIT, len(metrics))} functions by CRAP",
        "",
    ]

    if metrics:
        lines.extend(
            [
                "| Function | File | Line | CC | Coverage | CRAP |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for metric in metrics[:TOP_FUNCTIONS_LIMIT]:
            lines.append(
                f"| `{metric.name}` | `{metric.file_path}` | {metric.lineno} | "
                f"{metric.complexity} | {metric.coverage:.0%} | {metric.crap:.2f} |"
            )
    else:
        lines.append("_No functions or methods were analyzed._")

    return "\n".join(lines) + "\n", failed


def main() -> int:
    args = parse_args()
    coverage_xml_path = Path(args.coverage_xml)
    source_dir = Path(args.source_dir)
    summary_path = Path(args.summary_md)

    try:
        coverage_lines = load_coverage_lines(coverage_xml_path)
        complexity_blocks = load_complexity_blocks(source_dir)
        metrics = build_metrics(coverage_lines, complexity_blocks)
        summary, failed = build_summary(metrics)
        summary_path.write_text(summary, encoding="utf-8")
        print(summary, end="")
        return 1 if failed else 0
    except Exception as exc:
        error_summary = f"## CRAP quality gate\n\nStatus: **FAIL**\n\nError: `{exc}`\n"
        summary_path.write_text(error_summary, encoding="utf-8")
        print(error_summary, end="", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
