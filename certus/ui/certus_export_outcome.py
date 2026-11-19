"""What an export really wrote, said in the status bar, with a way to write the missing files again.

An export that reported "✓ Saved" while its manifest or HTML report had failed let the operator leave
believing the report existed (UX audit 2026-11-18, item 1). An `ExportOutcome` runs one writer per
report file, records which succeeded, names the folder, and keeps the writers of the missing files so
a "Retry missing" button can run those again, and only those.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable

from PyQt6.QtWidgets import QPushButton

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS

# A report the operator still has open in Excel raises PermissionError: exactly the case a retry is for.
WRITE_FAULTS = (OSError, *NUMERICAL_FAULT_EXCEPTIONS)

RETRY_BUTTON_TEXT = "Retry missing"


class ExportOutcome:
    """The report files of one export: which were written, and how to write the missing ones again."""

    def __init__(
        self,
        base_name: str,
        folder: str,
        writers: dict[str, Callable[[], bool]],
        logger: logging.Logger | None = None,
    ) -> None:
        self.base_name = base_name
        self.folder = folder
        self.writers = dict(writers)
        self.logger = logger or logging.getLogger("CERTUS")
        self.written = dict.fromkeys(self.writers, False)

    def run(self, kinds: list[str] | None = None) -> None:
        """Run the writers of ``kinds`` (all of them by default); a writer that raises counts as not written."""
        for kind in kinds if kinds is not None else list(self.writers):
            try:
                ok = bool(self.writers[kind]())
            except WRITE_FAULTS as exc:
                self.logger.error("Report file not written (%s): %s", kind, exc, exc_info=True)
                ok = False
            self.written[kind] = ok

    @property
    def done(self) -> list[str]:
        return [kind for kind, ok in self.written.items() if ok]

    @property
    def missing(self) -> list[str]:
        return [kind for kind, ok in self.written.items() if not ok]

    def retry_missing(self) -> None:
        self.run(self.missing)

    def status_text(self) -> str:
        where = f"{self.base_name} in {self.folder}"
        if not self.missing:
            return f"✓ Saved: {where}"
        listed = f"missing: {', '.join(self.missing)}; see log"
        if not self.done:
            return f"✗ Not saved: {where} ({listed})"
        return f"⚠ Partly saved: {where} (written: {', '.join(self.done)}; {listed})"

    def level(self) -> str:
        if not self.missing:
            return "done"
        return "error" if not self.done else "warning"


def show_export_outcome(window, outcome: ExportOutcome) -> None:
    """Write ``outcome`` in ``window.status_label``; offer "Retry missing" in the status bar while a file is missing."""
    label = window.status_label
    label.setText(outcome.status_text())
    if hasattr(label, "set_level"):
        label.set_level(outcome.level())
    label.setToolTip(f"Report folder: {outcome.folder}")
    if outcome.missing:
        outcome.logger.error(
            "Export incomplete: %s missing for %s in %s", ", ".join(outcome.missing), outcome.base_name, outcome.folder
        )

    button = getattr(window, "retry_export_btn", None)
    if button is None:
        status_bar = getattr(window, "status_bar", None)
        if status_bar is None:
            return
        button = QPushButton(RETRY_BUTTON_TEXT)
        button.setToolTip("Write again only the report files that failed, into the same folder.")
        button.clicked.connect(functools.partial(_retry, window))
        status_bar.addWidget(button)
        window.retry_export_btn = button
    window._export_outcome = outcome
    button.setVisible(bool(outcome.missing))


def _retry(window, _checked: bool = False) -> None:
    outcome = getattr(window, "_export_outcome", None)
    if outcome is None:
        return
    outcome.retry_missing()
    show_export_outcome(window, outcome)
    if hasattr(window, "_reports_exported"):
        window._reports_exported = not outcome.missing
