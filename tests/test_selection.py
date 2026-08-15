from __future__ import annotations

import os
import subprocess
import sys
import unittest

from lib import ROOT, output_lines


def selected(*paths: str) -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests/run.py"), "--list"],
        cwd=ROOT,
        env={**os.environ, "RELAY_CHANGED_FILES": "\n".join(paths)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return output_lines(result)


class SelectionTests(unittest.TestCase):
    def test_docs_select_only_contract(self) -> None:
        self.assertEqual(["contract"], selected("README.md"))

    def test_templates_select_contract_and_lifecycle(self) -> None:
        self.assertEqual(
            ["contract", "lifecycle"],
            selected("templates/core/AGENTS.md"),
        )

    def test_shared_cli_selects_every_suite(self) -> None:
        self.assertEqual(
            ["contract", "lifecycle", "migration", "selection"],
            selected("scripts/relay.py"),
        )

    def test_specific_test_selects_itself(self) -> None:
        self.assertEqual(["migration"], selected("tests/test_migration.py"))

    def test_windows_wrapper_selects_contract_and_lifecycle(self) -> None:
        self.assertEqual(
            ["contract", "lifecycle"],
            selected(r"scripts\install-rules.cmd"),
        )

    def test_line_ending_contract_selects_lifecycle(self) -> None:
        self.assertEqual(
            ["contract", "lifecycle"],
            selected(".gitattributes"),
        )


if __name__ == "__main__":
    unittest.main()
