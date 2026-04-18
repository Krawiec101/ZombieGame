from __future__ import annotations

import argparse
import os
import shutil
from collections.abc import Iterable
from fnmatch import fnmatch
from pathlib import Path

ROOT_LEVEL_DIRECTORIES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    "mutants",
}
ROOT_LEVEL_DIRECTORY_PATTERNS = (
    ".codex-*",
    ".tmp-*",
    "ci_tmp_*",
    "local-pytest-temp*",
    "pytest-cache-files-*",
    "pytest-temp-run-*",
    "tmp*",
)
ROOT_LEVEL_FILES = {
    ".coverage",
    "architecture-report.txt",
    "architecture-summary.md",
    "coverage-summary.md",
    "coverage.xml",
    "crap-summary.md",
    "lint-report.txt",
    "lint-summary.md",
    "mutation-summary.md",
    "mutmut-results.txt",
    "pytest-coverage.txt",
    "sca-report.txt",
    "sca-summary.md",
}
RECURSIVE_DIRECTORY_NAMES = {
    "__pycache__",
}
SKIPPED_RECURSION_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
}


def _matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch(name, pattern) for pattern in patterns)


def collect_cleanup_targets(root: Path) -> list[Path]:
    targets: set[Path] = set()

    for entry in root.iterdir():
        if entry.is_dir():
            if entry.name in ROOT_LEVEL_DIRECTORIES or _matches_any(entry.name, ROOT_LEVEL_DIRECTORY_PATTERNS):
                targets.add(entry)
        elif entry.is_file() and entry.name in ROOT_LEVEL_FILES:
            targets.add(entry)

    def _handle_walk_error(_error: OSError) -> None:
        return None

    for current_root, dirnames, _filenames in os.walk(root, topdown=True, onerror=_handle_walk_error):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIPPED_RECURSION_DIRECTORIES
            and name not in ROOT_LEVEL_DIRECTORIES
            and not _matches_any(name, ROOT_LEVEL_DIRECTORY_PATTERNS)
        ]
        current_root_path = Path(current_root)
        for dirname in tuple(dirnames):
            if dirname in RECURSIVE_DIRECTORY_NAMES:
                target = current_root_path / dirname
                targets.add(target)
                dirnames.remove(dirname)

    return sorted(targets)


def remove_targets(paths: Iterable[Path]) -> tuple[int, int, list[Path]]:
    removed = 0
    missing = 0
    failed: list[Path] = []
    for path in paths:
        if not path.exists():
            missing += 1
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError:
            failed.append(path)
            continue
        removed += 1
    return removed, missing, failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove local caches and generated artifacts from the repository.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to clean. Defaults to the project root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matched paths without deleting them.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = args.root.resolve()
    targets = collect_cleanup_targets(root)

    if not targets:
        print("No local artifacts found.")
        return 0

    for path in targets:
        print(path.relative_to(root).as_posix())

    if args.dry_run:
        print(f"Matched {len(targets)} paths.")
        return 0

    removed, missing, failed = remove_targets(targets)
    print(f"Removed {removed} paths.")
    if missing:
        print(f"Skipped {missing} paths that disappeared during cleanup.")
    if failed:
        print(f"Skipped {len(failed)} paths due to access errors:")
        for path in failed:
            print(path.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
