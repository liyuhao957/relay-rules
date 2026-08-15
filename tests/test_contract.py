from __future__ import annotations

import os
import unittest

from lib import ROOT, run_cli, run_wrapper


class ContractTests(unittest.TestCase):
    def test_source_template_is_valid(self) -> None:
        result = run_cli("validate-template")
        self.assertIn("is valid", result.stdout)

    def test_source_footprint_is_fixed_and_project_aware(self) -> None:
        self.assertFalse((ROOT / "templates/skills").exists())
        files = sorted(path for path in (ROOT / "templates").rglob("*") if path.is_file())
        self.assertEqual(
            {
                "templates/core/AGENTS.md",
                "templates/project/.relay/index.md",
                "templates/project/.relay/project.md",
                "templates/project/.relay/workflows/adapt.md",
                "templates/project/.relay/workflows/maintain.md",
            },
            {path.relative_to(ROOT).as_posix() for path in files},
        )
        core_lines = (ROOT / "templates/core/AGENTS.md").read_text().splitlines()
        self.assertLessEqual(len(core_lines), 50)
        core = "\n".join(core_lines)
        self.assertIn(".relay/index.md", core)
        self.assertIn(".relay/workflows/maintain.md", core)
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

        workflow = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
        self.assertIn("Verify Bash lifecycle", workflow)
        self.assertIn("install-rules.sh --target", workflow)
        self.assertIn("uninstall-rules.sh --target", workflow)
        self.assertIn("Verify PowerShell lifecycle", workflow)
        self.assertIn("Verify Command Prompt lifecycle", workflow)
        self.assertGreaterEqual(workflow.count("install-rules.cmd --target"), 2)
        self.assertGreaterEqual(workflow.count("uninstall-rules.cmd --target"), 2)

    def test_install_has_one_mode_and_defaults_to_the_current_directory(self) -> None:
        help_text = run_cli("install", "--help").stdout
        self.assertIn("default: current directory", help_text)
        self.assertNotIn("--profile", help_text)
        self.assertNotIn("--agents", help_text)
        self.assertNotIn("--upgrade", help_text)
        self.assertNotIn("--force", help_text)

        doctor_help = run_cli("doctor", "--help").stdout
        self.assertIn("--require-adapted", doctor_help)

    def test_readmes_describe_the_project_aware_cross_platform_contract(self) -> None:
        for name in ("README.md", "README.zh-CN.md"):
            with self.subTest(name=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn(".relay/index.md", text)
                self.assertIn(".relay/project.md", text)
                self.assertIn("AGENTS.override.md", text)
                self.assertIn("--require-adapted", text)
                self.assertIn("Windows PowerShell", text)
                self.assertIn("code.claude.com/docs/en/memory", text)
                self.assertIn("learn.chatgpt.com/docs/agent-configuration/agents-md", text)
                self.assertNotIn("One command. Two files.", text)
                self.assertNotIn("一条命令，2 个文件", text)


if __name__ == "__main__":
    unittest.main()
