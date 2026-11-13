"""Configuration persistence of a CERTUS window: the QSettings of its tables and the save / load of its configuration file (moved out of certus_base_app.py, S5.3)."""

import logging
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import certus.ui.certus_io_ui as certus_io_ui
from certus.ui.certus_ui_utils import safe_ui_action
from certus.utils.certus_atomic_io import atomic_open
from certus.utils.certus_dto import IndexSplineConfigDTO
from certus.utils.certus_qsettings import certus_settings


class CertusAppConfigMixin:
    """Configuration persistence of a CERTUS window: the QSettings of its tables and the save / load of its configuration file (moved out of certus_base_app.py, S5.3)."""

    def _qs_key(self, suffix: str) -> str:
        return f"window/{self.APP_NAME}/{suffix}"

    def _iter_persistable_tables(self):
        """Yield ``(stable_name, table)`` for every table held as an attribute.

        The attribute name is the identifier: most CERTUS tables carry no
        objectName, but ``self.front_table`` keeps its name across launches,
        which ``findChildren`` ordering would not.
        """
        from PyQt6.QtWidgets import QTableView, QTableWidget

        seen: set[int] = set()
        holders = [self]
        ui = getattr(self, "ui", None)
        if ui is not None and ui is not self:
            holders.append(ui)
        for holder in holders:
            for attr, obj in list(vars(holder).items()):
                if attr.startswith("__") or not isinstance(obj, (QTableWidget, QTableView)):
                    continue
                if id(obj) in seen:
                    continue
                seen.add(id(obj))
                yield attr, obj

    def _qs_save_table_headers(self, qs: QSettings) -> None:
        for attr, table in self._iter_persistable_tables():
            try:
                header = table.horizontalHeader()
                if header is not None and header.count() > 0:
                    qs.setValue(self._qs_key(f"table/{attr}"), header.saveState())
            except RuntimeError, AttributeError:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _qs_restore_table_headers(self, qs: QSettings) -> None:
        for attr, table in self._iter_persistable_tables():
            state = qs.value(self._qs_key(f"table/{attr}"))
            if state is None:
                continue
            try:
                header = table.horizontalHeader()
                if header is not None and header.count() > 0:
                    header.restoreState(state)
            except RuntimeError, AttributeError:
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _qs_restore(self) -> None:
        qs = certus_settings("CERTUS", self.APP_NAME)
        geom = qs.value(self._qs_key("geometry"))
        if geom is not None:
            self.restoreGeometry(geom)
        state = qs.value(self._qs_key("windowState"))
        if state is not None:
            self.restoreState(state)
        splitter_state = qs.value(self._qs_key("mainSplitter"))
        if splitter_state is not None:
            sp = getattr(self, "main_split", None)
            if sp is not None and sp.restoreState(splitter_state):
                # Tells apply_default_layout() not to overwrite what the user set.
                self._layout_restored_from_settings = True
        bottom_state = qs.value(self._qs_key("bottomSplitter"))
        if bottom_state is not None:
            bsp = (
                getattr(self, "bottom_split", None)
                or getattr(self, "bottom_splitter", None)
                or getattr(getattr(self, "ui", None), "bottom_splitter", None)
            )
            if bsp is not None:
                bsp.restoreState(bottom_state)
        self._qs_restore_table_headers(qs)

    def _qs_save(self) -> None:
        qs = certus_settings("CERTUS", self.APP_NAME)
        qs.setValue(self._qs_key("geometry"), self.saveGeometry())
        qs.setValue(self._qs_key("windowState"), self.saveState())
        sp = getattr(self, "main_split", None)
        if sp is not None:
            qs.setValue(self._qs_key("mainSplitter"), sp.saveState())
        bsp = (
            getattr(self, "bottom_split", None)
            or getattr(self, "bottom_splitter", None)
            or getattr(getattr(self, "ui", None), "bottom_splitter", None)
        )
        if bsp is not None:
            qs.setValue(self._qs_key("bottomSplitter"), bsp.saveState())
        self._qs_save_table_headers(qs)

    def _get_config_file_filter(self) -> str:

        return "JSON Files (*.json);;All Files (*)"

    def _get_default_config_name(self) -> str:

        return f"{self.APP_NAME.lower()}_config.json"

    def _collect_config(self) -> dict[str, Any]:
        """

        Override in subclass to collect configuration from widgets.

        Returns a dict to be serialized to JSON.

        """

        return {}

    def _apply_config(self, config: dict[str, Any]) -> None:
        """

        Override in subclass to apply loaded configuration to widgets.

        """

        pass

    def _config_load_problems(self, config: dict[str, Any]) -> list[str]:
        """What the configuration names that this window does not offer; override in a subclass.

        A combo box asked for a text it does not offer keeps its previous choice, and the window would compute with
        that other material while the file names another (D88). `load_config` loads nothing when this is not empty.
        """
        return []

    def _pre_save_smart_cleanup(self) -> None:
        """Override in subclass for pre-save cleanup (e.g. layer pruning in DESIGN)."""

        pass

    def _post_save_config(self, filename: str) -> None:
        """Override in subclass for post-save UI side-effects (status bar, popup, ...)."""

        pass

    def _post_load_config(self, filename: str, config: dict[str, Any]) -> None:
        """Override in subclass for post-load UI side-effects (status bar, popup, ...)."""

        pass

    # ---- unsaved work: what the operator has on file, compared with what the window holds now ------------------------

    def _config_snapshot(self) -> str | None:
        """The configuration as text that can be compared, or None when this window has none to save."""
        import json

        try:
            config = self._collect_config()
        except Exception:
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)
            return None
        return json.dumps(config, sort_keys=True, default=str) if config else None

    def mark_config_saved(self) -> None:
        """Take the configuration as it is now for the one the operator has on file: a later close compares with it."""
        self._saved_config_snapshot = self._config_snapshot()

    def _mark_initial_config_saved(self) -> None:
        """Take the delayed initial snapshot only if no save or load established one already."""
        if getattr(self, "_saved_config_snapshot", None) is None:
            self.mark_config_saved()

    # -- Session kept on disk (U12 A, decision Q40) ------------------------------------------------------------------
    #: Every minute a window whose configuration changed writes it to its session file; a finished close erases it.
    SESSION_AUTOSAVE_MS = 60_000

    def _session_supported(self) -> bool:
        """A window resumes through its own `_apply_config`: the mixin's, which does nothing, is not a way back."""
        cls = type(self)
        return cls._apply_config is not CertusAppConfigMixin._apply_config and cls._collect_config is not CertusAppConfigMixin._collect_config

    def _session_name(self) -> str:
        return str(getattr(self, "APP_NAME", "") or type(self).__name__)

    def _session_start(self) -> None:
        """Offer the session a window left without closing, then keep the session of this one every minute."""
        from PyQt6.QtCore import QTimer

        from certus.ui.certus_session import clear_session, read_session

        if not self._session_supported():
            return
        name = self._session_name()
        record = read_session(name)
        # Under the offscreen platform nobody answers: no offer, and the session found is left where it is.
        if record is not None and os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
            if self._ask_to_resume_session(str(record.get("saved_at", ""))):
                self._apply_config(record["config"])  # left unsaved on purpose: the operator saves it where he wants
                logging.getLogger("CERTUS").info("Session of %s resumed (saved %s)", name, record.get("saved_at"))
            clear_session(name)
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._session_autosave)
        self._session_timer.start(self.SESSION_AUTOSAVE_MS)

    def _ask_to_resume_session(self, saved_at: str) -> bool:
        """A decision, so a dialog (decision Q33): resume the configuration the window held when it was cut?"""
        when = saved_at.replace("T", " at ") if saved_at else "a previous run"
        answer = QMessageBox.question(
            self,
            "Resume the previous session?",
            f"This window did not close normally. Its configuration of {when} was kept.\n\n"
            "Resume it? It opens unsaved: save it where you want. No computation is resumed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _session_autosave(self) -> None:
        from certus.ui.certus_session import clear_session, write_session

        name = self._session_name()
        try:
            if self.has_unsaved_config():
                write_session(name, self._collect_config())
            else:
                clear_session(name)
        except (OSError, TypeError, ValueError, RuntimeError):
            logging.getLogger("CERTUS").debug("Session of %s not written", name, exc_info=True)

    def _session_end(self) -> None:
        """A close that went to its end: nothing to resume."""
        from certus.ui.certus_session import clear_session

        timer = getattr(self, "_session_timer", None)
        if timer is not None:
            timer.stop()
        if self._session_supported():
            try:
                clear_session(self._session_name())
            except OSError:
                logging.getLogger("CERTUS").debug("Session of %s not erased", self._session_name(), exc_info=True)

    def has_unsaved_config(self) -> bool:
        """True when the configuration is not the one last saved, loaded or settled at the opening of the window."""
        saved = getattr(self, "_saved_config_snapshot", None)
        return saved is not None and self._config_snapshot() != saved

    def _ask_about_unsaved_config(self) -> str:
        """Ask what to do with a changed configuration: "save", "discard" or "cancel"."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Unsaved configuration")
        box.setText("The configuration has changed since it was last saved or loaded.")
        box.setInformativeText("Save it before closing?")
        save = box.addButton("Save…", QMessageBox.ButtonRole.AcceptRole)
        discard = box.addButton("Close without saving", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.setEscapeButton(cancel)
        box.exec()
        clicked = box.clickedButton()
        return "save" if clicked is save else "discard" if clicked is discard else "cancel"

    def confirm_close_unsaved(self, event) -> bool:
        """Ask before a close throws away a configuration changed since it was last saved or loaded.

        Returns True when the close may go on: nothing changed, a run is going (the close asks its own question,
        `confirm_close_during_run`), the operator chose to close without saving, or the configuration was saved.
        A window that collects no configuration has nothing to compare and is never asked.
        """
        if getattr(self, "running_worker_count", lambda: 0)() or not self.has_unsaved_config():
            return True
        answer = self._ask_about_unsaved_config()
        if answer == "discard":
            return True
        if answer == "save":
            self.save_config()
            if not self.has_unsaved_config():
                return True
        event.ignore()
        return False

    @safe_ui_action
    def save_config(self) -> None:
        """Save current configuration to JSON file."""

        import json

        default_path = str(Path(certus_io_ui.get_certus_last_dir() or ".") / self._get_default_config_name())

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration",
            default_path,
            self._get_config_file_filter(),
        )

        if filename:
            certus_io_ui.set_certus_last_dir(filename)

            try:
                self._pre_save_smart_cleanup()

                config = self._collect_config()

                with atomic_open(filename, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                if self.logger:
                    self.logger.info(f"Configuration saved: {filename}")

                self._record_recent_config(filename)

                self._post_save_config(filename)

                self.mark_config_saved()

            except Exception as e:
                from certus.utils.errors import ConfigurationCorruptionError

                msg = f"Failed to save configuration: {e}"
                if self.logger:
                    self.logger.error(msg)
                raise ConfigurationCorruptionError(
                    msg,
                    details=str(e),
                    suggestion="Please verify if the destination path is writable and disk space is sufficient.",
                ) from e

    @safe_ui_action
    def load_config(self, filename: str | None = None) -> bool:
        """Load configuration from JSON file.

        Returns True once the file is loaded, False when no file was chosen. An error is raised to
        ``safe_ui_action``, which shows it and returns None.
        """

        import json

        if not filename:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", certus_io_ui.get_certus_last_dir(), self._get_config_file_filter()
            )

        if filename:
            certus_io_ui.set_certus_last_dir(filename)

            try:
                with open(filename, encoding="utf-8") as f:
                    config = json.load(f)

                if not isinstance(config, dict):
                    raise ValueError("Configuration JSON must be an object/dictionary.")
                app_mod = str(getattr(self.__class__, "__module__", "")).upper()
                if "INDEX_SPLINE" in app_mod:
                    try:
                        validated = IndexSplineConfigDTO.model_validate(config)
                        config = validated.model_dump(mode="python", exclude_none=False)
                    except ValidationError as e:
                        msg = f"Invalid INDEX_SPLINE configuration: {e}"
                        if self.logger:
                            self.logger.error(msg)
                        from certus.utils.errors import ConfigurationCorruptionError

                        raise ConfigurationCorruptionError(
                            msg,
                            details=str(e),
                            suggestion="Ensure the configuration file matches the INDEX_SPLINE schema.",
                        ) from e

                problems = self._config_load_problems(config)
                if problems:
                    logging.getLogger("CERTUS").warning("Configuration refused (%s): %s", filename, "; ".join(problems))
                    QMessageBox.warning(
                        self,
                        "Configuration not loaded",
                        "This configuration names what this installation does not offer; nothing was loaded:\n\n"
                        + "\n".join(f"• {p}" for p in problems),
                    )
                    return False

                self._apply_config(config)

                if self.logger:
                    self.logger.info(f"Configuration loaded: {filename}")

                self._record_recent_config(filename)

                self._post_load_config(filename, config)

                self.mark_config_saved()

                return True

            except Exception as e:
                from certus.utils.errors import ConfigurationCorruptionError

                if isinstance(e, ConfigurationCorruptionError):
                    raise
                msg = f"Failed to load configuration: {e}"
                if self.logger:
                    self.logger.error(msg)
                raise ConfigurationCorruptionError(
                    msg,
                    details=str(e),
                    suggestion="Ensure the configuration file exists, is valid JSON, and has correct file permissions.",
                ) from e

        return False
