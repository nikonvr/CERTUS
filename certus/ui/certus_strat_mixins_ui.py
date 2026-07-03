from __future__ import annotations
from certus.ui.certus_strat_common import *

class CertusWindowSpyMixin:
    def showEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.showEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        if hasattr(super(), "showEvent"):
            super().showEvent(event)

    def hideEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.hideEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        if hasattr(super(), "hideEvent"):
            super().hideEvent(event)

    def closeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.closeEvent() title='%s' id=%s geometry=%s visible=%s",
            self.__class__.__name__, self.windowTitle(), id(self), self.geometry(), self.isVisible()
        )
        if hasattr(super(), "closeEvent"):
            super().closeEvent(event)

    def moveEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.moveEvent() title='%s' id=%s old_pos=%s new_pos=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.oldPos(), event.pos()
        )
        if hasattr(super(), "moveEvent"):
            super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.resizeEvent() title='%s' id=%s old_size=%s new_size=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.oldSize(), event.size()
        )
        if hasattr(super(), "resizeEvent"):
            super().resizeEvent(event)

    def changeEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.changeEvent() title='%s' id=%s event_type=%s state=%s active=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.type(), self.windowState(), self.isActiveWindow()
        )
        try:
            super().changeEvent(event)
        except AttributeError:
            pass

    def focusInEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.focusInEvent() title='%s' id=%s reason=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.reason()
        )
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        logging.getLogger("CERTUS").debug(
            "[SPY-WINDOW] %s.focusOutEvent() title='%s' id=%s reason=%s",
            self.__class__.__name__, self.windowTitle(), id(self), event.reason()
        )
        super().focusOutEvent(event)

