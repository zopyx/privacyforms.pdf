"""PDF form filling logic using pypdf."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)

from privacyforms_pdf.parser import get_field_options, get_field_type

if TYPE_CHECKING:
    from pypdf import PdfReader, PdfWriter


class FormFiller:
    """Fills PDF forms using pypdf."""

    def __init__(self) -> None:
        """Initialize the filler."""

    @staticmethod
    def _get_widget_annotation(
        annotation_ref: Any,
    ) -> tuple[DictionaryObject, DictionaryObject]:
        """Resolve widget and parent annotations."""
        annotation = cast(
            "DictionaryObject",
            (
                annotation_ref.get_object()
                if hasattr(annotation_ref, "get_object")
                else annotation_ref
            ),
        )
        parent_ref = annotation.get("/Parent")
        parent_annotation = cast(
            "DictionaryObject",
            parent_ref.get_object() if parent_ref else annotation,
        )
        return annotation, parent_annotation

    @staticmethod
    def _get_widget_on_state(annotation: dict[str, Any]) -> str | None:
        """Return the non-Off appearance state for a widget, if any.

        PDF button widgets define their visual states in an Appearance dictionary
        (/AP) with a Normal sub-dictionary (/N). Each key in /N is a state name
        (e.g. "/Yes", "/Off"). We return the first state that is not "/Off".
        """
        ap = annotation.get("/AP")
        if not ap or "/N" not in ap:
            return None

        for state in ap["/N"]:
            state_name = str(state)
            if state_name.lower() != "/off":
                return state_name
        return None

    @classmethod
    def _resolve_radio_field_state(
        cls,
        parent_annotation: dict[str, Any],
        value: str,
    ) -> str:
        """Resolve the selected on-state name for a radio group.

        Radio buttons in PDF are tricky because the "on" state name stored in
        the widget's /AP dictionary may differ from the value written to the
        field's /V entry. We try three strategies:

        1. Direct match: the desired value exactly matches a kid's on-state.
        2. Index match: the desired value matches an entry in the /Opt array;
           we map that index to the corresponding kid widget and use its on-state.
        3. Normalized match: compare after stripping leading slashes.

        If nothing matches we fall back to "/Off" (unchecked).
        """
        normalized_value = value if value.startswith("/") else f"/{value}"
        kids = parent_annotation.get("/Kids", [])

        for kid_ref in kids:
            kid_annotation = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            kid_state = cls._get_widget_on_state(kid_annotation)
            if kid_state == normalized_value:
                return normalized_value

        options = get_field_options(parent_annotation)
        if options:
            option_value = value[1:] if value.startswith("/") else value
            for index, option in enumerate(options):
                if option != option_value or index >= len(kids):
                    continue
                kid_annotation = (
                    kids[index].get_object() if hasattr(kids[index], "get_object") else kids[index]
                )
                kid_state = cls._get_widget_on_state(kid_annotation)
                if kid_state is not None:
                    return kid_state

        for kid_ref in kids:
            kid_annotation = kid_ref.get_object() if hasattr(kid_ref, "get_object") else kid_ref
            kid_state = cls._get_widget_on_state(kid_annotation)
            if kid_state and kid_state.lstrip("/") == value.lstrip("/"):
                return kid_state

        return "/Off"

    def _sync_radio_button_states(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update radio widget appearances to match the selected option.

        PDF viewers render a radio button based on the widget's Appearance State
        (/AS) entry. The field's value (/V) tells the viewer which option is
        selected for the group, while each individual widget's /AS determines
        whether that specific button appears checked (its on-state) or unchecked
        (/Off). We must update both /V on the parent field and /AS on every
        kid widget so that the visual state matches the filled data.
        """
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                if parent_annotation.get("/FT", annotation.get("/FT")) != "/Btn":
                    continue
                if get_field_type(parent_annotation) != "radiobuttongroup":
                    continue

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                if qualified_name in field_values:
                    matched_field_name = qualified_name
                elif annotation_name in field_values:
                    matched_field_name = annotation_name
                elif parent_name in field_values:
                    matched_field_name = parent_name
                if matched_field_name is None:
                    continue

                selected_state = self._resolve_radio_field_state(
                    parent_annotation,
                    field_values[matched_field_name],
                )
                widget_state = self._get_widget_on_state(annotation)
                # Only the widget whose on-state matches the selected value
                # should show as checked; all others must be /Off.
                state = selected_state if widget_state == selected_state else "/Off"
                parent_annotation[NameObject("/V")] = NameObject(selected_state)
                annotation[NameObject("/AS")] = NameObject(state)
                annotation[NameObject("/V")] = NameObject(state)

    @staticmethod
    def _resolve_listbox_index(parent_annotation: dict[str, Any], value: str) -> int | None:
        """Resolve the selected index for a listbox value."""
        options = get_field_options(parent_annotation)
        normalized_value = value[1:] if value.startswith("/") else value
        for index, option in enumerate(options):
            if option == normalized_value:
                return index
        return None

    def _sync_listbox_selection_indexes(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Update listbox values and selection indexes for viewer highlighting.

        In addition to setting the field value (/V), PDF viewers need:

        - /I: an array of selected indexes so the viewer knows which rows are
          highlighted (required for multi-select, useful for single-select).
        - /TI: the top index (scroll position) so the selected item is visible.
        - /AP /N: an appearance stream that renders the list with the current
          selection visually indicated.

        We update all of these so the filled listbox looks correct in common
        viewers (Acrobat, Preview, Chrome PDF, etc.).
        """
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                if parent_annotation.get("/FT", annotation.get("/FT")) != "/Ch":
                    continue
                if get_field_type(parent_annotation) != "listbox":
                    continue

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                if qualified_name in field_values:
                    matched_field_name = qualified_name
                elif annotation_name in field_values:
                    matched_field_name = annotation_name
                elif parent_name in field_values:
                    matched_field_name = parent_name
                if matched_field_name is None:
                    continue

                value = field_values[matched_field_name]
                selected_index = self._resolve_listbox_index(parent_annotation, value)
                text_value = TextStringObject(value)
                parent_annotation[NameObject("/V")] = text_value
                annotation[NameObject("/V")] = text_value
                if selected_index is not None:
                    indexes = ArrayObject([NumberObject(selected_index)])
                    parent_annotation[NameObject("/I")] = indexes
                    annotation[NameObject("/I")] = ArrayObject([NumberObject(selected_index)])
                    parent_annotation[NameObject("/TI")] = NumberObject(selected_index)
                    annotation[NameObject("/TI")] = NumberObject(selected_index)
                appearance_ref = self._build_listbox_appearance_stream(
                    writer,
                    annotation,
                    parent_annotation,
                    selected_index,
                )
                if appearance_ref is not None:
                    if "/AP" not in annotation:
                        annotation[NameObject("/AP")] = DictionaryObject()
                    appearance_dict = cast("DictionaryObject", annotation["/AP"])
                    appearance_dict[NameObject("/N")] = appearance_ref

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        """Escape text for use in a PDF string literal."""
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _build_listbox_appearance_stream(
        self,
        writer: PdfWriter,
        annotation: dict[str, Any],
        parent_annotation: dict[str, Any],
        selected_index: int | None,
    ) -> Any | None:
        """Build a listbox appearance stream with highlighted selection.

        PDF appearance streams are self-contained content streams (similar to
        mini page descriptions) that define how a form field looks. We build one
        from scratch because pypdf does not generate listbox visuals.

        Content-stream operators used (PDF spec reference):

        - q / Q          : save / restore graphics state
        - BMC / EMC      : begin / end marked-content sequence
        - re             : rectangle (draw path)
        - W              : set clipping path
        - n              : end path without filling or stroking
        - rg             : set RGB non-stroking colour (0-1 range)
        - f              : fill path
        - BT / ET        : begin / end text object
        - Tf             : set text font and size
        - Tm             : set text matrix (position)
        - Tj             : show text
        - g              : set grey non-stroking colour (1 = white, 0 = black)
        """
        options = get_field_options(parent_annotation)
        if not options:
            return None

        ap = annotation.get("/AP")
        normal_ap = ap.get("/N").get_object() if ap and "/N" in ap else None
        resources = (
            cast("DictionaryObject", normal_ap.get("/Resources"))
            if normal_ap is not None and "/Resources" in normal_ap
            else DictionaryObject()
        )

        # Re-use the existing bounding box if available; otherwise use a
        # sensible default so the listbox still renders.
        bbox = (
            normal_ap.get("/BBox")
            if normal_ap is not None and "/BBox" in normal_ap
            else ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(150), NumberObject(60)]
            )
        )
        width = float(bbox[2]) - float(bbox[0])
        height = float(bbox[3]) - float(bbox[1])
        line_height = height / max(len(options), 1)
        font_size = max(8.0, min(12.0, line_height * 0.75))

        # Try to inherit the font name from the existing appearance resources;
        # fall back to a generic "/F0" which most PDF viewers substitute.
        font_name = "/F0"
        if "/Font" in resources and resources["/Font"]:
            fonts = cast("DictionaryObject", resources["/Font"])
            font_name = str(next(iter(fonts.keys())))

        # --- Build the content stream line by line ---
        lines: list[str] = [
            "q",                     # save graphics state
            "/Tx BMC",               # marked-content tag for text field
            "q",                     # nested save for clipping
            # Clip to the interior of the bbox (1-pt inset)
            f"1 1 {max(width - 2, 1):.3f} {max(height - 2, 1):.3f} re",
            "W",                     # use rectangle as clipping path
            "n",                     # end path (no fill, no stroke)
        ]
        if selected_index is not None:
            highlight_y = height - (selected_index + 1) * line_height
            lines.extend(
                [
                    # Light-blue highlight colour (approximates Acrobat's default)
                    "0.600006 0.756866 0.854904 rg",
                    f"1 {highlight_y:.3f} {max(width - 2, 1):.3f} {line_height:.3f} re",
                    "f",                 # fill the highlight rectangle
                ]
            )

        lines.extend(
            [
                "BT",                    # begin text object
                f"{font_name} {font_size:.3f} Tf",  # set font
            ]
        )
        for index, option in enumerate(options):
            # White text on highlighted row, black text otherwise
            lines.append("1 g" if index == selected_index else "0 g")
            text_y = height - ((index + 1) * line_height) + ((line_height - font_size) / 2)
            escaped = self._escape_pdf_text(str(option))
            lines.append(f"1 0 0 1 2 {text_y:.3f} Tm")  # position text cursor
            lines.append(f"({escaped}) Tj")             # draw the option text
        lines.extend(["ET", "Q", "EMC", "Q"])           # close all groups

        stream = StreamObject()
        stream[NameObject("/Type")] = NameObject("/XObject")
        stream[NameObject("/Subtype")] = NameObject("/Form")
        stream[NameObject("/BBox")] = bbox
        stream[NameObject("/Resources")] = resources
        stream.set_data("\n".join(lines).encode("utf-8"))
        return writer._add_object(stream)

    def _fill_form_fields_without_appearance(
        self,
        writer: PdfWriter,
        field_values: dict[str, str],
    ) -> None:
        """Fallback form fill that skips appearance-stream generation."""
        writer.set_need_appearances_writer(True)
        radio_field_values: dict[str, str] = {}
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            if not annotations:
                continue

            for annotation_ref in annotations:
                annotation = (
                    annotation_ref.get_object()
                    if hasattr(annotation_ref, "get_object")
                    else annotation_ref
                )
                if annotation.get("/Subtype", "") != "/Widget":
                    continue

                if "/FT" in annotation and "/T" in annotation:
                    parent_annotation = annotation
                else:
                    parent_ref = annotation.get("/Parent")
                    parent_annotation = (
                        parent_ref.get_object()
                        if parent_ref and hasattr(parent_ref, "get_object")
                        else (parent_ref or annotation)
                    )

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                if qualified_name in field_values:
                    matched_field_name = qualified_name
                elif annotation_name in field_values:
                    matched_field_name = annotation_name
                elif parent_name in field_values:
                    matched_field_name = parent_name
                if matched_field_name is None:
                    continue

                value = field_values[matched_field_name]
                field_type = parent_annotation.get("/FT", annotation.get("/FT"))
                if field_type == "/Btn":
                    if get_field_type(parent_annotation) == "radiobuttongroup":
                        text_value = TextStringObject(value)
                        parent_annotation[NameObject("/V")] = text_value
                        annotation[NameObject("/V")] = text_value
                        radio_field_values[matched_field_name] = value
                    else:
                        button_value = NameObject(
                            value if value.startswith("/") else (f"/{value}" if value else "/Off")
                        )
                        parent_annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/AS")] = button_value
                else:
                    text_value = TextStringObject(value)
                    parent_annotation[NameObject("/V")] = text_value
                    annotation[NameObject("/V")] = text_value

        if radio_field_values:
            self._sync_radio_button_states(writer, radio_field_values)

        # Build field-type lookup in one pass to avoid O(n²) scans
        field_type_map: dict[str, str] = {}
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")
                ftype = get_field_type(parent_annotation)
                for name in (qualified_name, annotation_name, parent_name):
                    if name is not None:
                        field_type_map[name] = ftype

        listbox_field_values = {
            field_name: value
            for field_name, value in field_values.items()
            if field_type_map.get(field_name) == "listbox"
        }
        if listbox_field_values:
            self._sync_listbox_selection_indexes(writer, listbox_field_values)

    def get_field_by_name_from_writer(
        self,
        writer: PdfWriter,
        field_name: str,
    ) -> dict[str, Any] | None:
        """Find a field annotation by name in writer pages."""
        for page in writer.pages:
            annotations = page.get("/Annots", [])
            for annotation_ref in annotations:
                annotation, parent_annotation = self._get_widget_annotation(annotation_ref)
                if annotation.get("/Subtype", "") != "/Widget":
                    continue
                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")
                if field_name in (qualified_name, annotation_name, parent_name):
                    return parent_annotation
        return None

    def fill(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        reader: PdfReader | None = None,
    ) -> Path:
        """Fill a PDF form with data.

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill.
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.
            reader: Optional pre-constructed PdfReader to avoid re-parsing.

        Returns:
            Path to the filled PDF.
        """
        from privacyforms_pdf.extractor import PdfReader, PdfWriter

        pdf_path = Path(pdf_path)

        own_reader = reader is None
        if own_reader:
            reader = PdfReader(str(pdf_path))
        assert reader is not None
        fields = reader.get_fields() or {}
        writer = PdfWriter()
        writer.append(reader)

        field_values: dict[str, str] = {}
        radio_field_values: dict[str, str] = {}
        listbox_field_values: dict[str, str] = {}
        for field_name, value in form_data.items():
            if value is None:
                continue
            str_value = ("/Yes" if value else "/Off") if isinstance(value, bool) else str(value)
            field_values[field_name] = str_value
            field_type = get_field_type(fields.get(field_name, {}))
            if field_type == "radiobuttongroup":
                radio_field_values[field_name] = str_value
            elif field_type == "listbox":
                listbox_field_values[field_name] = str_value

        if field_values:
            try:
                for page in writer.pages:
                    writer.update_page_form_field_values(
                        page,
                        field_values,
                    )
            except AttributeError as exc:
                if "'int' object has no attribute 'encode'" not in str(exc):
                    raise
                self._fill_form_fields_without_appearance(writer, field_values)
            if radio_field_values:
                self._sync_radio_button_states(writer, radio_field_values)
            if listbox_field_values:
                self._sync_listbox_selection_indexes(writer, listbox_field_values)

        output_file = Path(output_path) if output_path else pdf_path

        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=output_file.parent,
            suffix=output_file.suffix,
        ) as tmp:
            writer.write(tmp)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp.name, output_file)

        if own_reader:
            reader.close()

        return output_file
