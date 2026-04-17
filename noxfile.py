"""Nox configuration for privacyforms-pdf.

This module configures nox sessions for testing across multiple Python versions
including free-threaded variants (3.13t, 3.14t).
"""

from __future__ import annotations

import nox

# Python versions to test against
PYTHON_VERSIONS = ["3.12", "3.13", "3.14", "3.14t"]

# Default sessions to run when no session is specified
nox.options.sessions = ["test"]


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def test(session: nox.Session) -> None:
    """Run the test suite across Python versions.

    Args:
        session: The nox session object.
    """
    # Install dependencies using uv
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    # Run tests
    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "pytest",
        "-v",
        "--cov",
        "--cov-report=term-missing",
        "--cov-report=html",
    )


@nox.session(python="3.13", venv_backend="uv")
def lint(session: nox.Session) -> None:
    """Run linting checks.

    Args:
        session: The nox session object.
    """
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "ruff",
        "check",
        "privacyforms_pdf",
        "tests",
    )
    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "ruff",
        "format",
        "--check",
        "privacyforms_pdf",
        "tests",
    )


@nox.session(python="3.13", venv_backend="uv")
def type_check(session: nox.Session) -> None:
    """Run type checking.

    Args:
        session: The nox session object.
    """
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "ty",
        "check",
    )


@nox.session(python="3.13", venv_backend="uv")
def format_code(session: nox.Session) -> None:
    """Format code with ruff.

    Args:
        session: The nox session object.
    """
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "ruff",
        "format",
        "privacyforms_pdf",
        "tests",
    )


@nox.session(python="3.13", venv_backend="uv")
def fix(session: nox.Session) -> None:
    """Auto-fix linting issues.

    Args:
        session: The nox session object.
    """
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "ruff",
        "check",
        "--fix",
        "privacyforms_pdf",
        "tests",
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend="uv")
def check_all(session: nox.Session) -> None:
    """Run all checks (lint, type-check, test) for a Python version.

    Args:
        session: The nox session object.
    """
    session.run_install(
        "uv",
        "sync",
        "--group",
        "dev",
        env={"UV_PYTHON": session.virtualenv.interpreter},  # type: ignore
    )

    # Run tests
    session.run(
        "uv",
        "run",
        "--python",
        session.virtualenv.interpreter,  # type: ignore
        "pytest",
        "-v",
        "--cov",
        "--cov-report=term-missing",
    )
