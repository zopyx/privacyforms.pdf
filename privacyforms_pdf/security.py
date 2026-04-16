"""PDF security operations using pdfcpu backend."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from privacyforms_pdf.models import PDFFormError

# Permission bit positions (PDF spec uses bits 3-12)
PERMISSION_BITS = {
    "print": 3,  # Bit 3: Print (rev2), print quality (rev>=3)
    "modify": 4,  # Bit 4: Modify other than controlled by bits 6,9,11
    "extract": 5,  # Bit 5: Extract (rev2), extract other than bit 10 (rev>=3)
    "annotations": 6,  # Bit 6: Add or modify annotations
    "fill_forms": 9,  # Bit 9: Fill in form fields (rev>=3)
    "extract_accessibility": 10,  # Bit 10: Extract (rev>=3)
    "assemble": 11,  # Bit 11: Modify/assemble (rev>=3)
    "print_high": 12,  # Bit 12: Print high-level (rev>=3)
}

# Permission bit descriptions for high-level output
PERMISSION_DESCRIPTIONS = {
    3: ("print", "Print document"),
    4: ("modify", "Modify document (except annotations/form fields)"),
    5: ("extract", "Extract text and graphics"),
    6: ("annotations", "Add or modify annotations"),
    9: ("fill_forms", "Fill in form fields"),
    10: ("extract_accessibility", "Extract for accessibility"),
    11: ("assemble", "Assemble document (insert, rotate, delete pages)"),
    12: ("print_high", "Print high-quality / full resolution"),
}


def build_permission_bits(
    print_perm: bool = False,
    modify: bool = False,
    extract: bool = False,
    annotations: bool = False,
    fill_forms: bool = False,
    extract_accessibility: bool = False,
    assemble: bool = False,
    print_high: bool = False,
) -> str:
    """Build a 12-bit permission string from individual flags.

    Args:
        print_perm: Allow printing
        modify: Allow modification (except annotations/form fields)
        extract: Allow text/graphics extraction
        annotations: Allow adding/modifying annotations
        fill_forms: Allow filling form fields
        extract_accessibility: Allow extraction for accessibility
        assemble: Allow document assembly (insert, rotate, delete pages)
        print_high: Allow high-quality printing

    Returns:
        12-character binary string of permission bits.
    """
    bits = ["0"] * 12

    if print_perm:
        bits[2] = "1"  # Bit 3
    if modify:
        bits[3] = "1"  # Bit 4
    if extract:
        bits[4] = "1"  # Bit 5
    if annotations:
        bits[5] = "1"  # Bit 6
    if fill_forms:
        bits[8] = "1"  # Bit 9
    if extract_accessibility:
        bits[9] = "1"  # Bit 10
    if assemble:
        bits[10] = "1"  # Bit 11
    if print_high:
        bits[11] = "1"  # Bit 12

    return "".join(bits)


def parse_permission_bits(output: str) -> dict[str, Any]:
    """Parse pdfcpu permission list output into a structured dict.

    Args:
        output: Raw output from pdfcpu permissions list command.

    Returns:
        Dictionary with permission bits info.
    """
    result: dict[str, Any] = {
        "raw_bits": "",
        "hex_value": "",
        "permissions": {},
        "is_encrypted": False,
    }

    lines = output.strip().split("\n")

    for line in lines:
        line = line.strip()

        if "permission bits:" in line.lower():
            result["is_encrypted"] = True
            match = re.search(
                r"permission bits:\s*([01]+)\s*\(x([0-9a-fA-F]+)\)",
                line,
                re.IGNORECASE,
            )
            if match:
                result["raw_bits"] = match.group(1)
                result["hex_value"] = match.group(2)

        bit_match = re.search(r"bit\s+(\d+):\s*(true|false)\s*\(([^)]+)\)", line, re.IGNORECASE)
        if bit_match:
            bit_num = int(bit_match.group(1))
            value = bit_match.group(2).lower() == "true"
            description = bit_match.group(3)
            result["permissions"][bit_num] = {
                "value": value,
                "description": description,
            }

    return result


def format_permissions_highlevel(permissions: dict[str, Any]) -> str:
    """Format permissions in a high-level human-readable way.

    Args:
        permissions: Dictionary from parse_permission_bits.

    Returns:
        Formatted string for display.
    """
    lines: list[str] = []

    lines.append("PDF Permissions")
    lines.append("=" * 50)

    if not permissions["is_encrypted"]:
        lines.append("Document is not encrypted - all permissions granted")
        return "\n".join(lines)

    lines.append(f"Raw permission bits: {permissions['raw_bits']} (0x{permissions['hex_value']})")
    lines.append("")

    allowed: list[str] = []
    denied: list[str] = []

    for bit_num in sorted(PERMISSION_DESCRIPTIONS.keys()):
        if bit_num in permissions["permissions"]:
            perm_info = permissions["permissions"][bit_num]
            name, description = PERMISSION_DESCRIPTIONS[bit_num]
            if perm_info["value"]:
                allowed.append(f"  ✓ {name:20} - {description}")
            else:
                denied.append(f"  ✗ {name:20} - {description}")

    if allowed:
        lines.append("Allowed permissions:")
        lines.extend(allowed)
        lines.append("")

    if denied:
        lines.append("Denied permissions:")
        lines.extend(denied)
        lines.append("")

    total_relevant = len([b for b in permissions["permissions"] if b in PERMISSION_DESCRIPTIONS])
    allowed_count = len(allowed)
    denied_count = len(denied)

    lines.append(
        f"Summary: {allowed_count} allowed, {denied_count} denied "
        f"out of {total_relevant} relevant permission bits"
    )

    return "\n".join(lines)


class PDFSecurityManager:
    """Manages PDF encryption and permissions via pdfcpu.

    This class provides a programmatic API for the security features that
    are also available through the CLI.
    """

    def __init__(self, pdfcpu_path: str = "pdfcpu", timeout_seconds: float = 30.0) -> None:
        """Initialize the security manager.

        Args:
            pdfcpu_path: Path to the pdfcpu binary (default: "pdfcpu").
            timeout_seconds: Timeout for pdfcpu operations.
        """
        self._pdfcpu_path = pdfcpu_path
        self._timeout_seconds = timeout_seconds

    def _resolve_pdfcpu(self) -> str:
        """Resolve the pdfcpu binary path."""
        binary = shutil.which(self._pdfcpu_path)
        if binary is None:
            raise PDFFormError(
                f"pdfcpu binary not found: {self._pdfcpu_path}. "
                "Please install pdfcpu: https://pdfcpu.io/install"
            )
        return binary

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a pdfcpu command."""
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as e:
            raise PDFFormError(
                f"pdfcpu binary not found: {cmd[0]}. "
                "Please install pdfcpu or provide the correct path"
            ) from e

    def encrypt(
        self,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        *,
        owner_password: str,
        user_password: str | None = None,
        mode: str = "aes",
        key_length: str = "256",
        permissions: str = "none",
    ) -> Path:
        """Encrypt a PDF file.

        Args:
            pdf_path: Path to the PDF file to encrypt.
            output_path: Optional output path. If not provided, modifies input.
            owner_password: Owner password (mandatory).
            user_password: Optional user password.
            mode: Encryption algorithm ("rc4" or "aes", default: "aes").
            key_length: Key length in bits ("40", "128", or "256", default: "256").
            permissions: Permission preset ("none" or "all", default: "none").

        Returns:
            Path to the encrypted PDF.

        Raises:
            PDFFormError: If pdfcpu is not found or encryption fails.
        """
        pdf_path = Path(pdf_path)
        pdfcpu_binary = self._resolve_pdfcpu()

        cmd = [
            pdfcpu_binary,
            "encrypt",
            "-mode",
            mode.lower(),
            "-key",
            key_length,
            "-perm",
            permissions.lower(),
            "-opw",
            owner_password,
        ]

        if user_password:
            cmd.extend(["-upw", user_password])

        cmd.append(str(pdf_path))
        if output_path:
            cmd.append(str(output_path))

        result = self._run(cmd)
        if result.returncode != 0:
            raise PDFFormError(
                f"pdfcpu encryption failed: {result.stderr.strip() or result.stdout.strip()}"
            )

        return Path(output_path) if output_path else pdf_path

    def set_permissions(
        self,
        pdf_path: str | Path,
        *,
        owner_password: str,
        user_password: str | None = None,
        permissions_preset: str | None = None,
        print_perm: bool = False,
        modify: bool = False,
        extract: bool = False,
        annotations: bool = False,
        fill_forms: bool = False,
        extract_accessibility: bool = False,
        assemble: bool = False,
        print_high: bool = False,
        custom_bits: str | None = None,
    ) -> None:
        """Set permissions of an encrypted PDF file.

        Args:
            pdf_path: Path to the encrypted PDF file.
            owner_password: Owner password (required).
            user_password: Optional user password.
            permissions_preset: Preset ("none", "print", or "all").
            print_perm: Allow printing.
            modify: Allow modification.
            extract: Allow text/graphics extraction.
            annotations: Allow adding/modifying annotations.
            fill_forms: Allow filling form fields.
            extract_accessibility: Allow extraction for accessibility.
            assemble: Allow document assembly.
            print_high: Allow high-quality printing.
            custom_bits: Custom permission bits in hex or binary.

        Raises:
            PDFFormError: If custom_bits are invalid or pdfcpu operation fails.
        """
        pdf_path = Path(pdf_path)
        pdfcpu_binary = self._resolve_pdfcpu()

        cmd = [pdfcpu_binary, "permissions", "set"]

        if custom_bits:
            perm_value = custom_bits.strip().upper()
            if not all(c in "01" for c in perm_value) and not all(
                c in "0123456789ABCDEF" for c in perm_value
            ):
                raise PDFFormError(
                    "Invalid --custom-bits value. Must be hex (e.g., 'F3C') "
                    "or binary (e.g., '111100111100')"
                )
        elif permissions_preset:
            perm_value = permissions_preset.lower()
        else:
            perm_value = build_permission_bits(
                print_perm=print_perm,
                modify=modify,
                extract=extract,
                annotations=annotations,
                fill_forms=fill_forms,
                extract_accessibility=extract_accessibility,
                assemble=assemble,
                print_high=print_high,
            )

        cmd.extend(["-perm", perm_value])

        if user_password:
            cmd.extend(["-upw", user_password])
        cmd.extend(["-opw", owner_password])
        cmd.append(str(pdf_path))

        result = self._run(cmd)
        stderr_lower = result.stderr.lower() if result.stderr else ""
        stdout_lower = result.stdout.lower() if result.stdout else ""

        if (
            "please provide the owner password" in stderr_lower
            or "please provide the owner password" in stdout_lower
        ):
            raise PDFFormError("Incorrect owner password")

        if "not encrypted" in stderr_lower or "not encrypted" in stdout_lower:
            raise PDFFormError("Document is not encrypted")

        if result.returncode != 0:
            raise PDFFormError(
                f"pdfcpu permissions set failed: {result.stderr.strip() or result.stdout.strip()}"
            )

    def list_permissions(
        self,
        pdf_path: str | Path,
        *,
        user_password: str | None = None,
        owner_password: str | None = None,
    ) -> dict[str, Any]:
        """List permissions of an encrypted PDF file.

        Args:
            pdf_path: Path to the PDF file.
            user_password: Optional user password.
            owner_password: Optional owner password.

        Returns:
            Structured dictionary with permission information.

        Raises:
            PDFFormError: If pdfcpu is not found or the operation fails.
        """
        pdf_path = Path(pdf_path)
        pdfcpu_binary = self._resolve_pdfcpu()

        cmd = [pdfcpu_binary, "permissions", "list"]

        if user_password:
            cmd.extend(["-upw", user_password])
        if owner_password:
            cmd.extend(["-opw", owner_password])

        cmd.append(str(pdf_path))

        result = self._run(cmd)

        stderr_lower = result.stderr.lower() if result.stderr else ""
        stdout_lower = result.stdout.lower() if result.stdout else ""

        if (
            "please provide the correct password" in stderr_lower
            or "please provide the correct password" in stdout_lower
        ):
            raise PDFFormError("This document requires a password")

        if result.returncode != 0:
            raise PDFFormError(
                f"pdfcpu permissions list failed: {result.stderr.strip() or result.stdout.strip()}"
            )

        return parse_permission_bits(result.stdout)
