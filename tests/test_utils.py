"""Tests for utility functions."""

from __future__ import annotations

import logging

from privacyforms_pdf.utils import (
    _install_pypdf_warning_filter,
    _PypdfWarningFilter,
    cluster_y_positions,
    get_available_geometry_backends,
    has_geometry_support,
)


class TestClusterYPositions:
    """Tests for cluster_y_positions."""

    def test_empty(self) -> None:
        """It returns an empty dict for an empty list."""
        assert cluster_y_positions([]) == {}

    def test_single(self) -> None:
        """It maps a single position to itself."""
        assert cluster_y_positions([42.0]) == {42.0: 42.0}

    def test_all_same(self) -> None:
        """It collapses duplicate positions into one cluster."""
        assert cluster_y_positions([10.0, 10.0, 10.0]) == {10.0: 10.0}

    def test_two_clusters(self) -> None:
        """It separates far-apart positions into distinct clusters."""
        result = cluster_y_positions([10.0, 12.0, 100.0, 102.0])
        assert result[10.0] == result[12.0]
        assert result[100.0] == result[102.0]
        assert result[10.0] != result[100.0]


class TestPypdfWarningFilter:
    """Tests for _PypdfWarningFilter."""

    def test_filters_annotation_sizes(self) -> None:
        """It drops log records containing 'Annotation sizes differ:'."""
        filt = _PypdfWarningFilter()
        record = logging.LogRecord(
            "pypdf", logging.WARNING, "", 0, "Annotation sizes differ: 1 vs 2", (), None
        )
        assert filt.filter(record) is False

    def test_passes_other_messages(self) -> None:
        """It allows unrelated log records through."""
        filt = _PypdfWarningFilter()
        record = logging.LogRecord("pypdf", logging.WARNING, "", 0, "Some other warning", (), None)
        assert filt.filter(record) is True

    def test_install_idempotent(self) -> None:
        """It adds the filter only once per logger."""
        _install_pypdf_warning_filter()
        _install_pypdf_warning_filter()
        logger = logging.getLogger("pypdf")
        assert sum(1 for f in logger.filters if isinstance(f, _PypdfWarningFilter)) == 1


class TestGeometryHelpers:
    """Tests for geometry helper functions."""

    def test_get_available_geometry_backends(self) -> None:
        """It always returns a list containing 'pypdf'."""
        assert get_available_geometry_backends() == ["pypdf"]

    def test_has_geometry_support(self) -> None:
        """It always reports geometry support as available."""
        assert has_geometry_support() is True
