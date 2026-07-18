"""
Shared fixtures and helpers for docmap.cli tests.
"""

import subprocess
import sys

import pytest


@pytest.fixture
def run_cli():
    """Return a callable that invokes `python -m docmap.cli` via subprocess."""

    def _run_cli(args, input_text=None, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "docmap.cli", *args],
            input=input_text,
            capture_output=True,
            text=True,
            cwd=cwd,
        )

    return _run_cli


@pytest.fixture
def sample_project(tmp_path):
    """Build a small throwaway project tree and return its root."""
    (tmp_path / "mod.py").write_text('def hello():\n    """Say hello."""\n    pass\n')
    return tmp_path
