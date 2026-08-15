#!/usr/bin/env python3
"""Select and run Relay Rules test suites on every supported platform."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SUITES = ("contract", "lifecycle", "migration", "selection")
WRAPPERS = {
    "scripts/install-rules.sh",
    "scripts/agent-install-rules.sh",
    "scripts/uninstall-rules.sh",
    "scripts/validate-installed-project.sh",
    "scripts/validate-rules-template.sh",
    "scripts/relay.cmd",
    "scripts/install-rules.cmd",
    "scripts/agent-install-rules.cmd",
    "scripts/uninstall-rules.cmd",
    "scripts/validate-installed-project.cmd",
    "scripts/validate-rules-template.cmd",
}


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def git_changed_files() -> list[str]:
    configured = os.environ.get("RELAY_CHANGED_FILES")
    if configured:
        return [line for line in configured.splitlines() if line]

    files: list[str] = []
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    for arguments in commands:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            files.extend(result.stdout.splitlines())
    return sorted(set(files))


def selected_suites(paths: Iterable[str]) -> list[str]:
    selected: list[str] = []

    def add(*names: str) -> None:
        for name in names:
            if name not in selected:
                selected.append(name)

    for raw_path in paths:
        path = raw_path.replace("\\", "/")
        if path in {"scripts/relay.py", "VERSION", "tests/lib.py"}:
            return list(SUITES)
        if path == ".gitattributes":
            add("contract", "lifecycle")
        elif path.startswith("templates/"):
            add("contract", "lifecycle")
        elif path in WRAPPERS:
            add("contract", "lifecycle")
        elif path == "tests/test_contract.py":
            add("contract")
        elif path == "tests/test_lifecycle.py":
            add("lifecycle")
        elif path == "tests/test_migration.py":
            add("migration")
        elif path in {"tests/test_selection.py", "tests/run.py", "tests/run.sh", "tests/run.cmd"}:
            add("selection")
        elif path in {"README.md", "README.zh-CN.md"} or path.startswith(
            ".github/workflows/"
        ):
            add("contract")
    return selected or ["contract"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="run every suite")
    parser.add_argument(
        "--suite",
        action="append",
        choices=SUITES,
        default=[],
        help="run one suite; may be repeated",
    )
    parser.add_argument("--list", action="store_true", help="print selected suites only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all:
        selected = list(SUITES)
    elif args.suite:
        selected = unique(args.suite)
    else:
        selected = selected_suites(git_changed_files())

    if args.list:
        print(*selected, sep="\n")
        return 0

    print(f"Selected suites: {' '.join(selected)}", flush=True)
    failed = False
    for suite in selected:
        print(f"==> {suite}", flush=True)
        result = subprocess.run([sys.executable, str(HERE / f"test_{suite}.py")], check=False)
        failed = failed or result.returncode != 0
    print("SELECTED SUITES FAILED" if failed else "SELECTED SUITES PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
