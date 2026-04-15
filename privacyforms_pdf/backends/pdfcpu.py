"""pdfcpu backend for form filling operations."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from privacyforms_pdf.models import PDFFormError


class PdfcpuBackend:
    """Backend for filling PDF forms using the external pdfcpu binary."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        """Initialize the backend.

        Args:
            timeout_seconds: Timeout for pdfcpu operations.
        """
        self._timeout_seconds = timeout_seconds

    def _run_command(self, cmd: list[str]) -> None:
        """Run a pdfcpu command and normalize execution failures."""
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"pdfcpu failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise PDFFormError(error_msg) from e
        except subprocess.TimeoutExpired as e:
            raise PDFFormError(f"pdfcpu timed out after {self._timeout_seconds} seconds") from e
        except FileNotFoundError as e:
            raise PDFFormError(f"pdfcpu binary not found: {cmd[0]}") from e

    def _export_form_data(self, pdf_path: Path, pdfcpu_binary: str) -> dict[str, Any]:
        """Export a PDF form using pdfcpu so its full field metadata is preserved."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_json:
            temp_json_path = Path(temp_json.name)

        try:
            self._run_command([pdfcpu_binary, "form", "export", str(pdf_path), str(temp_json_path)])

            with open(temp_json_path, encoding="utf-8") as f:
                return cast("dict[str, Any]", json.load(f))
        finally:
            if temp_json_path.exists():
                temp_json_path.unlink()

    @staticmethod
    def _build_field_index(
        pdfcpu_data: dict[str, Any],
    ) -> tuple[dict[str, tuple[str, dict[str, Any]]], dict[str, tuple[str, dict[str, Any]]]]:
        """Index exported pdfcpu fields by exact and terminal field name."""
        exact_matches: dict[str, tuple[str, dict[str, Any]]] = {}
        suffix_candidates: dict[str, list[tuple[str, dict[str, Any]]]] = {}

        for form in pdfcpu_data.get("forms", []):
            if not isinstance(form, dict):
                continue

            for field_type, entries in form.items():
                if not isinstance(entries, list):
                    continue

                for entry in entries:
                    if not isinstance(entry, dict):
                        continue

                    field_id = entry.get("id")
                    if field_id is not None:
                        exact_matches[str(field_id)] = (field_type, entry)

                    field_name = entry.get("name")
                    if field_name is None:
                        continue

                    field_name_str = str(field_name)
                    exact_matches[field_name_str] = (field_type, entry)
                    suffix_candidates.setdefault(field_name_str.rsplit(".", 1)[-1], []).append(
                        (field_type, entry)
                    )

        suffix_matches = {
            suffix: matches[0] for suffix, matches in suffix_candidates.items() if len(matches) == 1
        }

        return exact_matches, suffix_matches

    def _merge_form_data(
        self,
        pdfcpu_data: dict[str, Any],
        form_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge simple key:value form data into exported pdfcpu JSON."""
        exact_matches, suffix_matches = self._build_field_index(pdfcpu_data)

        for field_name, value in form_data.items():
            lookup_key = str(field_name)
            field_match = exact_matches.get(lookup_key) or suffix_matches.get(lookup_key)
            if field_match is None:
                continue

            field_type, field_entry = field_match

            if field_type == "checkbox":
                field_entry["value"] = bool(value)
                continue

            if field_type == "listbox":
                if isinstance(value, list):
                    field_entry.pop("value", None)
                    field_entry["values"] = [str(item) for item in value]
                else:
                    field_entry.pop("values", None)
                    field_entry["value"] = str(value)
                continue

            field_entry["value"] = str(value)

        return pdfcpu_data

    @staticmethod
    def _should_fallback(error_message: str) -> bool:
        """Return True for known pdfcpu form-compatibility failures."""
        normalized = error_message.lower()
        return "required entry=da missing" in normalized or "unexpected panic attack" in normalized

    def fill_form(
        self,
        pdf_path: str | Path,
        form_data: dict[str, Any],
        output_path: str | Path | None = None,
        *,
        pdfcpu_path: str = "pdfcpu",
    ) -> Path:
        """Fill a PDF form with data using pdfcpu.

        Args:
            pdf_path: Path to the PDF file containing the form.
            form_data: The form data to fill.
            output_path: Optional output path. If not provided, the input PDF
                        is modified in place.
            pdfcpu_path: Path to the pdfcpu binary (default: "pdfcpu").

        Returns:
            Path to the filled PDF.

        Raises:
            PDFFormError: If pdfcpu execution fails or is not found.
        """
        pdf_path = Path(pdf_path)
        output_file = Path(output_path) if output_path else pdf_path

        pdfcpu_binary = shutil.which(pdfcpu_path)
        if pdfcpu_binary is None:
            raise PDFFormError(
                f"pdfcpu binary not found: {pdfcpu_path}. "
                "Please install pdfcpu: https://pdfcpu.io/install"
            )

        pdfcpu_json_data = self._merge_form_data(
            self._export_form_data(pdf_path, pdfcpu_binary),
            form_data,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as temp_json:
            json.dump(pdfcpu_json_data, temp_json, indent=2)
            temp_json_path = Path(temp_json.name)

        try:
            cmd = [
                pdfcpu_binary,
                "form",
                "fill",
                str(pdf_path),
                str(temp_json_path),
                str(output_file),
            ]
            self._run_command(cmd)

            if not output_file.exists():
                raise PDFFormError(f"pdfcpu did not create output file: {output_file}")

            return output_file
        finally:
            if temp_json_path.exists():
                temp_json_path.unlink()


def is_pdfcpu_available(pdfcpu_path: str = "pdfcpu") -> bool:
    """Check if pdfcpu binary is available.

    Args:
        pdfcpu_path: Path to the pdfcpu binary (default: "pdfcpu").

    Returns:
        True if pdfcpu is available in the system PATH, False otherwise.
    """
    return shutil.which(pdfcpu_path) is not None


# Backwards compatibility aliases (deprecated, will be removed in a future version)
PDFCPUError = PDFFormError
PDFCPUNotFoundError = PDFFormError
PDFCPUExecutionError = PDFFormError
