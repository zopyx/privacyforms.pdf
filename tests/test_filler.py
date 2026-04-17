"""Tests for the FormFiller class."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from privacyforms_pdf.filler import FormFiller

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
            result = filler.fill(test_file, {"Name": "John"}, output_file)
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
            result = filler.fill(test_file, {"Name": "John"}, output_file)
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
            filler.fill(test_file, {"Name": "John"}, output_file)

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
            result = filler.fill(test_file, {}, output_file)
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
            filler.fill(test_file, {"Choice": "/Yes"}, output_file)
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
            filler.fill(test_file, {"Colors": "Red"}, output_file)
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
        """Test fallback matching via get_field_options."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/OptionA": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
            "/Opt": ["OptionA"],
        }

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["OptionA"]):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "OptionA")
            assert result == "/OptionA"

    def test_resolve_radio_field_state_fallback_to_lstrip_match(self) -> None:
        """Test fallback matching by stripping leading slashes."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/CustomState": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
        }

        with patch("privacyforms_pdf.filler.get_field_options", return_value=None):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "//CustomState")
            assert result == "/CustomState"

    def test_resolve_radio_field_state_returns_off_when_no_match(self) -> None:
        """Test _resolve_radio_field_state returns /Off when nothing matches."""
        kid_annotation = MagicMock()
        kid_annotation.get_object.return_value = {"/AP": {"/N": {"/Off": None}}}

        parent_annotation = {
            "/Kids": [kid_annotation],
        }

        with patch("privacyforms_pdf.filler.get_field_options", return_value=None):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "Missing")
            assert result == "/Off"

    def test_resolve_radio_field_state_continues_when_option_state_is_missing(self) -> None:
        """Test option fallback continues when the matched kid has no on-state."""
        missing_state_kid = MagicMock()
        missing_state_kid.get_object.return_value = {"/AP": {"/N": {"/Off": None}}}
        matching_state_kid = MagicMock()
        matching_state_kid.get_object.return_value = {"/AP": {"/N": {"/Choice": None}}}

        parent_annotation = {
            "/Kids": [missing_state_kid, matching_state_kid],
        }

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Choice", "Other"]):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "/Other")
            assert result == "/Choice"

    def test_resolve_radio_field_state_retries_duplicate_options(self) -> None:
        """Test option fallback retries later duplicate options after an Off-only widget."""
        first_kid = MagicMock()
        first_kid.get_object.return_value = {"/AP": {"/N": {"/Off": None}}}
        second_kid = MagicMock()
        second_kid.get_object.return_value = {"/AP": {"/N": {"/MappedChoice": None}}}

        parent_annotation = {
            "/Kids": [first_kid, second_kid],
        }

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Choice", "Choice"]):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "Choice")
            assert result == "/MappedChoice"


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

        with patch("privacyforms_pdf.filler.get_field_type", return_value="textfield"):
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

        with patch("privacyforms_pdf.filler.get_field_type", return_value="checkbox"):
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

        with patch("privacyforms_pdf.filler.get_field_type", return_value="textfield"):
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

        with patch("privacyforms_pdf.filler.get_field_type", return_value="listbox"):
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
            patch("privacyforms_pdf.filler.get_field_type", return_value="listbox"),
            patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]),
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
            patch("privacyforms_pdf.filler.get_field_type", return_value="listbox"),
            patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]),
            patch.object(filler, "_build_listbox_appearance_stream", return_value=mock_ref),
        ):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})
            assert "/AP" in widget
            assert cast("DictionaryObject", widget["/AP"])["/N"] == mock_ref

    def test_sync_listbox_reuses_existing_appearance_dict(self) -> None:
        """Test _sync_listbox_selection_indexes reuses an existing /AP dictionary."""
        filler = FormFiller()
        writer = MagicMock()

        appearance = DictionaryObject()
        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Ch",
            "/T": "Colors",
            "/AP": appearance,
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        mock_ref = NameObject("/Ref")

        with (
            patch("privacyforms_pdf.filler.get_field_type", return_value="listbox"),
            patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]),
            patch.object(filler, "_build_listbox_appearance_stream", return_value=mock_ref),
        ):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Red"})
            assert widget["/AP"] is appearance
            assert appearance["/N"] == mock_ref

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

        with patch("privacyforms_pdf.filler.get_field_type", return_value="combobox"):
            filler._sync_listbox_selection_indexes(writer, {"Country": "USA"})


class TestFormFillerBuildListboxAppearanceStream:
    """Tests for _build_listbox_appearance_stream branches."""

    def test_build_listbox_appearance_stream_no_options(self) -> None:
        """Test _build_listbox_appearance_stream returns None when no options."""
        filler = FormFiller()
        writer = MagicMock()
        annotation = {}
        parent_annotation = {}

        with patch("privacyforms_pdf.filler.get_field_options", return_value=[]):
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

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Red"]):
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

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Red"]):
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
            patch("privacyforms_pdf.filler.get_field_type", return_value="radiobuttongroup"),
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
            patch("privacyforms_pdf.filler.get_field_type", side_effect=lambda a: "listbox"),
            patch.object(filler, "_sync_listbox_selection_indexes") as mock_sync,
        ):
            filler._fill_form_fields_without_appearance(writer, {"Colors": "Red"})
            mock_sync.assert_called_once_with(writer, {"Colors": "Red"})

    def test_sync_listbox_selected_index_none(self) -> None:
        """Test _sync_listbox_selection_indexes when selected_index is None."""
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

        with (
            patch("privacyforms_pdf.filler.get_field_type", return_value="listbox"),
            patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]),
            patch.object(filler, "_resolve_listbox_index", return_value=None),
            patch.object(
                filler, "_build_listbox_appearance_stream", return_value=None
            ) as mock_build,
        ):
            filler._sync_listbox_selection_indexes(writer, {"Colors": "Purple"})
            assert widget["/V"] == TextStringObject("Purple")
            mock_build.assert_called_once_with(writer, widget, widget, None)
            assert "/I" not in widget
            assert "/TI" not in widget


class TestFormFillerBuildListboxAppearanceStreamSelectedIndexNone:
    """Tests for _build_listbox_appearance_stream when selected_index is None."""

    def test_build_listbox_appearance_stream_selected_index_none(self) -> None:
        """Test _build_listbox_appearance_stream skips highlight when selected_index is None."""
        filler = FormFiller()
        writer = MagicMock()
        writer._add_object.return_value = "ref"
        annotation = {}
        parent_annotation = {}

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Red"]):
            result = filler._build_listbox_appearance_stream(
                writer, annotation, parent_annotation, None
            )
            assert result == "ref"
            stream_arg = writer._add_object.call_args[0][0]
            stream_data = stream_arg.get_data().decode("utf-8")
            assert "0.600006 0.756866 0.854904 rg" not in stream_data
            assert "1 g" not in stream_data  # no selected index, so all options use "0 g"


class TestFormFillerFillFormFieldsWithoutAppearanceEdgeCases:
    """Additional edge-case tests for _fill_form_fields_without_appearance."""

    def test_fill_without_appearance_skips_page_without_annotations(self) -> None:
        """Test _fill_form_fields_without_appearance skips pages with no annotations."""
        filler = FormFiller()
        writer = MagicMock()
        writer.pages = [{"/Annots": []}]
        filler._fill_form_fields_without_appearance(writer, {"Name": "John"})
        writer.set_need_appearances_writer.assert_called_once_with(True)

    def test_fill_without_appearance_skips_non_widget_annotation(self) -> None:
        """Test _fill_form_fields_without_appearance skips non-widget annotations."""
        filler = FormFiller()
        writer = MagicMock()

        link_ref = MagicMock()
        link_ref.get_object.return_value = {"/Subtype": "/Link"}

        writer.pages = [{"/Annots": [link_ref]}]
        filler._fill_form_fields_without_appearance(writer, {"Name": "John"})

    def test_fill_without_appearance_skips_unmatched_field_name(self) -> None:
        """Test _fill_form_fields_without_appearance skips widgets not in field_values."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "OtherField",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        filler._fill_form_fields_without_appearance(writer, {"Name": "John"})
        assert "/V" not in widget

    def test_fill_without_appearance_checkbox_button(self) -> None:
        """Test _fill_form_fields_without_appearance handles checkbox (/Btn non-radio)."""
        filler = FormFiller()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "Agree",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer = MagicMock()
        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch("privacyforms_pdf.filler.get_field_type", return_value="checkbox"):
            filler._fill_form_fields_without_appearance(writer, {"Agree": "/Yes"})
            from pypdf.generic import NameObject

            assert widget["/V"] == NameObject("/Yes")
            assert widget["/AS"] == NameObject("/Yes")

    def test_fill_without_appearance_checkbox_button_no_leading_slash(self) -> None:
        """Test checkbox value gets leading slash added when missing."""
        filler = FormFiller()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "Agree",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer = MagicMock()
        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        with patch("privacyforms_pdf.filler.get_field_type", return_value="checkbox"):
            filler._fill_form_fields_without_appearance(writer, {"Agree": "Yes"})
            from pypdf.generic import NameObject

            assert widget["/V"] == NameObject("/Yes")
            assert widget["/AS"] == NameObject("/Yes")


