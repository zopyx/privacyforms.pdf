"""Tests for json_utils safety helpers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from privacyforms_pdf.json_utils import (
    MAX_JSON_DEPTH,
    check_json_depth,
    check_json_size,
    load_json_object,
    require_json_object,
    safe_json_loads,
)


class TestCheckJsonDepth:
    """Tests for check_json_depth."""

    def test_shallow_dict_passes(self) -> None:
        """A flat dict passes the depth check."""
        check_json_depth({"a": 1, "b": 2})

    def test_exact_limit_passes(self) -> None:
        """A structure at exactly the limit passes."""
        data: dict[str, object] = {"a": "b"}
        for _ in range(MAX_JSON_DEPTH - 1):
            data = {"nested": data}
        check_json_depth(data)

    def test_exceeds_limit_raises(self) -> None:
        """A structure exceeding the limit raises ValueError."""
        data: dict[str, object] = {"a": "b"}
        for _ in range(MAX_JSON_DEPTH):
            data = {"nested": data}
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            check_json_depth(data)

    def test_nested_lists(self) -> None:
        """Nested lists are counted correctly."""
        data: list[object] = [1]
        for _ in range(MAX_JSON_DEPTH):
            data = [data]
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            check_json_depth(data)

    def test_mixed_dict_list(self) -> None:
        """Mixed dict/list nesting is counted correctly."""
        data: dict[str, object] = {"a": [1]}
        for _ in range(MAX_JSON_DEPTH):
            data = {"nested": [data]}
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            check_json_depth(data)

    def test_custom_max_depth(self) -> None:
        """A custom max_depth is respected."""
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            check_json_depth({"a": {"b": {"c": 1}}}, max_depth=2)


class TestSafeJsonLoads:
    """Tests for safe_json_loads."""

    def test_valid_json(self) -> None:
        """Valid JSON loads correctly."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_deep_json_raises(self) -> None:
        """Deeply nested JSON raises ValueError."""
        data: dict[str, object] = {"a": "b"}
        for _ in range(MAX_JSON_DEPTH + 1):
            data = {"nested": data}
        with pytest.raises(ValueError, match="exceeds maximum nesting depth"):
            safe_json_loads(json.dumps(data))

    def test_recursion_error_handled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RecursionError during json.loads is converted to ValueError."""
        import json as json_module

        def _raise_recursion(text: str) -> object:
            raise RecursionError("boom")

        monkeypatch.setattr(json_module, "loads", _raise_recursion)
        with pytest.raises(ValueError, match="too deeply nested"):
            safe_json_loads("{}")


class TestRequireJsonObject:
    """Tests for require_json_object."""

    def test_dict_passes(self) -> None:
        """A dict is accepted."""
        result = require_json_object({"a": 1})
        assert result == {"a": 1}

    def test_list_rejected(self) -> None:
        """A list raises ValueError."""
        with pytest.raises(ValueError, match="top-level object"):
            require_json_object([1, 2, 3])

    def test_str_keys(self) -> None:
        """Non-string keys are coerced to strings."""
        result = require_json_object({1: "value"})
        assert result == {"1": "value"}


class TestCheckJsonSize:
    """Tests for check_json_size."""

    def test_small_file_passes(self, tmp_path: Path) -> None:
        """A small file passes the size check."""
        f = tmp_path / "small.json"
        f.write_text('{"a": 1}', encoding="utf-8")
        check_json_size(f, max_size=1024)

    def test_large_file_raises(self, tmp_path: Path) -> None:
        """A file exceeding max_size raises ValueError."""
        f = tmp_path / "large.json"
        f.write_text("x" * 100, encoding="utf-8")
        with pytest.raises(ValueError, match="too large"):
            check_json_size(f, max_size=50)


class TestLoadJsonObject:
    """Tests for load_json_object."""

    def test_valid_file(self, tmp_path: Path) -> None:
        """A valid JSON object file loads correctly."""
        f = tmp_path / "data.json"
        f.write_text('{"name": "John"}', encoding="utf-8")
        result = load_json_object(f)
        assert result == {"name": "John"}

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        """A missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_json_object(tmp_path / "missing.json")

    def test_directory_raises(self, tmp_path: Path) -> None:
        """A directory path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_json_object(tmp_path)

    def test_non_object_raises(self, tmp_path: Path) -> None:
        """A non-object JSON file raises ValueError."""
        f = tmp_path / "array.json"
        f.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="top-level object"):
            load_json_object(f)

    def test_oversized_raises(self, tmp_path: Path) -> None:
        """An oversized file raises ValueError."""
        f = tmp_path / "big.json"
        f.write_text("x" * 200, encoding="utf-8")
        with pytest.raises(ValueError, match="too large"):
            load_json_object(f, max_size=100)
