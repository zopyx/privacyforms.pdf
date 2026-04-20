"""Extract nearby text blocks (labels, descriptions, etc.) for PDF form fields.

This module is optional. It requires PyMuPDF (``fitz``) which can be installed via:

    pip install privacyforms.pdf[labels]

"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from privacyforms_pdf.schema import (
    FieldLayout,
    FieldTextBlock,
    FieldTextDirection,
    FieldTextRole,
    PDFField,
    PDFPage,
    PDFTextBlock,
    TextFormat,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Heuristic patterns for role classification
# ---------------------------------------------------------------------------

_DESCRIPTION_KEYWORDS = re.compile(
    r"\b(please|note|hint|tip|example|description|info)\b|e\.g\.[\s,]",
    re.IGNORECASE,
)
_HELPER_KEYWORDS = re.compile(
    r"\b(required|optional|must|should|mandatory)\b|\*",
    re.IGNORECASE,
)
_INSTRUCTION_KEYWORDS = re.compile(
    r"\b(instruction|guide|step|follow|read|see below)\b",
    re.IGNORECASE,
)

_MAX_TEXT_BLOCK_LEN = 100_000
_DEFAULT_MAX_DISTANCE = 100.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _RawTextBlock(NamedTuple):
    """Intermediate text block with PDF-native coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def _require_fitz() -> Any:
    """Import fitz and raise a helpful error if it is missing."""
    try:
        import fitz
    except ImportError as exc:
        raise ImportError(
            "Label extraction requires PyMuPDF. "
            "Install it with: pip install privacyforms.pdf[labels]"
        ) from exc
    return fitz


def _rect_contains(
    fx0: float,
    fy0: float,
    fx1: float,
    fy1: float,
    tx0: float,
    ty0: float,
    tx1: float,
    ty1: float,
) -> bool:
    """Return True if the text block is fully inside the field rectangle."""
    return fx0 <= tx0 and fy0 <= ty0 and fx1 >= tx1 and fy1 >= ty1


def _compute_direction_distance(
    fx0: float,
    fy0: float,
    fx1: float,
    fy1: float,
    tx0: float,
    ty0: float,
    tx1: float,
    ty1: float,
) -> tuple[FieldTextDirection, float | None]:
    """Determine relative direction and Euclidean distance between field and text block.

    PDF-native coordinates are assumed: y increases upward.
    """
    x_overlap = not (tx1 < fx0 or tx0 > fx1)
    y_overlap = not (ty1 < fy0 or ty0 > fy1)

    if x_overlap and y_overlap:
        return "inside", 0.0

    # Horizontal / vertical edge distances
    if tx1 < fx0:
        dx = fx0 - tx1
    elif tx0 > fx1:
        dx = tx0 - fx1
    else:
        dx = 0.0

    if ty1 < fy0:
        dy = fy0 - ty1
    elif ty0 > fy1:
        dy = ty0 - fy1
    else:
        dy = 0.0

    distance = (dx * dx + dy * dy) ** 0.5

    if dx == 0.0 and dy == 0.0:
        return "inside", distance
    if dx == 0.0:
        return ("below" if ty0 < fy0 else "above"), distance
    if dy == 0.0:
        return ("right" if tx0 > fx1 else "left"), distance

    # Diagonal — pick dominant axis
    if dx > dy:
        return ("right" if tx0 > fx1 else "left"), distance
    return ("below" if ty0 < fy0 else "above"), distance