class TestFormFillerGetFieldByNameFromWriter:
    """Tests for get_field_by_name_from_writer edge cases."""

    def test_get_field_by_name_returns_none_when_no_annotations(self) -> None:
        """Test get_field_by_name_from_writer returns None for pages without annotations."""
        filler = FormFiller()
        writer = MagicMock()
        writer.pages = [{"/Annots": []}]
        result = filler.get_field_by_name_from_writer(writer, "Name")
        assert result is None

    def test_get_field_by_name_skips_non_widget(self) -> None:
        """Test get_field_by_name_from_writer skips non-widget annotations."""
        filler = FormFiller()
        writer = MagicMock()

        link_ref = MagicMock()
        link_ref.get_object.return_value = {"/Subtype": "/Link"}

        writer.pages = [{"/Annots": [link_ref]}]
        result = filler.get_field_by_name_from_writer(writer, "Name")
        assert result is None

    def test_get_field_by_name_continues_when_no_match(self) -> None:
        """Test get_field_by_name_from_writer continues inner loop when no match."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "Other",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        result = filler.get_field_by_name_from_writer(writer, "Name")
        assert result is None

    def test_get_field_by_name_returns_on_match(self) -> None:
        """Test get_field_by_name_from_writer returns parent_annotation on match."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "Name",
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        result = filler.get_field_by_name_from_writer(writer, "Name")
        assert result is widget

    def test_get_field_by_name_across_multiple_pages(self) -> None:
        """Test get_field_by_name_from_writer searches across pages."""
        filler = FormFiller()
        writer = MagicMock()

        first_widget = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "First",
        }
        first_ref = MagicMock()
        first_ref.get_object.return_value = first_widget

        second_widget = {
            "/Subtype": "/Widget",
            "/FT": "/Tx",
            "/T": "Second",
        }
        second_ref = MagicMock()
        second_ref.get_object.return_value = second_widget

        writer.pages = [
            {"/Annots": [first_ref]},
            {"/Annots": [second_ref]},
        ]
        writer._get_qualified_field_name.side_effect = lambda a: a.get("/T", "")

        result = filler.get_field_by_name_from_writer(writer, "Second")
        assert result is second_widget


