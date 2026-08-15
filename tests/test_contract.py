from __future__ import annotations

import os
import unittest

from lib import ROOT, run_cli, run_wrapper


class ContractTests(unittest.TestCase):
    def test_source_template_is_valid(self) -> None:
        result = run_cli("validate-template")
        self.assertIn("is valid", result.stdout)

    def test_source_footprint_is_intentionally_small(self) -> None:
        self.assertFalse((ROOT / "templates/project").exists())
        self.assertFalse((ROOT / "templates/skills").exists())
        files = sorted(path for path in (ROOT / "templates").rglob("*") if path.is_file())
        self.assertEqual(1, len(files))
        core_lines = (ROOT / "templates/core/AGENTS.md").read_text().splitlines()
        self.assertLessEqual(len(core_lines), 40)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.cmd text eol=crlf", attributes)
        self.assertIn("*.sh text eol=lf", attributes)

    def test_platform_wrappers_expose_the_cli(self) -> None:
        script_names = (
            "install-rules",
            "uninstall-rules",
            "validate-installed-project",
            "validate-rules-template",
        )
        for name in script_names:
            self.assertTrue((ROOT / "scripts" / f"{name}.sh").is_file())
            self.assertTrue((ROOT / "scripts" / f"{name}.cmd").is_file())

        commands = {
            "install-rules": "install",
            "uninstall-rules": "remove",
            "validate-installed-project": "doctor",
            "validate-rules-template": "validate-template",
        }
        for name, command in commands.items():
            content = (ROOT / "scripts" / f"{name}.cmd").read_text(encoding="utf-8")
            self.assertIn(f'call "%~dp0relay.cmd" {command} %*', content)

        relay_cmd = (ROOT / "scripts/relay.cmd").read_text(encoding="utf-8")
        self.assertIn('set "PYTHONUTF8=1"', relay_cmd)
        self.assertEqual(2, relay_cmd.count("sys.version_info >= (3, 9)"))
        self.assertIn('python "%~dp0relay.py" %*', relay_cmd)
        self.assertIn('py -3 "%~dp0relay.py" %*', relay_cmd)
        test_cmd = (ROOT / "tests/run.cmd").read_text(encoding="utf-8")
        self.assertIn('set "PYTHONUTF8=1"', test_cmd)
        self.assertEqual(2, test_cmd.count("sys.version_info >= (3, 9)"))
        self.assertIn('python "%~dp0run.py" %*', test_cmd)
        self.assertIn('py -3 "%~dp0run.py" %*', test_cmd)

        suffix = ".cmd" if os.name == "nt" else ".sh"
        for name in script_names:
            with self.subTest(name=name):
                result = run_wrapper(ROOT / "scripts" / f"{name}{suffix}", "--help")
                self.assertEqual(0, result.returncode, result.stderr)

        self.assertTrue((ROOT / "scripts/relay.cmd").is_file())
        self.assertTrue((ROOT / "tests/run.cmd").is_file())
        if os.name == "nt":
            self.assertEqual(
                0,
                run_wrapper(ROOT / "scripts/relay.cmd", "--help").returncode,
            )
            self.assertEqual(
                0,
                run_wrapper(ROOT / "tests/run.cmd", "--help").returncode,
            )

    def test_install_has_one_mode_and_defaults_to_the_current_directory(self) -> None:
        help_text = run_cli("install", "--help").stdout
        self.assertIn("default: current directory", help_text)
        self.assertNotIn("--profile", help_text)
        self.assertNotIn("--agents", help_text)
        self.assertNotIn("--upgrade", help_text)
        self.assertNotIn("--force", help_text)


if __name__ == "__main__":
    unittest.main()
