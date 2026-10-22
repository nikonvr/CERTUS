"""The short labels and messages of the export and copy actions, shared by the UI and `certus.utils.certus_export`.

Plain data, no Qt: it lives below the UI so that `certus.utils` can read it without importing `certus.ui` (D26, upward
imports). `certus.ui.certus_io_ui` re-exports it under the same name.
"""

CERTUS_UI_STRINGS = {
    "export": "Export",
    "export_ok": "Saved file",
    "export_failed": "Export failed",
    "no_data": "No data to export.",
    "copy_logs": "Copy Logs",
    "logs_copied": "Logs copied to clipboard.",
    "copy_excel_tsv": "Copy data (Excel)",
    "copy_excel_ok": "Data copied to clipboard (TSV).",
    "copy_excel_failed": "No data to copy.",
    "copy_pub_tsv": "Copy data (Publication TSV)",
    "copy_pub_ok": "Publication TSV copied to clipboard.",
}
