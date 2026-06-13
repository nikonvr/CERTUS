import logging
import os
import sys
from pathlib import Path
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.utils.certus_data import read_data_file_robust

DATA_FILE_FILTER = "Data (*.csv *.txt *.xlsx)"
DATA_FILES_FILTER_EXTENDED = "Data Files (*.csv *.txt *.xlsx *.xls);;All Files (*)"
CERTUS_SETTINGS_ORG = "CERTUS"
CERTUS_SETTINGS_APP = "Common"
CERTUS_LAST_DIR_KEY = "last_dir"

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

def get_certus_last_dir() -> str:
    settings = QSettings(CERTUS_SETTINGS_ORG, CERTUS_SETTINGS_APP)
    return str(settings.value(CERTUS_LAST_DIR_KEY, "") or "")

def set_certus_last_dir(file_or_dir_path: str) -> None:
    if not file_or_dir_path:
        return
    path = Path(file_or_dir_path).resolve()
    dirpath = path if path.is_dir() else path.parent
    if str(dirpath) and dirpath.is_dir():
        settings = QSettings(CERTUS_SETTINGS_ORG, CERTUS_SETTINGS_APP)
        settings.setValue(CERTUS_LAST_DIR_KEY, str(dirpath))

def certus_get_open_file_name(
    parent,
    title: str,
    file_filter: str,
    directory: str | None = None,
) -> str:
    initial = directory if directory is not None else get_certus_last_dir()
    path, _ = QFileDialog.getOpenFileName(parent, title, initial, file_filter)
    if path:
        set_certus_last_dir(path)
    return path

def certus_get_save_file_name(
    parent,
    title: str,
    file_filter: str,
    directory: str | None = None,
) -> str:
    initial = directory if directory is not None else get_certus_last_dir()
    path, _ = QFileDialog.getSaveFileName(parent, title, initial, file_filter)
    if path:
        set_certus_last_dir(path)
    return path

def certus_confirm_yes_no(
    parent,
    title: str,
    text: str,
    *,
    default_no: bool = True,
) -> bool:
    default_btn = QMessageBox.StandardButton.No if default_no else QMessageBox.StandardButton.Yes
    reply = QMessageBox.question(
        parent,
        title,
        text,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default_btn,
    )
    return reply == QMessageBox.StandardButton.Yes

def open_data_file_and_read(
    parent=None,
    title="Open",
    file_filter=None,
    initial_dir="",
    last_dir_settings_key=None,
    **read_kwargs,
) -> tuple:
    if file_filter is None:
        file_filter = DATA_FILE_FILTER
    if last_dir_settings_key is not None:
        org, app = last_dir_settings_key
        settings = QSettings(org, app)
        initial_dir = initial_dir or settings.value("last_dir", "")
    if not initial_dir:
        initial_dir = get_certus_last_dir()
    filepath, _ = QFileDialog.getOpenFileName(parent, title, initial_dir, file_filter)
    if not filepath:
        return None, None
    set_certus_last_dir(filepath)
    if last_dir_settings_key is not None:
        org, app = last_dir_settings_key
        settings = QSettings(org, app)
        settings.setValue("last_dir", str(Path(filepath).parent))
    df = read_data_file_robust(filepath, **read_kwargs)
    return filepath, df

def open_file_explorer(path: str) -> None:
    try:
        resolved_path = Path(path).resolve()
        if not resolved_path.exists():
            logging.warning(f"Path does not exist: {path}")
            return
        path_str = str(resolved_path)
        if sys.platform == "win32":
            try:
                if resolved_path.is_dir():
                    os.startfile(path_str)
                else:
                    import subprocess
                    subprocess.Popen(
                        ["explorer", "/select,", path_str],
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open Windows explorer: {e}")
                raise
        elif sys.platform == "darwin":
            try:
                import subprocess
                subprocess.Popen(
                    ["open", "-R", path_str],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open macOS finder: {e}")
                raise
        else:  # linux
            try:
                import subprocess
                subprocess.Popen(
                    ["xdg-open", str(resolved_path.parent)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.SubprocessError) as e:
                logging.error(f"Failed to open Linux file manager: {e}")
                raise
    except NUMERICAL_FAULT_EXCEPTIONS as e:
        logging.warning(f"Error opening file explorer for {path}: {e}")
