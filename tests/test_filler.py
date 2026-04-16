"""Tests for the FormFiller class."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from privacyforms_pdf.filler import FormFiller
from privacyforms_pdf.reader import FormReader

if TYPE_CHECKING:
    from pathlib import Path as PathType


class TestFormFillerFill:
    """Tests for FormFiller.fill (standalone API)."""

    def test_fill_success(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill succeeds with mocked pypdf."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx", "/V": ""}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = filler.fill(test_file, {"Name": "John"}, output_file, validate=False)
            assert result == output_file
            mock_writer.update_page_form_field_values.assert_called()

    def test_fill_falls_back_without_appearance(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill falls back when pypdf raises appearance bug."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx", "/V": ""}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]
        mock_writer.update_page_form_field_values.side_effect = AttributeError(
            "'int' object has no attribute 'encode'"
        )

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
            patch.object(filler, "_fill_form_fields_without_appearance") as fallback,
        ):
            result = filler.fill(test_file, {"Name": "John"}, output_file, validate=False)
            assert result == output_file
            fallback.assert_called_once_with(mock_writer, {"Name": "John"})

    def test_fill_reraises_unexpected_attribute_error(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill re-raises unrelated AttributeError."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]
        mock_writer.update_page_form_field_values.side_effect = AttributeError("different bug")

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
            pytest.raises(AttributeError, match="different bug"),
        ):
            filler.fill(test_file, {"Name": "John"}, output_file, validate=False)

    def test_fill_empty_form_data(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill with empty form data skips field updates."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Name": {"/FT": "/Tx"}}

        mock_writer = MagicMock()
        mock_writer.pages = []

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
        ):
            result = filler.fill(test_file, {}, output_file, validate=False)
            assert result == output_file
            mock_writer.update_page_form_field_values.assert_not_called()

    def test_fill_with_radio_button(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill handles radio button groups."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Choice": {"/FT": "/Btn", "/Opt": ["Yes", "No"]}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
            patch.object(filler, "_sync_radio_button_states") as mock_sync,
        ):
            filler.fill(test_file, {"Choice": "/Yes"}, output_file, validate=False)
            mock_sync.assert_called_once()

    def test_fill_with_listbox(self, tmp_path: PathType) -> None:
        """Test FormFiller.fill handles listbox fields."""
        filler = FormFiller()
        test_file = tmp_path / "test.pdf"
        test_file.touch()
        output_file = tmp_path / "output.pdf"

        mock_reader = MagicMock()
        mock_reader.get_fields.return_value = {"Colors": {"/FT": "/Ch"}}

        mock_writer = MagicMock()
        mock_writer.pages = [MagicMock()]

        with (
            patch("privacyforms_pdf.extractor.PdfReader", return_value=mock_reader),
            patch("privacyforms_pdf.extractor.PdfWriter", return_value=mock_writer),
            patch.object(filler, "_sync_listbox_selection_indexes") as mock_sync,
        ):
            filler.fill(test_file, {"Colors": "Red"}, output_file, validate=False)
            mock_sync.assert_called_once()


class TestFormFillerWidgetOnState:
    """Tests for _get_widget_on_state."""

    def test_get_widget_on_state_returns_none_when_all_off(self) -> None:
        """Test _get_widget_on_state returns None when only /Off states exist."""
        annotation = {"/AP": {"/N": {"/Off": None}}}
        assert FormFiller._get_widget_on_state(annotation) is None


class TestFormFillerResolveRadioFieldState:
    """Tests for _resolve_radio_field_state fallback loops."""

    def test_resolve_radio_field_state_fallback_to_options(self) -> None:
        """Test fallback matching via FormReader.get_field_options."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/OptionA": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
            "/Opt": ["OptionA"],
        }

        with patch.object(FormReader, "get_field_options", return_value=["OptionA"]):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "OptionA")
            assert result == "/OptionA"

    def test_resolve_radio_field_state_fallback_to_lstrip_match(self) -> None:
        """Test fallback matching by stripping leading slashes."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/CustomState": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
        }

        with patch.object(FormReader, "get_field_options", return_value=None):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "CustomState")
            assert result == "/CustomState"

    def test_resolve_radio_field_state_returns_off_when_no_match(self) -> None:
        """Test _resolve_radio_field_state returns /Off when nothing matches."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/Off": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
        }

        with patch.object(FormReader, "get_field_options", return_value=None):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "Missing")
            assert result == "/Off"


