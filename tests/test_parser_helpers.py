"""Unit tests for parser helper functions to boost coverage."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from privacyforms_pdf.parser import (
    _check_input_size,
    _collect_annotation_info,
    _extract_choices_for_button,
    _extract_choices_for_choice,
    _get_appearance_states,
    _is_date_field,
    _normalize_value,
    _resolve_kid_layout,
    _strip_pdf_string,
    determine_button_type,
    determine_choice_type,
    determine_text_type,
    extract_pdf_form,
    get_field_options,
    get_field_type,
    parse_pdf,
)
from privacyforms_pdf.schema import ChoiceOption, FieldFlags

if TYPE_CHECKING:
    from pathlib import Path


class TestCheckInputSize:
    """Tests for _check_input_size."""

    def test_too_large_raises(self, tmp_path: Path) -> None:
        """It raises ValueError when the file exceeds the size limit."""
        path = tmp_path / "big.pdf"
        path.write_text("x")
        os.truncate(path, 51 * 1024 * 1024)
        with pytest.raises(ValueError, match="too large"):
            _check_input_size(path)

    def test_missing_file_is_noop(self, tmp_path: Path) -> None:
        """It does nothing when the file does not exist."""
        path = tmp_path / "missing.pdf"
        _check_input_size(path)


class TestStripPdfString:
    """Tests for _strip_pdf_string."""

    def test_none(self) -> None:
        """It returns None for None input."""
        assert _strip_pdf_string(None) is None

    def test_off(self) -> None:
        """It preserves the string 'Off'."""
        assert _strip_pdf_string("Off") == "Off"

    def test_name_object_slash(self) -> None:
        """It strips a leading slash from NameObject strings."""
        assert _strip_pdf_string("/Yes") == "Yes"

    def test_empty(self) -> None:
        """It returns None for whitespace-only strings."""
        assert _strip_pdf_string("   ") is None

    def test_strips(self) -> None:
        """It strips surrounding whitespace."""
        assert _strip_pdf_string("  hello  ") == "hello"


class TestNormalizeValue:
    """Tests for _normalize_value."""

    def test_none(self) -> None:
        """It returns None for None input."""
        assert _normalize_value(None) is None

    def test_name_yes(self) -> None:
        """It converts NameObject '/Yes' to True."""
        assert _normalize_value(NameObject("/Yes")) is True

    def test_name_on(self) -> None:
        """It converts NameObject '/On' to True."""
        assert _normalize_value(NameObject("/On")) is True

    def test_name_off(self) -> None:
        """It converts NameObject '/Off' to False."""
        assert _normalize_value(NameObject("/Off")) is False

    def test_name_no(self) -> None:
        """It converts NameObject '/No' to False."""
        assert _normalize_value(NameObject("/No")) is False

    def test_name_other(self) -> None:
        """It strips the slash from other NameObjects."""
        assert _normalize_value(NameObject("/Foo")) == "Foo"

    def test_string_empty(self) -> None:
        """It returns None for whitespace-only strings."""
        assert _normalize_value("  ") is None

    def test_string(self) -> None:
        """It strips surrounding whitespace from strings."""
        assert _normalize_value(" hello ") == "hello"

    def test_generic_object(self) -> None:
        """It stringifies generic objects."""
        assert _normalize_value(123) == "123"


class TestGetAppearanceStates:
    """Tests for _get_appearance_states."""

    def test_no_ap(self) -> None:
        """It returns an empty list when /AP is missing."""
        d = DictionaryObject()
        assert _get_appearance_states(d) == []

    def test_ap_not_dict(self) -> None:
        """It returns an empty list when /AP is not a dictionary."""
        d = DictionaryObject({NameObject("/AP"): ArrayObject([])})
        assert _get_appearance_states(d) == []

    def test_n_missing(self) -> None:
        """It returns an empty list when /N is missing."""
        d = DictionaryObject({NameObject("/AP"): DictionaryObject()})
        assert _get_appearance_states(d) == []

    def test_n_not_dict(self) -> None:
        """It returns an empty list when /N is not a dictionary."""
        d = DictionaryObject(
            {NameObject("/AP"): DictionaryObject({NameObject("/N"): ArrayObject([])})}
        )
        assert _get_appearance_states(d) == []

    def test_skips_off_and_slash(self) -> None:
        """It skips 'Off' entries and strips leading slashes."""
        d = DictionaryObject(
            {
                NameObject("/AP"): DictionaryObject(
                    {
                        NameObject("/N"): DictionaryObject(
                            {
                                NameObject("/Off"): DictionaryObject(),
                                NameObject("/On"): DictionaryObject(),
                                NameObject("/Yes"): DictionaryObject(),
                            }
                        )
                    }
                )
            }
        )
        assert _get_appearance_states(d) == ["On", "Yes"]


class TestExtractChoicesForButton:
    """Tests for _extract_choices_for_button."""

    def test_no_kids_no_ap_with_v(self) -> None:
        """It falls back to /V when no kids or appearance exist."""
        d = DictionaryObject({NameObject("/V"): NameObject("/Selected")})
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="Selected", text="Selected", source_name="Selected")]

    def test_no_kids_no_ap_no_v_defaults_yes(self) -> None:
        """It defaults to Yes when nothing else is available."""
        d = DictionaryObject()
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="Yes", text="Yes", source_name="Yes")]

    def test_kid_not_dict(self) -> None:
        """It ignores kids that are not dictionaries."""
        d = DictionaryObject({NameObject("/Kids"): ArrayObject([NameObject("/Foo")])})
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="Yes", text="Yes", source_name="Yes")]

    def test_duplicate_states_across_kids(self) -> None:
        """It deduplicates states that appear in multiple kids."""

        def make_kid(state: str) -> DictionaryObject:
            return DictionaryObject(
                {
                    NameObject("/AP"): DictionaryObject(
                        {
                            NameObject("/N"): DictionaryObject(
                                {NameObject(f"/{state}"): DictionaryObject()}
                            )
                        }
                    )
                }
            )

        d = DictionaryObject({NameObject("/Kids"): ArrayObject([make_kid("A"), make_kid("A")])})
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="A", text="A", source_name="A")]


class TestExtractChoicesForChoice:
    """Tests for _extract_choices_for_choice."""

    def test_no_opt(self) -> None:
        """It returns an empty list when /Opt is missing."""
        d = DictionaryObject()
        assert _extract_choices_for_choice(d) == []

    def test_opt_not_array(self) -> None:
        """It returns an empty list when /Opt is not an array."""
        d = DictionaryObject({NameObject("/Opt"): NameObject("/Foo")})
        assert _extract_choices_for_choice(d) == []

    def test_opt_array_items(self) -> None:
        """It handles tuple, string and NameObject items in /Opt."""
        d = DictionaryObject(
            {
                NameObject("/Opt"): ArrayObject(
                    [
                        ArrayObject([TextStringObject("a"), TextStringObject("A")]),
                        TextStringObject("b"),
                        TextStringObject("c"),
                        NameObject("/d"),
                    ]
                )
            }
        )
        result = _extract_choices_for_choice(d)
        assert result[0].value == "a"
        assert result[0].text == "A"
        assert result[1].value == "b"
        assert result[2].value == "c"
        assert result[3].value == "d"


class TestDetermineTypes:
    """Tests for determine_button_type, determine_choice_type and determine_text_type."""

    def test_determine_button_checkbox(self) -> None:
        """It classifies buttons based on flags and kid count."""
        flags = FieldFlags()
        assert determine_button_type(flags, 2, False) == "radiobuttongroup"
        assert determine_button_type(flags, 0, False) == "checkbox"

    def test_determine_choice_listbox(self) -> None:
        """It returns listbox when the combo flag is not set."""
        flags = FieldFlags()
        assert determine_choice_type(flags) == "listbox"

    def test_determine_text_textarea(self) -> None:
        """It returns textarea when the multiline flag is set."""
        flags = FieldFlags(multiline=True)
        assert determine_text_type("Notes", None, flags) == "textarea"

    def test_determine_text_datefield(self) -> None:
        """It detects datefields from name heuristics or value patterns."""
        flags = FieldFlags()
        assert determine_text_type("Date", "2024-01-01", flags) == "datefield"
        assert determine_text_type("dob", None, flags) == "datefield"


class TestGetFieldType:
    """Tests for get_field_type."""

    def test_ft_none_uses_type(self) -> None:
        """It falls back to /Type when /FT is missing."""
        field = {"/Type": "/Sig"}
        assert get_field_type(field) == "signature"

    def test_tx_textfield_with_aa(self) -> None:
        """It does not over-detect datefields from /AA or /DV presence."""
        field = {"/FT": "/Tx", "/AA": {}}
        assert get_field_type(field) == "textfield"

    def test_tx_textarea(self) -> None:
        """It detects textarea via the multiline flag."""
        field = {"/FT": "/Tx", "/Ff": 1 << 12}
        assert get_field_type(field) == "textarea"

    def test_ch_listbox(self) -> None:
        """It returns listbox when the combo flag is absent."""
        field = {"/FT": "/Ch", "/Ff": 0}
        assert get_field_type(field) == "listbox"

    def test_sig(self) -> None:
        """It correctly identifies signature fields."""
        field = {"/FT": "/Sig"}
        assert get_field_type(field) == "signature"

    def test_unknown_defaults_textfield(self) -> None:
        """It defaults to textfield for unknown types."""
        field = {"/FT": "/Foo"}
        assert get_field_type(field) == "textfield"


class TestGetFieldOptions:
    """Tests for get_field_options."""

    def test_opt_arrays(self) -> None:
        """It extracts options from /Opt arrays of varying shapes."""
        field = {
            "/Opt": ArrayObject(
                [
                    ArrayObject([TextStringObject("a"), TextStringObject("A")]),
                    ArrayObject([TextStringObject("b")]),
                    TextStringObject("c"),
                ]
            )
        }
        assert get_field_options(field) == ["A", "b", "c"]

    def test_kids_ap(self) -> None:
        """It extracts options from kid widget appearance states."""
        kid = DictionaryObject(
            {
                NameObject("/AP"): DictionaryObject(
                    {
                        NameObject("/N"): DictionaryObject(
                            {
                                NameObject("/Off"): DictionaryObject(),
                                NameObject("/Yes"): DictionaryObject(),
                            }
                        )
                    }
                )
            }
        )
        field = {"/Kids": ArrayObject([kid])}
        assert get_field_options(field) == ["/Yes"]


class TestResolveKidLayout:
    """Tests for _resolve_kid_layout."""

    def test_kid_without_idnum(self) -> None:
        """It resolves rects from kids without indirect references."""
        kid = DictionaryObject(
            {
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
                )
            }
        )
        page, rect = _resolve_kid_layout(ArrayObject([kid]), {})
        assert rect == [0.0, 0.0, 10.0, 10.0]

    def test_kid_not_dict(self) -> None:
        """It skips kids that are not dictionaries."""
        page, rect = _resolve_kid_layout(ArrayObject([NameObject("/Foo")]), {})
        assert rect is None

    def test_kid_rect_wrong_length(self) -> None:
        """It skips kids with malformed rects."""
        kid = DictionaryObject({NameObject("/Rect"): ArrayObject([NumberObject(0)])})
        page, rect = _resolve_kid_layout(ArrayObject([kid]), {})
        assert rect is None

    def test_multiple_kids_combined_rect(self) -> None:
        """It combines rects from multiple kids into a bounding box."""
        kid1 = DictionaryObject(
            {
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
                )
            }
        )
        kid2 = DictionaryObject(
            {
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(20), NumberObject(20), NumberObject(30), NumberObject(30)]
                )
            }
        )
        page, rect = _resolve_kid_layout(ArrayObject([kid1, kid2]), {})
        assert rect == [0.0, 0.0, 30.0, 30.0]


class TestParsePdfEdgeCases:
    """Tests for parse_pdf edge cases."""

    def test_unsupported_field_type_skipped(self, tmp_path: Path) -> None:
        """It skips fields with unsupported /FT values."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Barcode"),
                NameObject("/FT"): NameObject("/Barcode"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Barcode": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields == []

    def test_non_dict_field_ref_skipped(self, tmp_path: Path) -> None:
        """It skips field references that do not resolve to dictionaries."""
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Bad": NameObject("/Foo")}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields == []

    def test_checkbox_string_normalization(self, tmp_path: Path) -> None:
        """It normalizes checkbox string values to booleans."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Agree"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): TextStringObject("Off"),
                NameObject("/DV"): TextStringObject("No"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Agree": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value is False
            assert result.fields[0].default_value is False

    def test_radiobuttongroup_off_becomes_none(self, tmp_path: Path) -> None:
        """It converts radiobuttongroup 'Off' values to None."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Status"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): NameObject("/Off"),
                NameObject("/DV"): NameObject("/Off"),
                NameObject("/Ff"): NumberObject(49152),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Status": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value is None
            assert result.fields[0].default_value is None

    def test_choice_multi_select(self, tmp_path: Path) -> None:
        """It handles multi-select choice fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Skills"),
                NameObject("/FT"): NameObject("/Ch"),
                NameObject("/Ff"): NumberObject(1 << 21),
                NameObject("/V"): ArrayObject([TextStringObject("A"), TextStringObject("B")]),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Skills": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value == ["A", "B"]
            assert result.fields[0].type == "listbox"


class TestCheckInputSizeExtra:
    """Additional tests for _check_input_size."""

    def test_within_limit_is_noop(self, tmp_path: Path) -> None:
        """It does nothing when the file exists and is within the limit."""
        path = tmp_path / "small.pdf"
        path.write_text("x")
        _check_input_size(path)


class TestIsDateField:
    """Tests for _is_date_field."""

    def test_date_by_value_pattern(self) -> None:
        """It detects date fields from value patterns when the name has no keywords."""
        assert _is_date_field("Name", "01/02/2024") is True


class TestNormalizeValueExtra:
    """Additional tests for _normalize_value."""

    def test_name_yes_without_slash(self) -> None:
        """It converts NameObject 'Yes' (no slash) to True."""
        assert _normalize_value(NameObject("Yes")) is True


class TestGetAppearanceStatesExtra:
    """Additional tests for _get_appearance_states."""

    def test_ap_truthy_not_dict(self) -> None:
        """It returns empty list when /AP is truthy but not a dictionary."""
        d = DictionaryObject({NameObject("/AP"): NameObject("/Foo")})
        assert _get_appearance_states(d) == []

    def test_n_truthy_not_dict(self) -> None:
        """It returns empty list when /N is truthy but not a dictionary."""
        d = DictionaryObject(
            {NameObject("/AP"): DictionaryObject({NameObject("/N"): NameObject("/Foo")})}
        )
        assert _get_appearance_states(d) == []

    def test_key_without_slash(self) -> None:
        """It handles keys that do not start with a slash."""
        d = DictionaryObject(
            {
                NameObject("/AP"): DictionaryObject(
                    {NameObject("/N"): DictionaryObject({NameObject("On"): DictionaryObject()})}
                )
            }
        )
        assert _get_appearance_states(d) == ["On"]


class TestExtractChoicesForButtonExtra:
    """Additional tests for _extract_choices_for_button."""

    def test_no_kids_with_ap_skips_fallback(self) -> None:
        """It skips the /V fallback when appearance states already exist."""
        d = DictionaryObject(
            {
                NameObject("/AP"): DictionaryObject(
                    {NameObject("/N"): DictionaryObject({NameObject("/Yes"): DictionaryObject()})}
                )
            }
        )
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="Yes", text="Yes", source_name="Yes")]

    def test_fallback_v_without_slash(self) -> None:
        """It handles /V values that do not start with a slash."""
        d = DictionaryObject({NameObject("/V"): NameObject("Selected")})
        result = _extract_choices_for_button(d)
        assert result == [ChoiceOption(value="Selected", text="Selected", source_name="Selected")]


class TestDetermineTypesExtra:
    """Additional tests for determine_*_type helpers."""

    def test_determine_text_textfield(self) -> None:
        """It returns textfield when no special flags or patterns match."""
        flags = FieldFlags()
        assert determine_text_type("Name", "hello", flags) == "textfield"

    def test_determine_choice_combobox(self) -> None:
        """It returns combobox when the combo flag is set."""
        flags = FieldFlags(combo=True)
        assert determine_choice_type(flags) == "combobox"

    def test_determine_button_has_opt(self) -> None:
        """It returns radiobuttongroup when has_opt is True."""
        flags = FieldFlags()
        assert determine_button_type(flags, 0, has_opt=True) == "radiobuttongroup"


class TestGetFieldTypeExtra:
    """Additional tests for get_field_type."""

    def test_tx_textfield(self) -> None:
        """It returns textfield for plain /Tx fields."""
        field = {"/FT": "/Tx", "/Ff": 0}
        assert get_field_type(field) == "textfield"

    def test_btn_checkbox(self) -> None:
        """It returns checkbox for /Btn without /Opt."""
        field = {"/FT": "/Btn"}
        assert get_field_type(field) == "checkbox"

    def test_btn_radiobuttongroup(self) -> None:
        """It returns radiobuttongroup for /Btn with /Opt."""
        field = {"/FT": "/Btn", "/Opt": []}
        assert get_field_type(field) == "radiobuttongroup"

    def test_ch_combobox(self) -> None:
        """It returns combobox when the combo flag is set."""
        field = {"/FT": "/Ch", "/Ff": 0x40000}
        assert get_field_type(field) == "combobox"


class TestGetFieldOptionsExtra:
    """Additional tests for get_field_options."""

    def test_opts_not_array(self) -> None:
        """It returns empty list when /Opt is not an array-like object."""
        field = {"/Opt": NameObject("/Foo")}
        assert get_field_options(field) == []

    def test_kid_without_ap(self) -> None:
        """It skips kids that lack an /AP dictionary."""
        kid = DictionaryObject({})
        field = {"/Kids": ArrayObject([kid])}
        assert get_field_options(field) == []

    def test_kid_ap_without_n(self) -> None:
        """It skips kids whose /AP lacks an /N entry."""
        kid = DictionaryObject({NameObject("/AP"): DictionaryObject()})
        field = {"/Kids": ArrayObject([kid])}
        assert get_field_options(field) == []

    def test_no_opts_no_kids(self) -> None:
        """It returns empty list when neither /Opt nor /Kids are present."""
        assert get_field_options({}) == []


class TestCollectAnnotationInfo:
    """Tests for _collect_annotation_info."""

    def test_mixed_annotations(self) -> None:
        """It processes a page with widgets, non-widgets and bad refs."""

        class MockIndirect:
            def __init__(self, obj: object, idnum: int, generation: int) -> None:
                self.obj = obj
                self.idnum = idnum
                self.generation = generation

            def get_object(self) -> object:
                return self.obj

        widget1 = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/T"): TextStringObject("Field1"),
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
                ),
            }
        )
        widget2 = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/T"): TextStringObject("Field1"),  # duplicate name
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(20), NumberObject(20), NumberObject(30), NumberObject(30)]
                ),
            }
        )
        non_widget = DictionaryObject({NameObject("/Subtype"): NameObject("/Foo")})

        page = MagicMock()
        page.get = MagicMock(
            return_value=[
                MockIndirect(widget1, idnum=1, generation=0),
                MockIndirect(widget2, idnum=2, generation=0),
                non_widget,
                "not a dict",
            ]
        )
        reader = MagicMock()
        reader.pages = [page]

        name_map, ref_map = _collect_annotation_info(reader)
        assert name_map["Field1"] == (1, widget1["/Rect"])
        assert (1, 0) in ref_map
        assert (2, 0) in ref_map

    def test_plain_dict_annot(self) -> None:
        """It handles plain dictionary annotations without indirect refs."""
        widget = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/T"): TextStringObject("Field2"),
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(5), NumberObject(5), NumberObject(15), NumberObject(15)]
                ),
            }
        )
        page = MagicMock()
        page.get = MagicMock(return_value=[widget])
        reader = MagicMock()
        reader.pages = [page]
        name_map, ref_map = _collect_annotation_info(reader)
        assert name_map["Field2"] == (1, widget["/Rect"])
        assert ref_map == {}


class TestResolveKidLayoutExtra:
    """Additional tests for _resolve_kid_layout."""

    def test_kid_in_ref_map_no_rect(self) -> None:
        """It handles kids in ref_map that have no rect."""

        class MockKid:
            def __init__(self, idnum: int, generation: int) -> None:
                self.idnum = idnum
                self.generation = generation

        kid = MockKid(1, 0)
        ref_map: dict[tuple[int, int], tuple[int, list[float] | None]] = {(1, 0): (2, None)}
        page, rect = _resolve_kid_layout(ArrayObject([kid]), ref_map)
        assert page == 2
        assert rect is None

    def test_kid_not_in_ref_map_with_rect(self) -> None:
        """It falls back to the kid object's /Rect when not in ref_map."""

        class MockKid:
            def __init__(self, idnum: int, generation: int) -> None:
                self.idnum = idnum
                self.generation = generation

            def get_object(self) -> object:
                return DictionaryObject(
                    {
                        NameObject("/Rect"): ArrayObject(
                            [
                                NumberObject(0),
                                NumberObject(0),
                                NumberObject(10),
                                NumberObject(10),
                            ]
                        ),
                    }
                )

        kid = MockKid(1, 0)
        page, rect = _resolve_kid_layout(ArrayObject([kid]), {})
        assert rect == [0.0, 0.0, 10.0, 10.0]


