"""Tests for the label extraction module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from privacyforms_pdf.label_extractor import (
    LabelExtractor,
    PageTextExtractor,
    ProximityMatcher,
    _compute_direction_distance,
    _infer_role,
    _RawTextBlock,
    _rect_contains,
    infer_title,
)
from privacyforms_pdf.schema import FieldLayout, FieldTextBlock, PDFField

if TYPE_CHECKING:
    from pathlib import Path


class TestRectContains:
    """Tests for _rect_contains helper."""

    def test_contains_fully_inside(self) -> None:
        """Text block fully inside field rect is contained."""
        assert _rect_contains(0, 0, 100, 100, 10, 10, 90, 90) is True

    def test_partial_overlap_not_contained(self) -> None:
        """Partial overlap is not full containment."""
        assert _rect_contains(0, 0, 100, 100, 50, 50, 150, 150) is False

    def test_outside_not_contained(self) -> None:
        """Completely outside is not contained."""
        assert _rect_contains(0, 0, 100, 100, 200, 200, 300, 300) is False


class TestComputeDirectionDistance:
    """Tests for _compute_direction_distance."""

    def test_inside(self) -> None:
        """Text block inside field returns inside."""
        direction, distance = _compute_direction_distance(0, 0, 100, 100, 10, 10, 90, 90)
        assert direction == "inside"
        assert distance == pytest.approx(0.0)

    def test_left(self) -> None:
        """Text block to the left."""
        direction, distance = _compute_direction_distance(100, 0, 200, 100, 0, 0, 80, 100)
        assert direction == "left"
        assert distance == pytest.approx(20.0)

    def test_right(self) -> None:
        """Text block to the right."""
        direction, distance = _compute_direction_distance(0, 0, 100, 100, 120, 0, 200, 100)
        assert direction == "right"
        assert distance == pytest.approx(20.0)

    def test_above(self) -> None:
        """Text block above field (PDF coords: larger y is higher)."""
        direction, distance = _compute_direction_distance(0, 100, 100, 200, 0, 220, 100, 300)
        assert direction == "above"
        assert distance == pytest.approx(20.0)

    def test_below(self) -> None:
        """Text block below field."""
        direction, distance = _compute_direction_distance(0, 200, 100, 300, 0, 100, 100, 180)
        assert direction == "below"
        assert distance == pytest.approx(20.0)

    def test_diagonal_dominant_horizontal(self) -> None:
        """Diagonal with larger horizontal gap resolves to left/right."""
        direction, distance = _compute_direction_distance(100, 100, 200, 200, 0, 0, 30, 50)
        assert direction == "left"
        assert distance == pytest.approx((70**2 + 50**2) ** 0.5)

    def test_diagonal_dominant_vertical(self) -> None:
        """Diagonal with larger vertical gap resolves to above/below."""
        direction, distance = _compute_direction_distance(100, 100, 200, 200, 150, 0, 180, 50)
        assert direction == "below"


class TestInferRole:
    """Tests for _infer_role heuristics."""

    def test_instruction_keyword(self) -> None:
        """Text containing instruction keywords."""
        assert _infer_role("Please read the instructions below", "above") == "instruction"

    def test_helper_keyword(self) -> None:
        """Text containing helper keywords."""
        assert _infer_role("This field is required", "below") == "helper"

    def test_description_keyword(self) -> None:
        """Text containing description keywords."""
        assert _infer_role("Note: enter your full name", "below") == "description"

    def test_label_heuristic_left(self) -> None:
        """Short text to the left is a label."""
        assert _infer_role("First Name:", "left") == "label"

    def test_label_heuristic_above(self) -> None:
        """Short text above is a label."""
        assert _infer_role("Email", "above") == "label"

    def test_description_heuristic_below_long(self) -> None:
        """Long text below is a description."""
        long_text = "A" * 81
        assert _infer_role(long_text, "below") == "description"

    def test_unknown_fallback(self) -> None:
        """No heuristics matched falls back to unknown."""
        assert _infer_role("Some text", "right") == "unknown"


class TestProximityMatcher:
    """Tests for ProximityMatcher.match."""

    def test_no_match_when_field_has_no_layout(self) -> None:
        """Empty list when field layout is missing coordinates."""
        layout = FieldLayout(page=1, x=None, y=None)
        blocks = [_RawTextBlock(0, 0, 10, 10, "Name")]
        assert ProximityMatcher.match(layout, blocks) == []

    def test_skip_contained_block(self) -> None:
        """Blocks fully inside the widget rect are skipped."""
        layout = FieldLayout(page=1, x=0, y=0, width=100, height=20)
        blocks = [_RawTextBlock(10, 2, 90, 18, "inside value")]
        assert ProximityMatcher.match(layout, blocks) == []

    def test_match_left_block(self) -> None:
        """Block to the left is matched and sorted."""
        layout = FieldLayout(page=1, x=100, y=0, width=50, height=20)
        blocks = [
            _RawTextBlock(0, 0, 80, 20, "Name"),
            _RawTextBlock(200, 0, 300, 20, "Other"),
        ]
        result = ProximityMatcher.match(layout, blocks, max_distance=25)
        assert len(result) == 1
        assert result[0].direction == "left"
        assert result[0].text == "Name"

    def test_respects_max_distance(self) -> None:
        """Blocks beyond max_distance are excluded."""
        layout = FieldLayout(page=1, x=0, y=0, width=50, height=20)
        blocks = [_RawTextBlock(200, 0, 250, 20, "Far away")]
        assert ProximityMatcher.match(layout, blocks, max_distance=50) == []

    def test_sorts_by_distance(self) -> None:
        """Result is sorted by ascending distance."""
        layout = FieldLayout(page=1, x=100, y=100, width=50, height=20)
        blocks = [
            _RawTextBlock(0, 100, 80, 120, "Closer"),  # dx=20
            _RawTextBlock(0, 0, 20, 20, "Farther"),  # dx=80, dy=80
        ]
        result = ProximityMatcher.match(layout, blocks, max_distance=150)
        assert len(result) == 2
        assert result[0].text == "Closer"
        assert result[1].text == "Farther"

    def test_populates_layout(self) -> None:
        """Matched block carries layout converted to FieldLayout."""
        layout = FieldLayout(page=1, x=100, y=0, width=50, height=20)
        blocks = [_RawTextBlock(0, 0, 80, 20, "Label")]
        result = ProximityMatcher.match(layout, blocks)
        assert result[0].layout is not None
        assert result[0].layout.x == 0
        assert result[0].layout.y == 0
        assert result[0].layout.width == 80
        assert result[0].layout.height == 20


class TestLabelExtractor:
    """Tests for LabelExtractor with mocked fitz."""

    def test_missing_fitz_raises_import_error(self, tmp_path: Path) -> None:
        """LabelExtractor raises ImportError when fitz is missing."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        with (
            patch.dict("sys.modules", {"fitz": None}),
            pytest.raises(ImportError, match="Label extraction requires PyMuPDF"),
        ):
            LabelExtractor(pdf_file)

    def test_extract_blocks_groups_by_page(self, tmp_path: Path) -> None:
        """Blocks are extracted and matched per page."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.get_text.return_value = [
            (10.0, 10.0, 80.0, 30.0, "Name", 0, 0),
        ]

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 2

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=1, x=100, y=750, width=50, height=20),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert "f-1" in result
        assert len(result["f-1"]) == 1
        assert result["f-1"][0].text == "Name"
        assert result["f-1"][0].direction == "left"

    def test_skips_blocks_inside_widget(self, tmp_path: Path) -> None:
        """Text blocks fully inside the field rect are excluded."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.get_text.return_value = [
            (105.0, 755.0, 140.0, 765.0, "value", 0, 0),
        ]

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=1, x=100, y=750, width=50, height=20),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert result["f-1"] == []

    def test_skips_out_of_range_pages(self, tmp_path: Path) -> None:
        """Fields referencing non-existent pages are skipped gracefully."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=99, x=0, y=0, width=10, height=10),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert result == {}


class TestInferTitle:
    """Tests for infer_title helper."""

    def test_prefers_label_role(self) -> None:
        """Returns the first text block with role label."""
        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            text_blocks=[
                FieldTextBlock(text="Above", direction="above"),
                FieldTextBlock(text="First Name", role="label", direction="left"),
            ],
        )
        assert infer_title(field) == "First Name"

    def test_falls_back_to_left_or_above(self) -> None:
        """When no label role exists, falls back to left/above direction."""
        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            text_blocks=[
                FieldTextBlock(text="Below", direction="below"),
                FieldTextBlock(text="Lefty", direction="left"),
            ],
        )
        assert infer_title(field) == "Lefty"

    def test_returns_none_when_no_candidates(self) -> None:
        """Returns None if no suitable text block is found."""
        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            text_blocks=[
                FieldTextBlock(text="Right", direction="right"),
            ],
        )
        assert infer_title(field) is None


class TestLabelExtractorContextManager:
    """Tests for LabelExtractor context manager protocol."""

    def test_context_manager_closes_document(self, tmp_path: Path) -> None:
        """__exit__ calls close on the underlying fitz document."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_doc = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            with LabelExtractor(pdf_file) as extractor:
                assert isinstance(extractor, LabelExtractor)
            mock_doc.close.assert_called_once()


