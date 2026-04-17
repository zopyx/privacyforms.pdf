"""Utility functions for privacyforms-pdf."""

from __future__ import annotations

import logging


def cluster_y_positions(
    y_positions: list[float], default_threshold: float = 15.0
) -> dict[float, float]:
    """Cluster Y positions into rows using adaptive gap detection.

    This function analyzes the distribution of Y coordinates and groups
    positions that are likely part of the same visual row. It uses
    statistical analysis of gaps between consecutive positions to
    automatically determine an appropriate threshold.

    The algorithm works by:
    1. Sorting all Y positions
    2. Calculating gaps between consecutive positions
    3. Using percentile analysis to find natural row breaks
    4. Clustering positions where gaps are smaller than the adaptive threshold

    This approach adapts to different form layouts - tight forms with small
    row spacing and loose forms with large row spacing are both handled well.

    Args:
        y_positions: List of Y coordinates from form fields.
        default_threshold: Maximum within-row gap (default 15.0).

    Returns:
        Dictionary mapping each original Y position to its cluster center.
    """
    if not y_positions:
        return {}

    if len(y_positions) == 1:
        return {y_positions[0]: y_positions[0]}

    # Sort positions and remove duplicates
    sorted_y = sorted(set(y_positions))

    if len(sorted_y) == 1:
        return {sorted_y[0]: sorted_y[0]}

    # Calculate gaps between consecutive positions
    gaps = [sorted_y[i + 1] - sorted_y[i] for i in range(len(sorted_y) - 1)]
    sorted_gaps = sorted(gaps)

    # Find the within-row threshold using gap analysis
    # Strategy: find the largest gap that is likely "within-row" vs "between-row"
    # We use the 25th percentile of gaps as the base threshold
    # This separates tight clusters (within rows) from large gaps (between rows)
    q1_idx = len(sorted_gaps) // 4  # 25th percentile

    # Within-row variation: use 25th percentile as base
    # This captures the typical "within row" variation
    within_row_threshold = sorted_gaps[q1_idx] if q1_idx < len(sorted_gaps) else default_threshold

    # Adaptive threshold: 75th percentile + small buffer, capped at reasonable max
    # The buffer accounts for slight variations, but we cap it to prevent over-grouping
    threshold = min(within_row_threshold * 1.5, default_threshold)

    # Ensure threshold is reasonable (between 10 and default_threshold)
    threshold = max(10.0, min(threshold, default_threshold))

    # Cluster positions
    clusters: list[list[float]] = []
    current_cluster: list[float] = [sorted_y[0]]

    for i in range(1, len(sorted_y)):
        gap = sorted_y[i] - sorted_y[i - 1]
        if gap <= threshold:
            # Same cluster (row)
            current_cluster.append(sorted_y[i])
        else:
            # New cluster (row)
            clusters.append(current_cluster)
            current_cluster = [sorted_y[i]]

    clusters.append(current_cluster)

    # Map each position to its cluster center (mean of cluster)
    position_to_cluster: dict[float, float] = {}
    for cluster in clusters:
        center = sum(cluster) / len(cluster)
        for pos in cluster:
            position_to_cluster[pos] = center

    return position_to_cluster


class _PypdfWarningFilter(logging.Filter):
    """Filter noisy non-fatal pypdf warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "Annotation sizes differ:" not in record.getMessage()


def _install_pypdf_warning_filter() -> None:
    """Install warning filter once for pypdf logger."""
    for logger_name in ("pypdf", "pypdf.generic._link"):
        logger = logging.getLogger(logger_name)
        if not any(isinstance(f, _PypdfWarningFilter) for f in logger.filters):
            logger.addFilter(_PypdfWarningFilter())



