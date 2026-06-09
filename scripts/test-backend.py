#!/usr/bin/env python3
"""Run backend test suites with isolated working directories.

Running ``pytest`` from the repository root collects all example apps in one
process. Several examples intentionally use app-local imports such as
``from models import ...``; collecting them together makes those imports collide.

This runner executes each backend suite separately with a deterministic cwd and
PYTHONPATH so package tests, examples, and apps can all be run from one command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERVIEW_FILE = ROOT / ".project/test-runs/backend-test-overview.json"
COUNT_PATTERN = re.compile(
    r"(?P<count>\d+)\s+"
    r"(?P<label>passed|failed|errors?|warnings?)"
)
RESET = "\033[0m"
COLORS = {
    "passed": "\033[32m",
    "failed": "\033[31m",
    "warning": "\033[33m",
    "header": "\033[36m",
    "muted": "\033[2m",
}


@dataclass(frozen=True)
class Suite:
    name: str
    cwd: Path
    pytest_args: tuple[str, ...]
    extra_pythonpath: tuple[Path, ...] = ()


@dataclass(frozen=True)
class SuiteResult:
    name: str
    status: str
    returncode: int | None = None
    passed: int = 0
    failed: int = 0
    warnings: int = 0
    errors: int = 0
    message: str = ""
    previous_status: str | None = None


PACKAGE_PATHS = (
    ROOT,
    ROOT / "packages/n3tx-core/src",
    ROOT / "packages/n3tx-actors/src",
    ROOT / "packages/n3tx-agents/src",
    ROOT / "packages/n3tx-files/src",
    ROOT / "packages/n3tx-ui/src",
    ROOT / "packages/n3tx/src",
)


SUITES = (
    Suite(
        name="core",
        cwd=ROOT,
        pytest_args=("packages/n3tx-core/src/n3tx_core/tests/unit/",),
    ),
    Suite(
        name="actors",
        cwd=ROOT,
        pytest_args=("packages/n3tx-actors/src/n3tx_actors/tests/",),
    ),
    Suite(
        name="agents",
        cwd=ROOT,
        pytest_args=("packages/n3tx-agents/src/n3tx_agents/tests/",),
    ),
    Suite(
        name="files",
        cwd=ROOT,
        pytest_args=("packages/n3tx-files/src/n3tx_files/tests/",),
    ),
    Suite(
        name="examples-core",
        cwd=ROOT / "examples/core",
        pytest_args=("tests/",),
        extra_pythonpath=(ROOT / "examples/core",),
    ),
    Suite(
        name="examples-actors",
        cwd=ROOT / "examples/actors",
        pytest_args=("tests/",),
        extra_pythonpath=(ROOT / "examples/actors",),
    ),
    Suite(
        name="examples-grants",
        cwd=ROOT / "examples/grants",
        pytest_args=("tests/",),
        extra_pythonpath=(ROOT / "examples/grants",),
    ),
    Suite(
        name="veille",
        cwd=ROOT / "apps/veille",
        pytest_args=("tests/",),
        extra_pythonpath=(ROOT / "apps/veille",),
    ),
)

SHORT_PYTEST_ARGS = ("-q", "--tb=short", "--disable-warnings", "-ra")


def has_pytest_color_arg(args: tuple[str, ...]) -> bool:
    return any(arg == "--color" or arg.startswith("--color=") for arg in args)


def pythonpath_for(suite: Suite) -> str:
    paths = [*suite.extra_pythonpath, *PACKAGE_PATHS]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.extend(Path(p) for p in existing.split(os.pathsep) if p)

    seen: set[str] = set()
    unique_paths = []
    for path in paths:
        normalized = str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_paths.append(normalized)
    return os.pathsep.join(unique_paths)


def run_suite(suite: Suite, pytest_extra: tuple[str, ...]) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = pythonpath_for(suite)
    color_args = () if has_pytest_color_arg(pytest_extra) else ("--color=yes",)
    command = [sys.executable, "-m", "pytest", *suite.pytest_args, *color_args, *pytest_extra]

    print(f"\n=== backend suite: {suite.name} ===", flush=True)
    print(f"cwd: {suite.cwd}", flush=True)
    print("cmd:", " ".join(command), flush=True)

    process = subprocess.Popen(
        command,
        cwd=suite.cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    output_lines: list[str] = []
    if process.stdout is not None:
        for line in process.stdout:
            print(line, end="")
            output_lines.append(line)
    return process.wait(), "".join(output_lines)


def parse_pytest_counts(output: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "warnings": 0, "errors": 0}
    for line in reversed(output.splitlines()):
        if " in " not in line:
            continue
        matches = list(COUNT_PATTERN.finditer(line))
        if not matches:
            continue
        for match in matches:
            label = match.group("label")
            count = int(match.group("count"))
            if label == "passed":
                counts["passed"] = count
            elif label == "failed":
                counts["failed"] = count
            elif label.startswith("warning"):
                counts["warnings"] = count
            elif label.startswith("error"):
                counts["errors"] = count
        return counts
    return counts


def status_from_counts(returncode: int, counts: dict[str, int]) -> str:
    if returncode != 0 or counts["failed"] or counts["errors"]:
        return "failed"
    if counts["warnings"]:
        return "warning"
    return "passed"


def load_previous_overview(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as overview_file:
            overview = json.load(overview_file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read previous overview {path}: {exc}", file=sys.stderr)
        return {}

    suites = overview.get("suites", [])
    if not isinstance(suites, list):
        return {}

    previous: dict[str, str] = {}
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        name = suite.get("name")
        status = suite.get("status")
        if isinstance(name, str) and isinstance(status, str):
            previous[name] = status
    return previous


def result_from_run(suite: Suite, code: int, output: str, previous: dict[str, str]) -> SuiteResult:
    counts = parse_pytest_counts(output)
    return SuiteResult(
        name=suite.name,
        status=status_from_counts(code, counts),
        returncode=code,
        passed=counts["passed"],
        failed=counts["failed"],
        warnings=counts["warnings"],
        errors=counts["errors"],
        previous_status=previous.get(suite.name),
    )


def warning_result(suite: Suite, message: str, previous: dict[str, str]) -> SuiteResult:
    return SuiteResult(
        name=suite.name,
        status="warning",
        message=message,
        previous_status=previous.get(suite.name),
    )


def summarize_results(results: list[SuiteResult]) -> dict[str, int]:
    totals = {
        "passed": 0,
        "failed": 0,
        "warning": 0,
        "total": len(results),
        "tests_passed": 0,
        "tests_failed": 0,
        "warnings": 0,
        "errors": 0,
    }
    for result in results:
        if result.status in totals:
            totals[result.status] += 1
        totals["tests_passed"] += result.passed
        totals["tests_failed"] += result.failed
        totals["warnings"] += result.warnings
        totals["errors"] += result.errors
    return totals


def color_enabled(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def paint(value: object, color: str, enabled: bool) -> str:
    text = str(value)
    if not enabled:
        return text
    return f"{COLORS[color]}{text}{RESET}"


def cell(
    value: object,
    width: int,
    color: str | None,
    enabled: bool,
    align: str = ">",
) -> str:
    text = f"{str(value):{align}{width}}"
    return paint(text, color, enabled) if color else text


def print_summary(results: list[SuiteResult], overview_file: Path, color_mode: str) -> None:
    totals = summarize_results(results)
    use_color = color_enabled(color_mode)
    name_width = max([len("suite"), *(len(result.name) for result in results)] or [len("suite")]) + 2
    status_width = len("warning") + 2

    print("\n" + paint("=== Backend test summary ===", "header", use_color))
    if not results:
        print("No backend suites were selected.")
    else:
        print()
        print(
            f"{'suite':<{name_width}}"
            f"{'status':<{status_width}}"
            f"{'passed':>8}"
            f"{'failed':>8}"
            f"{'warn':>8}"
            f"{'errors':>8}"
            f"  {'previous':<10}"
            "note"
        )
        print(
            f"{'-' * (name_width - 2):<{name_width}}"
            f"{'-' * (status_width - 2):<{status_width}}"
            f"{'-' * 6:>8}"
            f"{'-' * 6:>8}"
            f"{'-' * 4:>8}"
            f"{'-' * 6:>8}"
            f"  {'-' * 8:<10}"
            "----"
        )
        for result in results:
            previous = result.previous_status or "-"
            note = result.message
            if result.returncode not in (None, 0):
                note = f"exit {result.returncode}" if not note else f"{note}; exit {result.returncode}"
            status_color = "passed" if result.status == "passed" else result.status
            print(
                f"{result.name:<{name_width}}"
                f"{cell(result.status, status_width, status_color, use_color, '<')}"
                f"{cell(result.passed, 8, 'passed' if result.passed else None, use_color)}"
                f"{cell(result.failed, 8, 'failed' if result.failed else None, use_color)}"
                f"{cell(result.warnings, 8, 'warning' if result.warnings else None, use_color)}"
                f"{cell(result.errors, 8, 'failed' if result.errors else None, use_color)}"
                f"  {previous:<10}"
                f"{note}"
            )

    print()
    print(
        "Suites: "
        f"{paint(totals['passed'], 'passed', use_color)} passed, "
        f"{paint(totals['failed'], 'failed', use_color)} failed, "
        f"{paint(totals['warning'], 'warning', use_color)} warning, "
        f"{totals['total']} total"
    )
    print(
        "Tests:  "
        f"{paint(totals['tests_passed'], 'passed', use_color)} passed, "
        f"{paint(totals['tests_failed'], 'failed', use_color)} failed, "
        f"{paint(totals['warnings'], 'warning', use_color)} warnings, "
        f"{paint(totals['errors'], 'failed', use_color)} errors"
    )
    print(f"Overview saved: {overview_file}")


def overview_payload(
    results: list[SuiteResult],
    argv: list[str],
    overview_file: Path,
) -> dict[str, object]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(argv),
        "overview_file": str(overview_file),
        "totals": summarize_results(results),
        "suites": [
            {
                "name": result.name,
                "status": result.status,
                "returncode": result.returncode,
                "counts": {
                    "passed": result.passed,
                    "failed": result.failed,
                    "warnings": result.warnings,
                    "errors": result.errors,
                },
                "message": result.message,
                "previous_status": result.previous_status,
            }
            for result in results
        ],
    }


def save_overview(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as overview_file:
        json.dump(payload, overview_file, indent=2, sort_keys=True)
        overview_file.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend test suites without root-level pytest import collisions.",
    )
    parser.add_argument(
        "--suite",
        action="append",
        choices=[suite.name for suite in SUITES],
        help="Suite to run. May be provided multiple times. Default: all suites.",
    )
    failure_group = parser.add_mutually_exclusive_group()
    failure_group.add_argument(
        "--continue-on-failure",
        dest="continue_on_failure",
        action="store_true",
        default=True,
        help="Run remaining suites after a failure and return non-zero at the end. This is the default.",
    )
    failure_group.add_argument(
        "--fail-fast",
        dest="continue_on_failure",
        action="store_false",
        help="Stop after the first failing suite.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suites and exit.",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help=(
            "Use concise pytest output for each suite: "
            "-q --tb=short --disable-warnings -ra."
        ),
    )
    parser.add_argument(
        "--overview-file",
        type=Path,
        default=DEFAULT_OVERVIEW_FILE,
        help=(
            "Write the final suite overview to this JSON file and compare "
            "against it when it already exists. "
            f"Default: {DEFAULT_OVERVIEW_FILE}"
        ),
    )
    parser.add_argument(
        "--summary-color",
        choices=("auto", "always", "never"),
        default="auto",
        help="Colorize the final backend test summary. Default: auto.",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed to pytest after '--', e.g. -- -q -x.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list:
        for suite in SUITES:
            print(f"{suite.name}\tcwd={suite.cwd}\tpytest={' '.join(suite.pytest_args)}")
        return 0

    selected = set(args.suite or [suite.name for suite in SUITES])
    pytest_extra = tuple(arg for arg in args.pytest_args if arg != "--")
    if args.short:
        pytest_extra = (*SHORT_PYTEST_ARGS, *pytest_extra)

    overview_file = args.overview_file
    previous = load_previous_overview(overview_file)
    results: list[SuiteResult] = []
    exit_code = 0
    for suite in SUITES:
        if suite.name not in selected:
            continue
        if not suite.cwd.exists():
            message = f"missing cwd: {suite.cwd}"
            print(f"Skipping missing suite {suite.name}: {suite.cwd}", file=sys.stderr)
            results.append(warning_result(suite, message, previous))
            continue
        code, output = run_suite(suite, pytest_extra)
        results.append(result_from_run(suite, code, output, previous))
        if code != 0:
            exit_code = code
            if not args.continue_on_failure:
                print(f"\nFAILED: {suite.name}", file=sys.stderr)
                break

    save_overview(overview_file, overview_payload(results, sys.argv, overview_file))
    print_summary(results, overview_file, args.summary_color)

    failures = [result.name for result in results if result.status == "failed"]
    if failures:
        print("\nFailed suites:", ", ".join(failures), file=sys.stderr)

    return 1 if failures and args.continue_on_failure else exit_code


if __name__ == "__main__":
    raise SystemExit(main())
