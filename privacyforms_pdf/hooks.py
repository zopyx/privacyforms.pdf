"""Hook specifications for the privacyforms-pdf plugin system."""

from __future__ import annotations

import pluggy

hookspec = pluggy.HookspecMarker("privacyforms_pdf")
hookimpl = pluggy.HookimplMarker("privacyforms_pdf")


class PDFFormsCommandsSpec:
    """Hook specification for registering CLI commands."""

    @hookspec
    def register_commands(self) -> list[object]:
        """Return a list of click.Command instances to register."""
        raise NotImplementedError
