"""Regression tests for removing Gitleaks from a pre-commit config in python-quality.yml."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/python-quality.yml"

CONFIG = """\
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
exclude: ^(docs/|vendor/)
default_language_version:
  python: python3
files: ^src/
"""

CONFIG_GITLEAKS_NOT_LAST = """\
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.30.1
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
exclude: ^(docs/|vendor/)
"""


def awk_from_workflow() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.find("awk '")
    end = text.find("' .pre-commit-config.yaml", start)
    if start < 0 or end < 0:
        raise AssertionError("Could not extract the Gitleaks awk filter from the quality workflow")
    program = text[start + len("awk '"):end]
    return "\n".join(line[14:] if line.startswith("              ") else line for line in program.splitlines())


def apply_filter(config: str) -> str:
    result = subprocess.run(
        ["awk", awk_from_workflow()],
        input=config,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


class PreCommitGitleaksFilterTests(unittest.TestCase):
    def test_keeps_top_level_keys_when_gitleaks_is_last_repo(self):
        filtered = apply_filter(CONFIG)
        self.assertNotIn("gitleaks/gitleaks", filtered)
        self.assertIn("pre-commit/pre-commit-hooks", filtered)
        self.assertIn("exclude: ^(docs/|vendor/)", filtered)
        self.assertIn("default_language_version:", filtered)
        self.assertIn("python: python3", filtered)
        self.assertIn("files: ^src/", filtered)

    def test_resets_skip_on_the_next_repo(self):
        filtered = apply_filter(CONFIG_GITLEAKS_NOT_LAST)
        self.assertNotIn("gitleaks/gitleaks", filtered)
        self.assertIn("pre-commit/pre-commit-hooks", filtered)
        self.assertIn("exclude: ^(docs/|vendor/)", filtered)


if __name__ == "__main__":
    unittest.main()
