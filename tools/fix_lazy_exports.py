from pathlib import Path

ui_file = Path('certus/ui/certus_ui.py')
source = ui_file.read_text(encoding='utf-8')

lazy_reexports = '''
_LAZY_REEXPORTS: dict[str, tuple[str, str]] = {
    "get_certus_last_dir": ("certus.ui.certus_io_ui", "get_certus_last_dir"),
    "set_certus_last_dir": ("certus.ui.certus_io_ui", "set_certus_last_dir"),
    "certus_get_open_file_name": ("certus.ui.certus_io_ui", "certus_get_open_file_name"),
    "certus_get_save_file_name": ("certus.ui.certus_io_ui", "certus_get_save_file_name"),
    "certus_confirm_yes_no": ("certus.ui.certus_io_ui", "certus_confirm_yes_no"),
    "open_data_file_and_read": ("certus.ui.certus_io_ui", "open_data_file_and_read"),
    "open_file_explorer": ("certus.ui.certus_io_ui", "open_file_explorer"),
    "DATA_FILE_FILTER": ("certus.ui.certus_io_ui", "DATA_FILE_FILTER"),
    "DATA_FILES_FILTER_EXTENDED": ("certus.ui.certus_io_ui", "DATA_FILES_FILTER_EXTENDED"),
    "CERTUS_UI_STRINGS": ("certus.ui.certus_io_ui", "CERTUS_UI_STRINGS"),

    "get_plot_style_config": ("certus.ui.certus_plot", "get_plot_style_config"),
    "apply_certus_plot_style": ("certus.ui.certus_plot", "apply_certus_plot_style"),
    "apply_theme_to_plots": ("certus.ui.certus_plot", "apply_theme_to_plots"),
    "iter_plot_data_series": ("certus.utils.certus_export", "iter_plot_data_series"),
    "build_wide_dataframe_for_export": ("certus.utils.certus_export", "build_wide_dataframe_for_export"),
    "plot_dataframe_from_widget": ("certus.utils.certus_export", "plot_dataframe_from_widget"),
    "copy_plot_to_clipboard_excel": ("certus.utils.certus_export", "copy_plot_to_clipboard_excel"),
    "attach_excel_clipboard_context_menu": ("certus.utils.certus_export", "attach_excel_clipboard_context_menu"),
}

def __getattr__(name: str):
'''

source = source.replace('def __getattr__(name: str):', lazy_reexports)
ui_file.write_text(source, encoding='utf-8')
print("Fixed lazy exports")