class TestProximityMatcherEdgeCases:
    """Additional edge-case tests for ProximityMatcher."""

    def test_skips_empty_text_block(self) -> None:
        """Blocks with empty text are skipped."""
        layout = FieldLayout(page=1, x=100, y=0, width=50, height=20)
        blocks = [
            _RawTextBlock(0, 0, 80, 20, ""),
            _RawTextBlock(0, 0, 80, 20, "Valid"),
        ]
        result = ProximityMatcher.match(layout, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"


class TestLabelExtractorEdgeCases:
    """Additional edge-case tests for LabelExtractor."""

    def test_skips_field_without_layout(self, tmp_path: Path) -> None:
        """Fields with layout=None are skipped."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.get_text.return_value = []

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=None,
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert result == {}

    def test_skips_page_zero(self, tmp_path: Path) -> None:
        """Fields with page_index=0 are skipped (pages are 1-based)."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=0, x=0, y=0, width=10, height=10),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert result == {}

    def test_skips_malformed_blocks(self, tmp_path: Path) -> None:
        """Malformed tuples from get_text are skipped gracefully."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.get_text.return_value = [
            (10.0, 10.0),  # too short
            (10.0, 10.0, 80.0, 30.0, "Good", 0, 0),
        ]

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=1, x=100, y=750, width=50, height=20),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert "f-1" in result
        assert len(result["f-1"]) == 1
        assert result["f-1"][0].text == "Good"

    def test_skips_oversized_text_blocks(self, tmp_path: Path) -> None:
        """Text blocks exceeding 100k characters are skipped."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.get_text.return_value = [
            (10.0, 10.0, 80.0, 30.0, "x" * 100_001, 0, 0),
        ]

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        field = PDFField(
            name="Name",
            id="f-1",
            type="textfield",
            layout=FieldLayout(page=1, x=100, y=750, width=50, height=20),
        )

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = LabelExtractor(pdf_file)
            result = extractor.extract_blocks([field])

        assert result["f-1"] == []


