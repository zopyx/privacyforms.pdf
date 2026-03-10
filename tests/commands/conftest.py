"""Shared fixtures for command tests."""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click test runner."""
    return CliRunner()
