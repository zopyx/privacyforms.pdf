from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

try:
    from .pdf_schema import FieldLayout, PDFField, RowGroup
except ImportError:
    from pdf_schema import FieldLayout, PDFField, RowGroup  # type: ignore[import-not-found]


def _build_layout(
    page_index: int | None,
    rect: list[float] | None,
) -> FieldLayout | None:
    """Build FieldLayout from raw rectangle."""
    if rect is None or len(rect) != 4:
        return None
    x1, y1, x2, y2 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    return FieldLayout(
        page=page_index,
        x=int(min(x1, x2)),
        y=int(min(y1, y2)),
        width=int(abs(x2 - x1)),
        height=int(abs(y2 - y1)),
    )


def _get_layout_x(field: PDFField) -> int:
    """Return the x coordinate of a field's layout, or 0 if unknown."""
    return field.layout.x if field.layout is not None and field.layout.x is not None else 0


def _build_rows(fields: Sequence[PDFField], y_tolerance: int = 15) -> list[RowGroup]:
    """Group fields into visual rows based on layout proximity."""
    # Group by page
    page_fields: dict[int, list[PDFField]] = {}
    for f in fields:
        if f.layout is None or f.layout.page is None:
            continue
        page_fields.setdefault(f.layout.page, []).append(f)

    rows: list[RowGroup] = []
    for page_idx in sorted(page_fields.keys()):
        pf = page_fields[page_idx]
        # Sort by y descending (top of page first)
        pf.sort(key=lambda f: -(f.layout.y if f.layout else 0))

        current_row: list[PDFField] = []
        current_y = 0
        has_current = False
        for f in pf:
            fy = f.layout.y if f.layout is not None and f.layout.y is not None else 0
            if not has_current:
                current_row = [f]
                current_y = fy
                has_current = True
                continue
            if abs(fy - current_y) <= y_tolerance:
                current_row.append(f)
            else:
                # Sort row by x ascending
                current_row.sort(key=_get_layout_x)
                rows.append(RowGroup(fields=current_row, page_index=page_idx))
                current_row = [f]
                current_y = fy
        if current_row:
            current_row.sort(key=_get_layout_x)
            rows.append(RowGroup(fields=current_row, page_index=page_idx))

    return rows
