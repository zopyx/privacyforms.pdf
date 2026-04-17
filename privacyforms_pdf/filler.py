"""PDF form filling logic using pypdf."""

from __future__ import annotations

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
    from pypdf import PdfWriter


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
        """Return the non-Off appearance state for a widget, if any."""
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
        """Resolve the selected on-state name for a radio group."""
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
        """Update radio widget appearances to match the selected option."""
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
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
                if matched_field_name is None:
                    continue

                selected_state = self._resolve_radio_field_state(
                    parent_annotation,
                    field_values[matched_field_name],
                )
                widget_state = self._get_widget_on_state(annotation)
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
        """Update listbox values and selection indexes for viewer highlighting."""
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
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
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
        """Build a listbox appearance stream with highlighted selection."""
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

        font_name = "/F0"
        if "/Font" in resources and resources["/Font"]:
            fonts = cast("DictionaryObject", resources["/Font"])
            font_name = str(next(iter(fonts.keys())))

        lines: list[str] = [
            "q",
            "/Tx BMC",
            "q",
            f"1 1 {max(width - 2, 1):.3f} {max(height - 2, 1):.3f} re",
            "W",
            "n",
        ]
        if selected_index is not None:
            highlight_y = height - (selected_index + 1) * line_height
            lines.extend(
                [
                    "0.600006 0.756866 0.854904 rg",
                    f"1 {highlight_y:.3f} {max(width - 2, 1):.3f} {line_height:.3f} re",
                    "f",
                ]
            )

        lines.extend(
            [
                "BT",
                f"{font_name} {font_size:.3f} Tf",
            ]
        )
        for index, option in enumerate(options):
            lines.append("1 g" if index == selected_index else "0 g")
            text_y = height - ((index + 1) * line_height) + ((line_height - font_size) / 2)
            escaped = self._escape_pdf_text(str(option))
            lines.append(f"1 0 0 1 2 {text_y:.3f} Tm")
            lines.append(f"({escaped}) Tj")
        lines.extend(["ET", "Q", "EMC", "Q"])

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
                annotation = annotation_ref.get_object()
                if annotation.get("/Subtype", "") != "/Widget":
                    continue

                if "/FT" in annotation and "/T" in annotation:
                    parent_annotation = annotation
                else:
                    parent_ref = annotation.get("/Parent")
                    parent_annotation = parent_ref.get_object() if parent_ref else annotation

                qualified_name = writer._get_qualified_field_name(parent_annotation)
                annotation_name = annotation.get("/T")
                parent_name = parent_annotation.get("/T")

                matched_field_name = None
                for field_name in field_values:
                    if field_name in (qualified_name, annotation_name, parent_name):
                        matched_field_name = field_name
                        break
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
                        button_value = NameObject(value if value.startswith("/") else f"/{value}")
                        parent_annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/V")] = button_value
                        annotation[NameObject("/AS")] = button_value
                else:
                    text_value = TextStringObject(value)
                    parent_annotation[NameObject("/V")] = text_value
                    annotation[NameObject("/V")] = text_value

        if radio_field_values:
            self._sync_radio_button_states(writer, radio_field_values)

        listbox_field_values = {
            field_name: value
            for field_name, value in field_values.items()
            if get_field_type(self.get_field_by_name_from_writer(writer, field_name) or {})
            == "listbox"
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
    ) -> Path:
        """Fill a PDF form with data.

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill.
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.

        Returns:
            Path to the filled PDF.
        """
        from privacyforms_pdf.extractor import PdfReader, PdfWriter

        pdf_path = Path(pdf_path)

        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}
        writer = PdfWriter()
        writer.append(reader)

        field_values: dict[str, str] = {}
        radio_field_values: dict[str, str] = {}
        listbox_field_values: dict[str, str] = {}
        for field_name, value in form_data.items():
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
        with open(output_file, "wb") as f:
            writer.write(f)

        return output_file