class TestPageTextExtractor:
    """Tests for PageTextExtractor."""

    def test_missing_fitz_raises_import_error(self, tmp_path: Path) -> None:
        """PageTextExtractor raises ImportError when fitz is missing."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        with (
            patch.dict("sys.modules", {"fitz": None}),
            pytest.raises(ImportError, match="Label extraction requires PyMuPDF"),
        ):
            PageTextExtractor(pdf_file)

    def test_extract_pages_empty_document(self, tmp_path: Path) -> None:
        """Empty document returns no pages."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda _self: 0

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = PageTextExtractor(pdf_file)
            result = extractor.extract_pages()

        assert result == []

    def test_extract_pages_single_page(self, tmp_path: Path) -> None:
        """Single page with one text block is extracted correctly."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.rect.width = 600.0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 0,
                    "bbox": [10.0, 10.0, 100.0, 30.0],
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Hello World",
                                    "font": "Helvetica",
                                    "size": 12.0,
                                    "flags": 0,
                                    "color": 0,
                                }
                            ]
                        }
                    ],
                }
            ]
        }

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = PageTextExtractor(pdf_file)
            result = extractor.extract_pages()

        assert len(result) == 1
        assert result[0].page_index == 1
        assert result[0].width == 600.0
        assert result[0].height == 800.0
        assert len(result[0].text_blocks) == 1
        assert result[0].text_blocks[0].text == "Hello World"
        assert result[0].text_blocks[0].block_type == 0
        fmt = result[0].text_blocks[0].format
        assert fmt is not None
        assert fmt.font == "Helvetica"
        assert fmt.font_size == 12.0
        assert fmt.color == "#000000"

    def test_extract_pages_skips_image_blocks(self, tmp_path: Path) -> None:
        """Image blocks (type 1) are skipped entirely."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.rect.width = 600.0
        mock_page.get_text.return_value = {
            "blocks": [
                {
                    "type": 1,
                    "bbox": [10.0, 10.0, 100.0, 100.0],
                }
            ]
        }

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = PageTextExtractor(pdf_file)
            result = extractor.extract_pages()

        assert len(result[0].text_blocks) == 0

    def test_extract_pages_skips_malformed_blocks(self, tmp_path: Path) -> None:
        """Malformed blocks are skipped gracefully."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_page = MagicMock()
        mock_page.rect.height = 800.0
        mock_page.rect.width = 600.0
        mock_page.get_text.return_value = {
            "blocks": [
                "not-a-dict",
                {
                    "type": 0,
                    "bbox": [10.0, 10.0, 100.0, 30.0],
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "Good",
                                    "font": "Helvetica",
                                    "size": 10.0,
                                }
                            ]
                        }
                    ],
                },
            ]
        }

        mock_doc = MagicMock()
        mock_doc.load_page.return_value = mock_page
        mock_doc.__len__ = lambda _self: 1

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            extractor = PageTextExtractor(pdf_file)
            result = extractor.extract_pages()

        assert len(result[0].text_blocks) == 1
        assert result[0].text_blocks[0].text == "Good"

    def test_context_manager_closes_document(self, tmp_path: Path) -> None:
        """PageTextExtractor context manager closes the document."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")

        mock_doc = MagicMock()
        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch("privacyforms_pdf.label_extractor._require_fitz", return_value=mock_fitz):
            with PageTextExtractor(pdf_file) as extractor:
                assert isinstance(extractor, PageTextExtractor)
            mock_doc.close.assert_called_once()
