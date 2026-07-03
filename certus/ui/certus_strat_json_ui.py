from __future__ import annotations
from certus.ui.certus_strat_common import *

class JsonViewerWindow(CertusWindowSpyMixin, QMainWindow):

    def __init__(self, parent, title: str, data: Any) -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] JsonViewerWindow created id=%s parent=%s",
            id(self), id(parent) if parent else None
        )

        set_certus_window_icon(self)

        self.setWindowTitle(f"Viewer: {title}")

        self.setGeometry(300, 300, 300, 750)

        main_widget = QWidget()

        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)

        header_widget = QWidget()

        header_widget.setStyleSheet(
            f"background-color: {CertusTheme.BACKGROUND}; border-bottom: 1px solid {CertusTheme.BORDER};"
        )

        header_layout = QHBoxLayout(header_widget)

        header_layout.setContentsMargins(10, 5, 10, 5)

        svg_path = get_resource_path("certus.svg")

        if Path(svg_path).exists() and QSvgWidget:
            mini_logo = QSvgWidget(svg_path)

            mini_logo.setFixedSize(180, 40)

            header_layout.addWidget(mini_logo)

        else:
            lbl = QLabel("CERTUS")

            lbl.setStyleSheet(f"color: {CertusTheme.PRIMARY}; font-weight: bold; font-size: 16px;")

            header_layout.addWidget(lbl)

        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        self.text_edit = QTextEdit()

        self.text_edit.setReadOnly(True)

        self.text_edit.setStyleSheet(
            f""" QTextEdit {{ background-color: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_MAIN}; font-family: {CertusTheme.FONT_FAMILY}; font-size: 10pt; border: none; padding: 10px; }} """
        )

        try:
            pretty_json = json.dumps(data, indent=4, ensure_ascii=False, default=numpy_encoder)

            self.text_edit.setText(pretty_json)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.text_edit.setText(f"Error parsing JSON data: {e}")

        main_layout.addWidget(self.text_edit)

