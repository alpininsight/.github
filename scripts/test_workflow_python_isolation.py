"""Regression tests: workflow Python must not import from a checkout cwd."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CREATE_RELEASE = WORKFLOWS / "create-release.yml"
PYTHON_COMMAND = re.compile(
    r"(?:^|[\n;&]|\|\||&&)\s*(python3?)\s+([^\n]*)",
    re.MULTILINE,
)


def _run_scripts(text: str) -> list[tuple[int, str]]:
    """Return (line_number, script) for every workflow `run:` step."""
    scripts: list[tuple[int, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)run:\s*(.*)$", lines[index])
        if match is None:
            index += 1
            continue
        indent = len(match.group(1))
        rest = match.group(2)
        start = index + 1
        if rest in {"|", "|-", ">+", ">", ">-", "|+"}:
            block: list[str] = []
            index += 1
            while index < len(lines):
                line = lines[index]
                if line.strip() == "" or len(line) - len(line.lstrip(" ")) > indent:
                    block.append(line)
                    index += 1
                    continue
                break
            scripts.append((start, "\n".join(block)))
            continue
        scripts.append((start, rest))
        index += 1
    return scripts


def _python_invocations(script: str) -> list[str]:
    invocations: list[str] = []
    for match in PYTHON_COMMAND.finditer(script):
        line = script[: match.start()].count("\n")
        stripped = script.splitlines()[line].lstrip()
        if stripped.startswith("#"):
            continue
        invocations.append(f"{match.group(1)} {match.group(2).strip()}")
    return invocations


def _has_isolated_flag(invocation: str) -> bool:
    try:
        tokens = invocation.split()
    except Exception:
        return False
    if not tokens or tokens[0] not in {"python", "python3"}:
        return False
    for token in tokens[1:]:
        if token in {"-c", "-", "--"} or not token.startswith("-"):
            break
        if "I" in token[1:] and not token.startswith("--"):
            return True
    return False


class WorkflowPythonIsolationTests(unittest.TestCase):
    def test_every_workflow_python_invocation_is_isolated(self):
        violations: list[str] = []
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for line, script in _run_scripts(path.read_text(encoding="utf-8")):
                for invocation in _python_invocations(script):
                    if not _has_isolated_flag(invocation):
                        violations.append(f"{path.relative_to(ROOT)}:{line}: {invocation}")
        self.assertEqual(violations, [])

    def test_create_release_loads_scripts_from_the_pinned_catalog_checkout(self):
        text = CREATE_RELEASE.read_text(encoding="utf-8")
        self.assertIn("repository: alpininsight/.github", text)
        self.assertIn("ref: ${{ inputs.contract_revision }}", text)
        self.assertIn("path: public-ci", text)
        self.assertIn("path: source", text)
        self.assertNotIn("\n          path: .\n", text)
        self.assertIn("'git', '-C', str(workspace / 'source'), 'rev-parse'", text)
        self.assertIn("[sys.executable, '-I', '-B', str(directory / 'create_github_release.py')]", text)
        self.assertNotIn("env['PYTHONPATH']", text)
        self.assertNotIn("raw.githubusercontent.com/alpininsight/.github/{revision}", text)

    def test_hostile_hashlib_in_cwd_is_imported_without_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "hashlib.py").write_text(
                'raise SystemExit("hostile hashlib imported")\n',
                encoding="utf-8",
            )
            probe = "import hashlib; print(hashlib.sha256(b'x').hexdigest())"
            loose = subprocess.run(
                ["python3", "-c", probe],
                cwd=directory,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(loose.returncode, 0)
            self.assertIn("hostile hashlib imported", loose.stdout + loose.stderr)

    def test_isolated_python_ignores_hostile_hashlib_in_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "hashlib.py").write_text(
                'raise SystemExit("hostile hashlib imported")\n',
                encoding="utf-8",
            )
            probe = "import hashlib; print(hashlib.sha256(b'x').hexdigest())"
            isolated = subprocess.run(
                ["python3", "-I", "-c", probe],
                cwd=directory,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(isolated.returncode, 0)
            self.assertEqual(isolated.stdout.strip(), hashlib.sha256(b"x").hexdigest())
            self.assertNotIn("hostile hashlib imported", isolated.stdout + isolated.stderr)

    def test_isolated_stdin_script_ignores_hostile_hashlib_in_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "hashlib.py").write_text(
                'raise SystemExit("hostile hashlib imported")\n',
                encoding="utf-8",
            )
            script = "import hashlib\nprint(hashlib.sha256(b'x').hexdigest())\n"
            isolated = subprocess.run(
                ["python3", "-I", "-"],
                cwd=directory,
                input=script,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(isolated.returncode, 0)
            self.assertEqual(isolated.stdout.strip(), hashlib.sha256(b"x").hexdigest())


if __name__ == "__main__":
    unittest.main()
