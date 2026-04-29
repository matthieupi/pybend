#!/usr/bin/env python3
"""Run frontend test suites with isolated commands and a final overview.

The frontend harness has two runner families:

* Vitest for jsdom/unit-style tests under ``tests/**/*.test.js``.
* Playwright for browser specs under ``tests/e2e/*.spec.js``.

Specialized Playwright configs own app-specific suites such as grants, veille,
and performance. The core e2e suite runs through the worker-isolated parallel
config and intentionally excludes those files so the default run covers every
frontend spec exactly once.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "tests/frontend"
E2E_DIR = FRONTEND_ROOT / "tests/e2e"
DEFAULT_OVERVIEW_FILE = ROOT / ".project/test-runs/frontend-test-overview.json"
DEFAULT_SUITE_WORKERS = int(os.environ.get("N3TX_FRONTEND_SUITE_WORKERS", "2"))
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
}
PRINT_LOCK = threading.Lock()


@dataclass(frozen=True)
class Suite:
    name: str
    cwd: Path
    command: tuple[str, ...]
    append_args: bool = False
    env: dict[str, str] | None = None
    description: str = ""


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


def core_e2e_specs() -> tuple[str, ...]:
    excluded_names = {"performance.spec.js"}
    excluded_prefixes = ("grants-", "veille-")
    specs = []
    for path in sorted(E2E_DIR.glob("*.spec.js")):
        if path.name in excluded_names or path.name.startswith(excluded_prefixes):
            continue
        specs.append(f"tests/e2e/{path.name}")
    return tuple(specs)


def frontend_env() -> dict[str, str]:
    return {
        "FORCE_COLOR": "1",
        "npm_config_color": "always",
        "N3TX_E2E_PARALLEL_WORKERS": os.environ.get("N3TX_E2E_PARALLEL_WORKERS", "2"),
    }


def build_suites() -> tuple[Suite, ...]:
    return (
        Suite(
            name="unit",
            cwd=FRONTEND_ROOT,
            command=("npx", "vitest", "run", "--color"),
            append_args=True,
            env=frontend_env(),
            description="Vitest jsdom tests/**/*.test.js",
        ),
        Suite(
            name="e2e-core",
            cwd=FRONTEND_ROOT,
            command=(
                "npx",
                "playwright",
                "test",
                "--config=tests/e2e/playwright.parallel.config.js",
                *core_e2e_specs(),
            ),
            append_args=True,
            env=frontend_env(),
            description=(
                "Core Playwright specs with worker-isolated app servers/DBs; "
                "excludes grants, veille, and performance"
            ),
        ),
        Suite(
            name="e2e-grants",
            cwd=FRONTEND_ROOT,
            command=(
                "npx",
                "playwright",
                "test",
                "--config=tests/e2e/playwright.grants.config.js",
            ),
            append_args=True,
            env=frontend_env(),
            description="Grants app Playwright specs",
        ),
        Suite(
            name="e2e-veille",
            cwd=FRONTEND_ROOT,
            command=(
                "npx",
                "playwright",
                "test",
                "--config=tests/e2e/veille.playwright.config.js",
            ),
            append_args=True,
            env=frontend_env(),
            description="Veille app Playwright specs",
        ),
        Suite(
            name="e2e-perf",
            cwd=FRONTEND_ROOT,
            command=(
                "npx",
                "playwright",
                "test",
                "--config=tests/e2e/playwright.perf.config.js",
            ),
            append_args=True,
            env=frontend_env(),
            description="Performance Playwright spec",
        ),
    )


SUITES = build_suites()


def run_suite(suite: Suite, extra_args: tuple[str, ...]) -> tuple[int, str]:
    env = os.environ.copy()
    if suite.env:
        env.update(suite.env)
    command = [*suite.command, *(extra_args if suite.append_args else ())]

    with PRINT_LOCK:
        print(f"\n=== frontend suite: {suite.name} ===", flush=True)
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
            with PRINT_LOCK:
                print(f"[{suite.name}] {line}", end="")
            output_lines.append(line)
    return process.wait(), "".join(output_lines)


def parse_counts_from_line(line: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "warnings": 0, "errors": 0}
    for match in COUNT_PATTERN.finditer(line):
        label = match.group("label")
        count = int(match.group("count"))
        if label == "passed":
            counts["passed"] += count
        elif label == "failed":
            counts["failed"] += count
        elif label.startswith("warning"):
            counts["warnings"] += count
        elif label.startswith("error"):
            counts["errors"] += count
    return counts


def add_counts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {key: left[key] + right[key] for key in left}


def parse_frontend_counts(output: str) -> dict[str, int]:
    lines = output.splitlines()

    # Vitest prints a dedicated "Tests" summary. Prefer it over "Test Files" so
    # file counts are not mistaken for test counts.
    for line in reversed(lines):
        normalized = line.strip()
        if normalized.startswith("Tests"):
            return parse_counts_from_line(normalized)

    # Playwright's list reporter commonly prints separate trailing lines such as
    # "1 failed" and "39 passed (1.2m)". Aggregate those final summary lines.
    counts = {"passed": 0, "failed": 0, "warnings": 0, "errors": 0}
    for line in lines[-40:]:
        normalized = line.strip()
        if not normalized or normalized.startswith("[") or "›" in normalized:
            continue
        if normalized.startswith("Test Files") or normalized.startswith("Tests"):
            continue
        line_counts = parse_counts_from_line(normalized)
        if any(line_counts.values()):
            counts = add_counts(counts, line_counts)
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

    previous: dict[str, str] = {}
    suites = overview.get("suites", [])
    if not isinstance(suites, list):
        return previous
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        name = suite.get("name")
        status = suite.get("status")
        if isinstance(name, str) and isinstance(status, str):
            previous[name] = status
    return previous


def result_from_run(suite: Suite, code: int, output: str, previous: dict[str, str]) -> SuiteResult:
    counts = parse_frontend_counts(output)
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


def exception_result(suite: Suite, exc: BaseException, previous: dict[str, str]) -> SuiteResult:
    return SuiteResult(
        name=suite.name,
        status="failed",
        returncode=1,
        message=f"runner exception: {exc}",
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
    return f"{COLORS[color]}{text}{RESET}" if enabled else text


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

    print("\n" + paint("=== Frontend test summary ===", "header", use_color))
    if not results:
        print("No frontend suites were selected.")
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
        description="Run frontend test suites and write a comparable JSON overview.",
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
        help="List available frontend suites and exit.",
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
        help="Colorize the final frontend test summary. Default: auto.",
    )
    parser.add_argument(
        "--workers",
        "--suite-workers",
        dest="suite_workers",
        type=int,
        default=DEFAULT_SUITE_WORKERS,
        help=(
            "Number of frontend suites to run concurrently. "
            f"Default: {DEFAULT_SUITE_WORKERS} (N3TX_FRONTEND_SUITE_WORKERS). "
            "--suite-workers is kept as a backward-compatible alias."
        ),
    )
    parser.add_argument(
        "test_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments passed to each selected test command after '--'.",
    )
    return parser.parse_args()


def runnable_suites(selected: set[str], previous: dict[str, str]) -> tuple[list[Suite], list[SuiteResult]]:
    suites: list[Suite] = []
    results: list[SuiteResult] = []
    for suite in SUITES:
        if suite.name not in selected:
            continue
        if not suite.cwd.exists():
            message = f"missing cwd: {suite.cwd}"
            print(f"Skipping missing suite {suite.name}: {suite.cwd}", file=sys.stderr)
            results.append(warning_result(suite, message, previous))
            continue
        suites.append(suite)
    return suites, results


def run_suites_parallel(
    suites: list[Suite],
    extra_args: tuple[str, ...],
    previous: dict[str, str],
    suite_workers: int,
    continue_on_failure: bool,
) -> list[SuiteResult]:
    if not suites:
        return []

    workers = max(1, min(suite_workers, len(suites)))
    print(f"\nRunning {len(suites)} frontend suites with {workers} suite worker(s).", flush=True)

    ordered_results: dict[str, SuiteResult] = {}
    pending = iter(suites)
    futures: dict[Future[tuple[int, str]], Suite] = {}
    stop_submitting = False

    def submit_next(executor: ThreadPoolExecutor) -> bool:
        try:
            suite = next(pending)
        except StopIteration:
            return False
        futures[executor.submit(run_suite, suite, extra_args)] = suite
        return True

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for _ in range(workers):
            if not submit_next(executor):
                break

        while futures:
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in done:
                suite = futures.pop(future)
                try:
                    code, output = future.result()
                    result = result_from_run(suite, code, output, previous)
                except BaseException as exc:  # pragma: no cover - defensive runner guard
                    result = exception_result(suite, exc, previous)
                ordered_results[suite.name] = result

                if result.status == "failed" and not continue_on_failure:
                    stop_submitting = True

            while not stop_submitting and len(futures) < workers:
                if not submit_next(executor):
                    break

    return [ordered_results[suite.name] for suite in suites if suite.name in ordered_results]


def main() -> int:
    args = parse_args()
    if args.list:
        for suite in SUITES:
            print(
                f"{suite.name}\tcwd={suite.cwd}\t"
                f"cmd={' '.join(suite.command)}\t{suite.description}"
            )
        return 0

    selected = set(args.suite or [suite.name for suite in SUITES])
    extra_args = tuple(arg for arg in args.test_args if arg != "--")
    overview_file = args.overview_file
    previous = load_previous_overview(overview_file)
    suites_to_run, results = runnable_suites(selected, previous)
    results.extend(
        run_suites_parallel(
            suites_to_run,
            extra_args,
            previous,
            args.suite_workers,
            args.continue_on_failure,
        )
    )

    save_overview(overview_file, overview_payload(results, sys.argv, overview_file))
    print_summary(results, overview_file, args.summary_color)

    failures = [result.name for result in results if result.status == "failed"]
    if failures:
        print("\nFailed suites:", ", ".join(failures), file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
