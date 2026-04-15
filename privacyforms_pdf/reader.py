"""PDF form reading and extraction logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from privacyforms_pdf.models import FieldGeometry, PDFField, PDFFormData
from privacyforms_pdf.utils import cluster_y_positions

if TYPE_CHECKING:
    from pypdf import PdfReader
    from pypdf.generic import ArrayObject


class FormReader:
    """Reads and extracts form data from PDF files."""

    _DEFAULT_ROW_GAP_THRESHOLD = 15.0

    def __init__(self, extract_geometry: bool = True) -> None:
        """Initialize the reader.

        Args:
            extract_geometry: Whether to extract field geometry information.
        """
        self._extract_geometry = extract_geometry

    @staticmethod
    def get_field_type(field: dict[str, Any]) -> str:
        """Determine field type from pypdf field data.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            Field type string.
        """
        ft = field.get("/FT")
        if ft is None:
            ft = field.get("/Type")

        if ft == "/Tx":
            if "/AA" in field or "/DV" in field:
                return "datefield"
            return "textfield"
        elif ft == "/Btn":
            if "/Opt" in field:
                return "radiobuttongroup"
            return "checkbox"
        elif ft == "/Ch":
            ff = field.get("/Ff", 0)
            if isinstance(ff, int) and ff & 0x40000:
                return "combobox"
            return "listbox"
        elif ft == "/Sig":
            return "signature"

        return "textfield"

    @staticmethod
    def get_field_value(field: dict[str, Any]) -> str | bool:
        """Extract value from pypdf field data.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            Field value (string or boolean for checkboxes).
        """
        value = field.get("/V")

        if value is None:
            return ""

        if isinstance(value, str):
            if value.lower() in ("/yes", "yes", "/on", "on", "1"):
                return True
            elif value.lower() in ("/off", "off", "no", "0"):
                return False
            return value

        if hasattr(value, "name"):
            name = value.name
            if name.lower() in ("/yes", "yes", "/on", "on", "1"):
                return True
            elif name.lower() in ("/off", "off", "no", "0"):
                return False
            return str(name)

        return str(value)

    @staticmethod
    def get_field_options(field: dict[str, Any]) -> list[str]:
        """Extract options for choice/radio fields.

        Args:
            field: Field dictionary from pypdf.

        Returns:
            List of option strings.
        """
        options = field.get("/Opt", [])
        if options:
            result = []
            for opt in options:
                if isinstance(opt, list) and len(opt) >= 2:
                    result.append(str(opt[1]))
                elif isinstance(opt, list) and len(opt) == 1:
                    result.append(str(opt[0]))
                else:
                    result.append(str(opt))
            return result

        kids = field.get("/Kids", [])
        if kids:
            opt_list = []
            for kid in kids:
                kid_obj = kid.get_object() if hasattr(kid, "get_object") else kid
                if kid_obj and "/AP" in kid_obj:
                    ap = kid_obj["/AP"]
                    if "/N" in ap:
                        names = list(ap["/N"].keys())
                        opt_list.extend([str(n) for n in names if str(n).lower() != "/off"])
            return list(dict.fromkeys(opt_list))

        return []

    def extract_widgets_info(
        self, reader: PdfReader
    ) -> dict[str, tuple[list[int], FieldGeometry | None]]:
        """Scan all pages once to find widget pages and geometry.

        Args:
            reader: PdfReader instance.

        Returns:
            Dictionary mapping field names to (pages_list, geometry_object).
        """
        info: dict[str, tuple[list[int], FieldGeometry | None]] = {}

        for page_num, page in enumerate(reader.pages, start=1):
            if "/Annots" not in page:
                continue

            annots = cast("ArrayObject", page["/Annots"])
            for annot_ref in annots:
                try:
                    annot = (
                        annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
                    )

                    if annot.get("/Subtype") != "/Widget":
                        continue

                    t_value = annot.get("/T")
                    if not t_value:
                        continue

                    field_name = (
                        str(t_value)
                        if isinstance(t_value, str)
                        else str(getattr(t_value, "name", t_value))
                    )

                    geometry = None
                    rect = annot.get("/Rect")
                    if rect:
                        x0, y0, x1, y1 = [float(coord) for coord in rect]
                        geometry = FieldGeometry(
                            page=page_num,
                            rect=(x0, y0, x1, y1),
                        )

                    if field_name not in info:
                        info[field_name] = ([page_num], geometry)
                    else:
                        pages, existing_geom = info[field_name]
                        if page_num not in pages:
                            pages.append(page_num)
                        if existing_geom is None:
                            info[field_name] = (pages, geometry)

                except (AttributeError, KeyError, TypeError, ValueError):
                    logger = logging.getLogger(__name__)
                    logger.debug(
                        "Skipping malformed widget annotation on page %s",
                        page_num,
                        exc_info=True,
                    )

        return info

    def compute_and_set_row_clusters(self, fields: list[PDFField]) -> None:
        """Compute row clusters and set row_y on each field's geometry."""
        y_positions: list[float] = []
        for field in fields:
            if field.geometry:
                y_positions.append(field.geometry.y)

        if not y_positions:
            return

        y_clusters = cluster_y_positions(y_positions, self._DEFAULT_ROW_GAP_THRESHOLD)

        for field in fields:
            if field.geometry:
                cluster_y = y_clusters.get(field.geometry.y, field.geometry.y)
                field.geometry.set_row_y(cluster_y)

    def sort_fields(self, fields: list[PDFField]) -> list[PDFField]:
        """Sort fields by page number and position."""

        def sort_key(field: PDFField) -> tuple[int, float, float]:
            page = field.pages[0] if field.pages else 1
            if field.geometry:
                return (page, -field.geometry.row_y, field.geometry.x)
            return (page, 0.0, 0.0)

        return sorted(fields, key=sort_key)

    def build_raw_data_structure(self, fields: list[PDFField], source: str) -> dict[str, Any]:
        """Build raw data structure for export."""
        raw_data: dict[str, Any] = {
            "header": {"source": source, "version": "pypdf"},
            "forms": [
                {
                    "textfield": [],
                    "datefield": [],
                    "checkbox": [],
                    "radiobuttongroup": [],
                    "combobox": [],
                    "listbox": [],
                    "signature": [],
                }
            ],
        }

        for field in fields:
            field_entry: dict[str, Any] = {
                "pages": field.pages,
                "id": field.id,
                "name": field.name,
                "value": field.value,
                "locked": field.locked,
            }

            if field.field_type == "datefield" and field.format:
                field_entry["format"] = field.format

            if field.options and field.field_type in (
                "radiobuttongroup",
                "combobox",
                "listbox",
            ):
                field_entry["options"] = field.options

            if field.field_type in raw_data["forms"][0]:
                raw_data["forms"][0][field.field_type].append(field_entry)
            else:
                raw_data["forms"][0]["textfield"].append(field_entry)

        return raw_data

    def read(self, pdf_path: Any) -> PDFFormData:
        """Extract form data from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            PDFFormData containing all form information.
        """
        from pathlib import Path

        from privacyforms_pdf.extractor import PdfReader

        pdf_path = Path(pdf_path)

        reader = PdfReader(str(pdf_path))

        fields = reader.get_fields()
        if not fields:
            from privacyforms_pdf.models import PDFFormNotFoundError

            raise PDFFormNotFoundError(f"PDF does not contain a form: {pdf_path}")

        widget_info = self.extract_widgets_info(reader)

        pdf_fields: list[PDFField] = []
        raw_fields_data: dict[str, Any] = {}

        for field_counter, (field_name, field_data) in enumerate(fields.items(), start=1):
            raw_fields_data[field_name] = field_data

            field_type = self.get_field_type(field_data)
            value = self.get_field_value(field_data)
            info = widget_info.get(field_name, ([], None))
            pages = info[0] if info[0] else [1]
            geometry = info[1] if self._extract_geometry else None
            options = self.get_field_options(field_data)

            pdf_field = PDFField(
                name=field_name,
                id=str(field_counter),
                type=field_type,
                value=value,
                pages=pages,
                locked=False,
                geometry=geometry,
                format=None,
                options=options,
            )
            pdf_fields.append(pdf_field)

        self.compute_and_set_row_clusters(pdf_fields)
        pdf_fields = self.sort_fields(pdf_fields)
        raw_data = self.build_raw_data_structure(pdf_fields, str(pdf_path))

        if hasattr(reader, "pdf_header"):
            pdf_version = reader.pdf_header.replace("%PDF-", "")
        else:
            pdf_version = "unknown"

        return PDFFormData(
            source=pdf_path,
            pdf_version=pdf_version,
            has_form=len(pdf_fields) > 0,
            fields=pdf_fields,
            raw_data=raw_data,
        )
