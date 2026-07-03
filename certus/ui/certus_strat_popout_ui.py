from __future__ import annotations
from certus.ui.certus_strat_common import *

class PopOutWindow(CertusWindowSpyMixin, QMainWindow):
    closed_signal = pyqtSignal()

    def closeEvent(self, event) -> None:
        self.closed_signal.emit()
        self.takeCentralWidget()
        super().closeEvent(event)

    def __init__(self, widget_to_host, parent=None, title="Detached Window") -> None:

        super().__init__(None)
        self._parent = parent
        logging.getLogger("CERTUS").debug(
            "[STRAT-UI] PopOutWindow created id=%s parent=%s title='%s'",
            id(self), id(parent) if parent else None, title
        )

        set_certus_window_icon(self)

        self.setWindowTitle(title)

        self.setCentralWidget(widget_to_host)

        self.resize(600, 600)

        self.setStyleSheet(f"QMainWindow {{ background-color: {CertusTheme.SURFACE}; }} QWidget {{ font-size: 10pt; }}")