def _infer_role(text: str, direction: FieldTextDirection) -> FieldTextRole:
    """Classify the semantic role of a text block using heuristics."""
    if _INSTRUCTION_KEYWORDS.search(text):
        return "instruction"
    if _HELPER_KEYWORDS.search(text):
        return "helper"
    if _DESCRIPTION_KEYWORDS.search(text):
        return "description"
    if direction in ("left", "above") and len(text) < 80:
        return "label"
    if direction in ("below", "right") and len(text) > 80:
        return "description"
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class ProximityMatcher:
    """Associate text blocks with form fields via geometric proximity."""

    @staticmethod
    def match(
        field_layout: FieldLayout,
        text_blocks: list[_RawTextBlock],
        *,
        max_distance: float = _DEFAULT_MAX_DISTANCE,
    ) -> list[FieldTextBlock]:
        """Return text blocks near *field_layout*, sorted by ascending distance.

        Blocks that are fully contained inside the field rectangle are skipped
        (they are typically the current field value, not a label).
        """
        if field_layout.x is None or field_layout.y is None:
            return []

        fx0 = float(field_layout.x)
        fy0 = float(field_layout.y)
        fx1 = fx0 + (field_layout.width or 0)
        fy1 = fy0 + (field_layout.height or 0)

        matches: list[FieldTextBlock] = []
        for tb in text_blocks:
            if not tb.text:
                continue

            if _rect_contains(fx0, fy0, fx1, fy1, tb.x0, tb.y0, tb.x1, tb.y1):
                continue

            direction, distance = _compute_direction_distance(
                fx0, fy0, fx1, fy1, tb.x0, tb.y0, tb.x1, tb.y1
            )
            if distance is None or distance > max_distance:
                continue

            role = _infer_role(tb.text, direction)

            matches.append(
                FieldTextBlock(
                    text=tb.text,
                    role=role,
                    direction=direction,
                    layout=FieldLayout(
                        page=field_layout.page,
                        x=int(tb.x0),
                        y=int(tb.y0),
                        width=int(tb.x1 - tb.x0),
                        height=int(tb.y1 - tb.y0),
                    ),
                    distance=round(distance, 2),
                )
            )

        matches.sort(key=lambda m: m.distance if m.distance is not None else float("inf"))
        return matches


class LabelExtractor:
    """Extract nearby text blocks for a set of form fields using PyMuPDF."""

    def __init__(self, pdf_path: str | Path) -> None:
        """Open *pdf_path* with PyMuPDF.

        Args:
            pdf_path: Path to the PDF file.
        """
        self._pdf_path = pdf_path
        self._fitz = _require_fitz()
        self._doc = self._fitz.open(str(pdf_path))

    def __enter__(self) -> LabelExtractor:
        """Enter context manager."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Close the underlying document."""
        self._doc.close()

    def extract_blocks(self, fields: Sequence[PDFField]) -> dict[str, list[FieldTextBlock]]:
        """Return a mapping from field id to associated text blocks.

        Args:
            fields: Fields parsed from the PDF (must have ``layout`` populated).

        Returns:
            Dictionary ``{field_id: [FieldTextBlock, ...]}``.
        """
        page_fields: dict[int, list[PDFField]] = {}
        for f in fields:
            if f.layout is not None and f.layout.page is not None:
                page_fields.setdefault(f.layout.page, []).append(f)

        result: dict[str, list[FieldTextBlock]] = {}
        for page_num, pfields in page_fields.items():
            if page_num < 1 or page_num > len(self._doc):
                continue
            page = self._doc.load_page(page_num - 1)
            page_height = page.rect.height
            text_blocks = self._get_text_blocks(page, page_height)

            for field in pfields:
                if field.layout is None:
                    continue
                result[field.id] = ProximityMatcher.match(field.layout, text_blocks)

        return result

    def _get_text_blocks(self, page: Any, page_height: float) -> list[_RawTextBlock]:
        """Extract text blocks from *page* and convert coordinates to PDF-native."""
        blocks = page.get_text("blocks")
        raw_blocks: list[_RawTextBlock] = []
        for b in blocks:
            if not isinstance(b, tuple) or len(b) < 5:
                continue
            x0, y0, x1, y1, text, *_rest = b
            # MuPDF: (0,0) is top-left, y increases downward.
            # PDF native: (0,0) is bottom-left, y increases upward.
            pdf_x0 = float(x0)
            pdf_y0 = float(page_height - y1)  # bottom edge
            pdf_x1 = float(x1)
            pdf_y1 = float(page_height - y0)  # top edge
            cleaned = str(text).strip()
            if cleaned and len(cleaned) <= _MAX_TEXT_BLOCK_LEN:
                raw_blocks.append(_RawTextBlock(pdf_x0, pdf_y0, pdf_x1, pdf_y1, cleaned))
        return raw_blocks


