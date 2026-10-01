"""Configuration persistence of a CERTUS window: the QSettings of its tables and the save / load of its configuration file (moved out of certus_base_app.py, S5.3)."""

import logging
from pathlib import Path
from typing import Any
from pydantic import ValidationError
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFileDialog
import certus.ui.certus_io_ui as certus_io_ui

from certus.utils.certus_dto import IndexSplineConfigDTO
from certus.ui.certus_ui_utils import safe_ui_action
from certus.utils.certus_qsettings import certus_settings
from certus.utils.certus_atomic_io import atomic_open


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

    def _pre_save_smart_cleanup(self) -> None:
        """Override in subclass for pre-save cleanup (e.g. layer pruning in DESIGN)."""

        pass

    def _post_save_config(self, filename: str) -> None:
        """Override in subclass for post-save UI side-effects (status bar, popup, ...)."""

        pass

    def _post_load_config(self, filename: str, config: dict[str, Any]) -> None:
        """Override in subclass for post-load UI side-effects (status bar, popup, ...)."""

        pass

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
    def load_config(self, filename: str | None = None) -> None:
        """Load configuration from JSON file."""

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

                self._apply_config(config)

                if self.logger:
                    self.logger.info(f"Configuration loaded: {filename}")

                self._record_recent_config(filename)

                self._post_load_config(filename, config)

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