class TestFormFillerWidgetOnStateExtra:
    """Extra tests for _get_widget_on_state uncovered branches."""

    def test_get_widget_on_state_returns_none_when_no_ap(self) -> None:
        """Test _get_widget_on_state returns None when /AP is missing."""
        assert FormFiller._get_widget_on_state({}) is None

    def test_get_widget_on_state_returns_none_when_no_n_in_ap(self) -> None:
        """Test _get_widget_on_state returns None when /N is missing in /AP."""
        assert FormFiller._get_widget_on_state({"/AP": {}}) is None


class TestFormFillerResolveRadioFieldStateExtra:
    """Extra tests for _resolve_radio_field_state uncovered branches."""

    def test_resolve_radio_field_state_continues_when_index_gte_len_kids(self) -> None:
        """Test option fallback continues when matching option index exceeds kids length."""
        kid = MagicMock()
        kid.get_object.return_value = {"/AP": {"/N": {"/Off": None}}}
        parent_annotation = {"/Kids": [kid]}

        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Other", "Match"]):
            result = FormFiller._resolve_radio_field_state(parent_annotation, "Match")
            assert result == "/Off"


class TestFormFillerSyncRadioButtonStatesExtra:
    """Extra tests for _sync_radio_button_states inner loop branches."""

    def test_sync_radio_continues_when_no_field_match(self) -> None:
        """Test _sync_radio_button_states continues when widget name not in field_values."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "RadioGroup",
            "/AP": {"/N": {"/Yes": None}},
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.return_value = "Qualified.RadioGroup"

        with patch("privacyforms_pdf.filler.get_field_type", return_value="radiobuttongroup"):
            filler._sync_radio_button_states(writer, {"OtherGroup": "/Yes"})
            assert "/V" not in widget

    def test_sync_radio_matches_by_annotation_name(self) -> None:
        """Test _sync_radio_button_states matches via annotation /T when qualified_name differs."""
        filler = FormFiller()
        writer = MagicMock()

        widget = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "RadioGroup",
            "/AP": {"/N": {"/Yes": None}},
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.return_value = "Qualified.Other"

        with (
            patch("privacyforms_pdf.filler.get_field_type", return_value="radiobuttongroup"),
            patch.object(filler, "_resolve_radio_field_state", return_value="/Yes"),
        ):
            filler._sync_radio_button_states(writer, {"RadioGroup": "/Yes"})
            assert widget["/V"] == NameObject("/Yes")
            assert widget["/AS"] == NameObject("/Yes")

    def test_sync_radio_matches_by_parent_name(self) -> None:
        """Test _sync_radio_button_states matches via parent /T when other names differ."""
        filler = FormFiller()
        writer = MagicMock()

        parent = {
            "/Subtype": "/Widget",
            "/FT": "/Btn",
            "/T": "ParentRadio",
        }
        parent_ref = MagicMock()
        parent_ref.get_object.return_value = parent

        widget = {
            "/Subtype": "/Widget",
            "/Parent": parent_ref,
            "/AP": {"/N": {"/Yes": None}},
        }
        widget_ref = MagicMock()
        widget_ref.get_object.return_value = widget

        writer.pages = [{"/Annots": [widget_ref]}]
        writer._get_qualified_field_name.return_value = "Qualified.Other"

        with (
            patch("privacyforms_pdf.filler.get_field_type", return_value="radiobuttongroup"),
            patch.object(filler, "_resolve_radio_field_state", return_value="/Yes"),
        ):
            filler._sync_radio_button_states(writer, {"ParentRadio": "/Yes"})
            assert parent["/V"] == NameObject("/Yes")
            assert widget["/AS"] == NameObject("/Yes")
            assert widget["/V"] == NameObject("/Yes")


class TestFormFillerResolveListboxIndex:
    """Tests for _resolve_listbox_index uncovered branches."""

    def test_resolve_listbox_index_returns_none_when_not_found(self) -> None:
        """Test _resolve_listbox_index returns None when value is not in options."""
        parent_annotation = {}
        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]):
            result = FormFiller._resolve_listbox_index(parent_annotation, "Green")
            assert result is None

    def test_resolve_listbox_index_continues_loop_before_match(self) -> None:
        """Test _resolve_listbox_index continues loop when first options don't match."""
        parent_annotation = {}
        with patch("privacyforms_pdf.filler.get_field_options", return_value=["Red", "Blue"]):
            result = FormFiller._resolve_listbox_index(parent_annotation, "Blue")
            assert result == 1
