"""CLI commands package for privacyforms-pdf."""

from __future__ import annotations

from .pdf_check import check_command
from .pdf_encrypt import encrypt_command
from .pdf_extract import extract_command
from .pdf_fill_form import fill_form_command
from .pdf_get_value import get_value_command
from .pdf_info import info_command
from .pdf_list_fields import list_fields_command
from .pdf_list_permissions import list_permissions_command
from .pdf_set_permissions import set_permissions_command
from .utils import create_extractor

__all__ = [
    "check_command",
    "create_extractor",
    "encrypt_command",
    "extract_command",
    "fill_form_command",
    "get_value_command",
    "info_command",
    "list_fields_command",
    "list_permissions_command",
    "set_permissions_command",
]
