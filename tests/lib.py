from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/relay.py"


def run_cli(
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CLI), *map(str, args)]
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        env={**os.environ, "PYTHONUTF8": "1", **(env or {})},
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def run_wrapper(
    path: Path,
    *args: str,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    values = [str(path), *map(str, args)]
    command: list[str] | str = values
    use_shell = os.name == "nt"
    if use_shell:
        command = subprocess.list2cmdline(values)
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=use_shell,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"wrapper failed ({result.returncode}): {values}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def file_paths(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    snapshot: dict[str, tuple[bytes, int]] = {}
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            snapshot[path.relative_to(root).as_posix()] = (
                path.read_bytes(),
                path.stat().st_mtime_ns,
            )
    return snapshot


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def output_lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def assert_contains_all(text: str, values: Iterable[str]) -> None:
    for value in values:
        if value not in text:
            raise AssertionError(f"expected {value!r} in:\n{text}")