class PageTextExtractor:
    """Extract all text blocks from PDF pages with layout and formatting."""

    def __init__(self, pdf_path: str | Path) -> None:
        """Open *pdf_path* with PyMuPDF.

        Args:
            pdf_path: Path to the PDF file.
        """
        self._pdf_path = Path(pdf_path)
        self._fitz = _require_fitz()
        self._doc = self._fitz.open(str(self._pdf_path))

    def __enter__(self) -> PageTextExtractor:
        """Enter context manager."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Close the underlying document."""
        self._doc.close()

    def extract_pages(self) -> list[PDFPage]:
        """Return a list of PDFPage objects with all text blocks.

        Returns:
            List of pages containing extracted text blocks.
        """
        pages: list[PDFPage] = []
        for page_idx in range(len(self._doc)):
            page = self._doc.load_page(page_idx)
            page_height = page.rect.height
            page_width = page.rect.width
            text_blocks = self._get_page_text_blocks(page, page_idx + 1, page_height)
            pages.append(
                PDFPage(
                    page_index=page_idx + 1,
                    width=float(page_width),
                    height=float(page_height),
                    text_blocks=text_blocks,
                )
            )
        return pages

    def _get_page_text_blocks(
        self, page: Any, page_index: int, page_height: float
    ) -> list[PDFTextBlock]:
        """Extract text blocks from *page* with formatting via ``get_text('dict')``."""
        raw = page.get_text("dict")
        blocks_data = raw.get("blocks", [])
        pdf_blocks: list[PDFTextBlock] = []
        for block in blocks_data:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            bbox = block.get("bbox")
            if bbox is None or len(bbox) != 4:
                continue
            x0, y0, x1, y1 = bbox
            # Convert MuPDF coords to PDF-native
            pdf_x0 = float(x0)
            pdf_y0 = float(page_height - y1)
            pdf_x1 = float(x1)
            pdf_y1 = float(page_height - y0)
            layout = FieldLayout(
                page=page_index,
                x=int(pdf_x0),
                y=int(pdf_y0),
                width=int(pdf_x1 - pdf_x0),
                height=int(pdf_y1 - pdf_y0),
            )
            if block_type == 1:  # image block — skip
                continue
            # Text block: aggregate lines/spans
            lines = block.get("lines", [])
            text_parts: list[str] = []
            span_formats: list[TextFormat] = []
            for line in lines:
                spans = line.get("spans", [])
                for span in spans:
                    span_text = span.get("text", "")
                    if span_text:
                        text_parts.append(span_text)
                    fmt = self._build_text_format(span)
                    if fmt is not None:
                        span_formats.append(fmt)
            full_text = "".join(text_parts).strip()
            if not full_text:
                continue
            # Use the most common formatting as the block-level format
            block_format = self._resolve_block_format(span_formats)
            pdf_blocks.append(
                PDFTextBlock(
                    text=full_text,
                    layout=layout,
                    format=block_format,
                    block_type=0,
                )
            )
        return pdf_blocks

    @staticmethod
    def _build_text_format(span: dict[str, Any]) -> TextFormat | None:
        """Build a TextFormat from a PyMuPDF span dictionary."""
        font = span.get("font")
        size = span.get("size")
        flags = span.get("flags")
        color_raw = span.get("color")
        if font is None and size is None and flags is None and color_raw is None:
            return None
        color_hex: str | None = None
        if color_raw is not None:
            try:
                color_int = int(color_raw)
                color_hex = f"#{color_int & 0xFFFFFF:06X}"
            except (ValueError, TypeError):
                color_hex = None
        bold = None
        italic = None
        if flags is not None:
            try:
                flags_int = int(flags)
                bold = bool(flags_int & 2**4)  # bit 4 = bold
                italic = bool(flags_int & 2**0)  # bit 0 = italic
            except (ValueError, TypeError):
                pass
        return TextFormat(
            font=font if font is not None else None,
            font_size=float(size) if size is not None else None,
            color=color_hex,
            flags=int(flags) if flags is not None else None,
            bold=bold,
            italic=italic,
        )

    @staticmethod
    def _resolve_block_format(formats: list[TextFormat]) -> TextFormat | None:
        """Pick the dominant format from a list of span formats.

        Simple heuristic: return the first format, or None if the list is empty.
        """
        if not formats:
            return None
        return formats[0]


def infer_title(field: PDFField) -> str | None:
    """Infer a human-facing title from a field's text blocks.

    Prefers the closest block with ``role == "label"``,
    falling back to the closest ``left`` or ``above`` block.

    Args:
        field: A parsed PDF field (may already have text_blocks populated).

    Returns:
        Best title candidate, or ``None`` if no suitable block is found.
    """
    for block in field.text_blocks:
        if block.role == "label":
            return block.text
    for block in field.text_blocks:
        if block.direction in ("left", "above"):
            return block.text
    return None