class TestFormFillerSyncRadioButtonStates:
    """Tests for _sync_radio_button_states edge-case branches."""

    def test_sync_radio_skips_page_without_annotations(self) -> None:
        """Test _sync_radio_button_states skips pages with no annotations."""
        filler = FormFiller()
        writer = MagicMock()
        writer.pages = [{"/Annots": []}]
        filler._sync_radio_button_states(writer, {"Choice": "/Yes"})

    def test_sync_radio_skips_non_widgets(self) -> None:
        """Test _sync_radio_button_states skips non-widget annotations."""
        filler = FormFiller()
        writer = MagicMock()

        link_ref = MagicMock()
        link_ref.get_object.return_value = {"/Subtype": "/Link"}

        writer.pages = [{"/Annots": [link_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")
        filler._sync_radio_button_states(writer, {"Choice": "/Yes"})

    def test_sync_radio_skips_non_radio_buttons(self) -> None:
        """Test _sync_radio_button_states skips non-radio button widgets."""
        filler = FormFiller()
        writer = MagicMock()

        text_ref = MagicMock()
        text_ref.get_object.return_value = {"/Subtype": "/Widget", "/FT": "/Tx", "/T": "Name"}

        writer.pages = [{"/Annots": [text_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch.object(FormReader, "get_field_type", return_value="textfield"):
            filler._sync_radio_button_states(writer, {"Choice": "/Yes"})

    def test_sync_radio_skips_checkbox_widgets(self) -> None:
        """Test _sync_radio_button_states skips checkbox widgets (/Btn but not radiobuttongroup)."""
        filler = FormFiller()
        writer = MagicMock()

        checkbox_ref = MagicMock()
        checkbox_ref.get_object.return_value = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "Agree",
        }

        writer.pages = [{"/Annots": [checkbox_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch.object(FormReader, "get_field_type", return_value="checkbox"):
            filler._sync_radio_button_states(writer, {"Agree": "/Yes"})


class TestFormFillerSyncListboxSelectionIndexes:
    """Tests for _sync_listbox_selection_indexes edge-case branches."""

    def test_sync_listbox_skips_page_without_annotations(self) -> None:
        """Test _sync_listbox_selection_indexes skips pages with no annotations."""
        filler = FormFiller()
        writer = MagicMock()
        writer.pages = [{"/Annots": []}]
        filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})

    def test_sync_listbox_skips_non_widgets(self) -> None:
        """Test _sync_listbox_selection_indexes skips non-widget annotations."""
        filler = FormFiller()
        writer = MagicMock()

        link_ref = MagicMock()
        link_ref.get_object.return_value = {"/Subtype": "/Link"}

        writer.pages = [{"/Annots": [link_ref]}]
        filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})

    def test_sync_listbox_skips_non_listbox_widgets(self) -> None:
        """Test _sync_listbox_selection_indexes skips non-listbox widgets."""
        filler = FormFiller()
        writer = MagicMock()

        text_ref = MagicMock()
        text_ref.get_object.return_value = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "Name",
        }

        writer.pages = [{"/Annots": [text_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch.object(FormReader, "get_field_type", return_value="textfield"):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})

    def test_sync_listbox_skips_unmatched_field(self) -> None:
        """Test _sync_listbox_selection_indexes skips widgets not in field_values."""
        filler = FormFiller()
        writer = MagicMock()

        widget_ref = MagicMock()
        widget_ref.get_object.return_value = {
            "/Subtype": "/Widget",
            "/FT": "/Ch",
            "/T": "Other",
        }

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch.object(FormReader, "get_field_type", return_value="listbox"):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})

    def test_sync_listbox_with_parent_ref(self) -> None:
        """Test _sync_listbox_selection_indexes resolves parent annotation via /Parent."""
        filler = FormFiller()
        writer = MagicMock()

        parent_annotation = {
            "/Subtype": "/Widget",
            "/FT": "/Ch",
            "/T": "Colors",
        }
        parent_ref = MagicMock()
        parent_ref.get_object.return_value = parent_annotation

        widget = {
            "/Subtype": "/Widget",
            "/Parent": parent_ref,
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with (
            patch.object(FormReader, "get_field_type", return_value="listbox"),
            patch.object(FormReader, "get_field_options", return_value=["Red", "Blue"]),
            patch.object(filler, "_build_listbox_appearance_stream", return_value=None),
        ):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})
            assert parent_annotation["/V"] == TextStringObject("Red")

    def test_sync_listbox_with_appearance_ref(self) -> None:
        """Test _sync_listbox_selection_indexes sets appearance dict when ref is returned."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Ch",
            "/T": "Colors",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        from pypdf.generic import NameObject

        mock_ref = NameObject("/Ref")

        with (
            patch.object(FormReader, "get_field_type", return_value="listbox"),
            patch.object(FormReader, "get_field_options", return_value=["Red", "Blue"]),
            patch.object(filler, "_build_listbox_appearance_stream", return_value=mock_ref),
        ):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})
            assert "/AP" in widget
            assert cast("DictionaryObject", widget["/AP"])["/N"] == mock_ref

    def test_sync_listbox_skips_combobox_widgets(self) -> None:
        """Test _sync_listbox_selection_indexes skips combobox widgets (/Ch but not listbox)."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Ch",
            "/T": "Country",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch.object(FormReader, "get_field_type", return_value="combobox"):
            filler._sync_listbox_selection_indexes(writer, {"Country": "USA"})


class TestFormFillerBuildListboxAppearanceStream:
    """Tests for _build_listbox_appearance_stream branches."""

    def test_build_listbox_appearance_stream_no_options(self) -> None:
        """Test _build_listbox_appearance_stream returns None when no options."""
        filler = FormFiller()
        writer = MagicMock()
        annotation = {}
        parent_annotation = {}

        with patch.object(FormReader, "get_field_options", return_value=[]):
            result = filler._build_listbox_appearance_stream(
                writer, annotation, parent_annotation, 0
            )
            assert result is None

    def test_build_listbox_appearance_stream_with_default_bbox(self) -> None:
        """Test _build_listbox_appearance_stream uses default bbox when no AP exists."""
        filler = FormFiller()
        writer = MagicMock()
        writer._add_object.return_value = "ref"
        annotation = {}
        parent_annotation = {}

        with patch.object(FormReader, "get_field_options", return_value=["Red"]):
            result = filler._build_listbox_appearance_stream(
                writer, annotation, parent_annotation, 0
            )
            assert result == "ref"
            stream_arg = writer._add_object.call_args[0][0]
            assert stream_arg.get("/BBox") is not None

    def test_build_listbox_appearance_stream_with_existing_font(self) -> None:
        """Test _build_listbox_appearance_stream reuses existing font from AP resources."""
        filler = FormFiller()
        writer = MagicMock()
        writer._add_object.return_value = "ref"

        from pypdf.generic import ArrayObject, DictionaryObject, NumberObject, StreamObject

        normal_ap = StreamObject()
        normal_ap[NameObject("/BBox")] = ArrayObject(
            [NumberObject(0), NumberObject(0), NumberObject(100), NumberObject(50)]
        )
        normal_ap[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): DictionaryObject()}),
            }
        )

        mock_n_ref = MagicMock()
        mock_n_ref.get_object.return_value = normal_ap
        ap_dict = DictionaryObject({NameObject("/N"): mock_n_ref})
        annotation = {"/AP": ap_dict}
        parent_annotation = {}

        with patch.object(FormReader, "get_field_options", return_value=["Red"]):
            result = filler._build_listbox_appearance_stream(
                writer, annotation, parent_annotation, 0
            )
            assert result == "ref"


