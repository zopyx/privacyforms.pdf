"""Shared JSON safety helpers for CLI and extractor workflows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MAX_JSON_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_JSON_DEPTH = 50


def check_json_size(path: Path, max_size: int = MAX_JSON_SIZE) -> None:
    """Raise ValueError if *path* exceeds *max_size* bytes."""
    size = path.stat().st_size
    if size > max_size:
        raise ValueError(
            f"JSON file too large: {path.name} ({size} bytes). Maximum allowed is {max_size} bytes."
        )


def check_json_depth(obj: object, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Raise ValueError if *obj* exceeds *max_depth* levels of nesting.

    Uses an iterative stack to avoid recursion limits.
    """
    # Stack of (object, current_depth)
    stack: list[tuple[object, int]] = [(obj, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > max_depth:
            raise ValueError(f"JSON structure exceeds maximum nesting depth of {max_depth}")
        if isinstance(current, dict):
            for value in current.values():
                stack.append((value, depth + 1))
        elif isinstance(current, list):
            for item in current:
                stack.append((item, depth + 1))


def safe_json_loads(text: str) -> object:
    """Parse JSON with a safe depth limit."""
    try:
        result = json.loads(text)
    except RecursionError as exc:
        raise ValueError(
            f"JSON structure is too deeply nested (maximum depth {MAX_JSON_DEPTH})"
        ) from exc
    check_json_depth(result)
    return result


def require_json_object(data: object) -> dict[str, Any]:
    """Require a top-level JSON object."""
    if not isinstance(data, Mapping):
        raise ValueError(
            "JSON data must be a top-level object with field names or field IDs as keys"
        )
    return {str(key): value for key, value in data.items()}


def load_json_object(path: str | Path, *, max_size: int = MAX_JSON_SIZE) -> dict[str, Any]:
    """Load a JSON object from *path* with size and depth protections."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(f"Path is not a file: {file_path}")

    check_json_size(file_path, max_size=max_size)
    text = file_path.read_text(encoding="utf-8")
    return require_json_object(safe_json_loads(text))