class TestParsePdfEdgeCasesExtra:
    """Additional edge-case tests for parse_pdf."""

    def test_no_fields(self, tmp_path: Path) -> None:
        """It returns an empty representation when the PDF has no fields."""
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields == []

    def test_with_reader_arg(self, tmp_path: Path) -> None:
        """It accepts a pre-existing PdfReader and skips creating a new one."""
        reader = MagicMock()
        reader.get_fields.return_value = {}
        reader.pages = []
        result = parse_pdf(tmp_path / "form.pdf", reader=reader)
        assert result.fields == []

    def test_textfield_normal(self, tmp_path: Path) -> None:
        """It correctly parses a plain textfield."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Name"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/Ff"): NumberObject(0),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Name": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "textfield"
            assert result.fields[0].value is None

    def test_pushbutton_skipped(self, tmp_path: Path) -> None:
        """It skips pushbutton fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Click"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/Ff"): NumberObject(1 << 16),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Click": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields == []

    def test_signature_field(self, tmp_path: Path) -> None:
        """It correctly parses signature fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Sign"),
                NameObject("/FT"): NameObject("/Sig"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Sign": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "signature"

    def test_checkbox_string_yes(self, tmp_path: Path) -> None:
        """It normalizes checkbox string value 'Yes' to boolean True."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Agree"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): TextStringObject("Yes"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Agree": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value is True

    def test_combobox_single_select(self, tmp_path: Path) -> None:
        """It handles single-select combobox fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Country"),
                NameObject("/FT"): NameObject("/Ch"),
                NameObject("/Ff"): NumberObject(1 << 17),
                NameObject("/V"): TextStringObject("USA"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Country": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "combobox"
            assert result.fields[0].value == "USA"

    def test_listbox_single_select(self, tmp_path: Path) -> None:
        """It handles single-select listbox fields."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Skills"),
                NameObject("/FT"): NameObject("/Ch"),
                NameObject("/Ff"): NumberObject(0),
                NameObject("/V"): TextStringObject("A"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Skills": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].type == "listbox"
            assert result.fields[0].value == "A"

    def test_resolve_kid_layout_called(self, tmp_path: Path) -> None:
        """It falls back to _resolve_kid_layout when annot_info lacks the field."""
        kid = DictionaryObject(
            {
                NameObject("/Rect"): ArrayObject(
                    [
                        NumberObject(0),
                        NumberObject(0),
                        NumberObject(10),
                        NumberObject(10),
                    ]
                ),
            }
        )
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Radio"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/Ff"): NumberObject(1 << 15),
                NameObject("/Kids"): ArrayObject([kid]),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Radio": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].layout is not None
            assert result.fields[0].layout.x == 0
            assert result.fields[0].layout.y == 0
            assert result.fields[0].layout.width == 10
            assert result.fields[0].layout.height == 10

    def test_flags_int_zero(self, tmp_path: Path) -> None:
        """It omits field_flags when /Ff is 0."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Name"),
                NameObject("/FT"): NameObject("/Tx"),
                NameObject("/Ff"): NumberObject(0),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Name": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].field_flags is None


class TestExtractPdfForm:
    """Tests for the extract_pdf_form facade."""

    def test_facade(self, tmp_path: Path) -> None:
        """It proxies to parse_pdf."""
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {}
            mock_reader.return_value.pages = []
            result = extract_pdf_form(tmp_path / "form.pdf")
            assert result.fields == []


class TestCollectAnnotationInfoExtra:
    """Additional tests for _collect_annotation_info edge cases."""

    def test_page_without_annots(self) -> None:
        """It skips pages that have no annotations."""
        page_no_annots = MagicMock()
        page_no_annots.get = MagicMock(return_value=None)
        reader = MagicMock()
        reader.pages = [page_no_annots]
        name_map, ref_map = _collect_annotation_info(reader)
        assert name_map == {}
        assert ref_map == {}

    def test_widget_without_t(self) -> None:
        """It skips widget annotations that have no /T entry."""
        widget = DictionaryObject(
            {
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Rect"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)]
                ),
            }
        )
        page = MagicMock()
        page.get = MagicMock(return_value=[widget])
        reader = MagicMock()
        reader.pages = [page]
        name_map, ref_map = _collect_annotation_info(reader)
        assert name_map == {}
        assert ref_map == {}


class TestResolveKidLayoutExtra2:
    """Additional tests for _resolve_kid_layout."""

    def test_kid_in_ref_map_with_rect(self) -> None:
        """It appends rect from a kid found in ref_map."""

        class MockKid:
            def __init__(self, idnum: int, generation: int) -> None:
                self.idnum = idnum
                self.generation = generation

        kid = MockKid(1, 0)
        ref_map: dict[tuple[int, int], tuple[int, list[float] | None]] = {
            (1, 0): (1, [0.0, 0.0, 10.0, 10.0])
        }
        page, rect = _resolve_kid_layout(ArrayObject([kid]), ref_map)
        assert page == 1
        assert rect == [0.0, 0.0, 10.0, 10.0]


class TestParsePdfMaxFields:
    """Tests for MAX_FIELDS limit in parse_pdf."""

    def test_too_many_fields_raises(self, tmp_path: Path) -> None:
        """It raises ValueError when PDF has more than 10,000 fields."""
        from privacyforms_pdf.parser import _MAX_FIELDS

        fields = {f"field_{i}": DictionaryObject({}) for i in range(_MAX_FIELDS + 1)}
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = fields
            mock_reader.return_value.pages = []
            with pytest.raises(ValueError, match="too many fields"):
                parse_pdf(tmp_path / "form.pdf")

    def test_at_limit_succeeds(self, tmp_path: Path) -> None:
        """It succeeds when PDF has exactly 10,000 fields."""
        from privacyforms_pdf.parser import _MAX_FIELDS

        fields = {
            f"field_{i}": DictionaryObject(
                {
                    NameObject("/T"): TextStringObject(f"field_{i}"),
                    NameObject("/FT"): NameObject("/Tx"),
                }
            )
            for i in range(_MAX_FIELDS)
        }
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = fields
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert len(result.fields) == _MAX_FIELDS


class TestParsePdfEdgeCasesExtra2:
    """More edge-case tests for parse_pdf."""

    def test_checkbox_name_yes(self, tmp_path: Path) -> None:
        """It handles checkbox values that normalize to a bool (not a string)."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("Agree"),
                NameObject("/FT"): NameObject("/Btn"),
                NameObject("/V"): NameObject("/Yes"),
            }
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"Agree": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value is True


class TestParsePdfEdgeCasesExtra3:
    """Edge-case tests that require deeper mocking."""

    def test_unknown_field_type_else_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It reaches the generic else branch for unexpected field types."""
        field_dict = DictionaryObject(
            {
                NameObject("/T"): TextStringObject("X"),
                NameObject("/FT"): NameObject("/Btn"),
            }
        )

        class MockField:
            def __init__(self, **kwargs: object) -> None:
                for k, v in kwargs.items():
                    setattr(self, k, v)

        monkeypatch.setattr("privacyforms_pdf.parser.PDFField", MockField)
        monkeypatch.setattr(
            "privacyforms_pdf.parser.PDFRepresentation",
            lambda **kwargs: type("MockRep", (), kwargs)(),
        )
        monkeypatch.setattr(
            "privacyforms_pdf.parser.determine_button_type",
            lambda *args, **kwargs: "unknown",
        )
        with patch("privacyforms_pdf.parser.PdfReader") as mock_reader:
            mock_reader.return_value.get_fields.return_value = {"X": field_dict}
            mock_reader.return_value.pages = []
            result = parse_pdf(tmp_path / "form.pdf")
            assert result.fields[0].value is None
            assert result.fields[0].default_value is None