class TestFormFillerFillFormFieldsWithoutAppearance:
    """Tests for _fill_form_fields_without_appearance edge cases."""

    def test_fill_without_appearance_parent_ref(self) -> None:
        """Test _fill_form_fields_without_appearance resolves parent via /Parent."""
        filler = FormFiller()

        parent_annotation = {"/Subtype": "/Widget", "/FT": "/Tx", "/T": "Name"}
        parent_ref = MagicMock()
        parent_ref.get_object.return_value = parent_annotation

        widget = {"/Subtype": "/Widget", "/Parent": parent_ref}
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer = MagicMock()
        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        filler._fill_form_fields_without_appearance(writer, {"Name": "John"})
        assert parent_annotation["/V"] == TextStringObject("John")

    def test_fill_without_appearance_radio_button_group(self) -> None:
        """Test _fill_form_fields_without_appearance handles radio button groups."""
        filler = FormFiller()

        widget = {"/Subtype": "/Widget", "/FT": "/Btn", "/T": "Choice"}
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer = MagicMock()
        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with (
            patch.object(FormReader, "get_field_type", return_value="radiobuttongroup"),
            patch.object(filler, "_sync_radio_button_states") as mock_sync,
        ):
            filler._fill_form_fields_without_appearance(writer, {"Choice": "/Yes"})
            assert widget["/V"] == TextStringObject("/Yes")
            mock_sync.assert_called_once_with(writer, {"Choice": "/Yes"})

    def test_fill_without_appearance_listbox(self) -> None:
        """Test _fill_form_fields_without_appearance handles listboxes."""
        filler = FormFiller()

        widget = {"/Subtype": "/Widget", "/FT": "/Ch", "/T": "Colors"}
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer = MagicMock()
        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with (
            patch.object(FormReader, "get_field_type", side_effect=lambda a: "listbox"),
            patch.object(filler, "_sync_listbox_selection_indexes") as mock_sync,
        ):
            filler._fill_form_fields_without_appearance(writer, {"Colors": "Red"})
            mock_sync.assert_called_once_with(writer, {"Colors": "Red"})
