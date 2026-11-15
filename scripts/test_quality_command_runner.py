"""Regression tests for fail-fast caller-command execution in python-quality.yml."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/python-quality.yml"
WRAPPER = 'run: bash -euo pipefail -c "$CMD"'


class QualityCommandRunnerTests(unittest.TestCase):
    def test_workflow_uses_failfast_wrapper(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn('run: bash -c "$CMD"', text)
        self.assertEqual(text.count(WRAPPER), 5)

    def test_pipeline_failure_is_not_hidden(self):
        hidden = subprocess.run(["bash", "-c", "false | true"], check=False)
        self.assertEqual(hidden.returncode, 0)
        wrapped = subprocess.run(["bash", "-euo", "pipefail", "-c", "false | true"], check=False)
        self.assertNotEqual(wrapped.returncode, 0)

    def test_multiline_command_fails_on_an_early_error(self):
        hidden = subprocess.run(["bash", "-c", "false\ntrue"], check=False)
        self.assertEqual(hidden.returncode, 0)
        wrapped = subprocess.run(["bash", "-euo", "pipefail", "-c", "false\ntrue"], check=False)
        self.assertNotEqual(wrapped.returncode, 0)


if __name__ == "__main__":
    unittest.main()
