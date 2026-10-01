import pyqtgraph.exporters  # pylint: disable=unused-import
from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class WelcomeGuideWidget(QWidget):
    """

    Welcome/onboarding widget showing app name and optional steps.

    Args:

        app_name: Application name to display

        steps: List of step descriptions for the guide

    """

    def __init__(self, app_name: str = "CERTUS", steps: list[str] | None = None) -> None:

        super().__init__()

        steps = steps or []

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel(f"Welcome to {app_name}"))

