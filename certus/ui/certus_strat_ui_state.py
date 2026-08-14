from __future__ import annotations
from certus.ui.certus_strat_common import *
from certus.ui.certus_strat_json_ui import JsonViewerWindow

#: String values recognized as TRUE in a config file.
_CONFIG_TRUE = frozenset({"1", "true", "yes", "on", "oui", "vrai"})


def _config_flag(config: object, key: str, default: bool = False) -> bool:
    """Reads a boolean flag from the loaded configuration, without associated widget.

    The values of a STRAT JSON are sometimes booleans, sometimes strings
    ("1", "0", "true"). `_get_float_safe` is not suitable: it queries the
    widgets, and a flag without a widget would always take its default — so a
    setting present in the file would be SILENTLY ignored. This is the failure
    mode that cost two sessions on `trigger_tolerance`.
    """
    if not isinstance(config, dict):
        return default
    raw = config.get(key, None)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return float(raw) > 0.5
    return str(raw).strip().lower() in _CONFIG_TRUE


from certus.core.certus_strat_robustness import INDEX_CORRIDOR_DEFAULT  # noqa: E402
from certus_physics import PHOTOMETRIC_CURVATURE_AMP  # noqa: E402


def _config_float(config: object, key: str, default: float = 0.0) -> float:
    """Reads a float from the loaded configuration, without associated widget.

    Same reason as `_config_flag`: these settings have no field in the interface and
    are placed in the JSON. `_get_float_safe` queries the widgets and would therefore
    always return the default — a setting present in the file would be SILENTLY ignored.
    """
    if not isinstance(config, dict):
        return default
    raw = config.get(key, None)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _config_flag_default(config: object, key: str, default: bool) -> bool:
    """A boolean whose ABSENCE means the code default, never `False`.

    🔴 `_config_float` returns 0.0 for a missing key, so routing a flag through it would
    turn silence into "off". Since 2026-08-12 the defaults describe the real machine --
    slit bias on, Rate on, index corridor on, photometric curvature on -- so reading an
    absent key as "off" would quietly hand back the optimistic machine that does not
    exist. That is the failure mode this whole document is about.
    """
    if not isinstance(config, dict):
        return default
    raw = config.get(key, None)
    if raw is None or raw == "":
        return default
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(float(raw) > 0.5)


class CertusStratStateMixin:
    def _load_defaults(self) -> None:
        """Load default values for CERTUS-STRAT"""

        # Reset workflow state

        self.opti_results = None

        self.undo_stack.clear()

        # Reset materials database

        if hasattr(self, "materials_db"):
            self.materials_db.clear_cache()

        # Reset stack table

        if hasattr(self, "widgets") and "stack_table" in self.widgets:
            self.widgets["stack_table"].setRowCount(0)

        # Reset material selections

        if hasattr(self, "widgets"):
            default_materials = {"substrate_choice": "Custom", "nSub_custom": "1.73", "l0": "550.0"}

            for widget_name, default_value in default_materials.items():
                if widget_name in self.widgets:
                    if hasattr(self.widgets[widget_name], "setCurrentText"):
                        self.widgets[widget_name].setCurrentText(default_value)

                    elif hasattr(self.widgets[widget_name], "setText"):
                        self.widgets[widget_name].setText(default_value)

        # Close all auxiliary windows

        self.close_all_auxiliary_windows()

        # Kill existing log timer before creating a new one (prevents timer leak)

        if getattr(self, "_log_timer_id", None) is not None:
            self.killTimer(self._log_timer_id)

        self._log_timer_id = self.startTimer(self.LOG_TIMER_MS)

        self._init_global_shortcuts()

    def _init_widget_states(self) -> None:
        """Initialize enable/disable states for all mode-dependent widgets."""

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

    def set_default_values(self) -> None:

        stack_string = "0.376863,0.544274,0.525625,2.014363,1.404237,1.260913,2.108868,1.619996,1.661556,1.051359,1.410965,0.96871,1.000151,0.812025,0.723532,0.679077,0.749945,0.697612,0.590237,0.654072,0.756165,0.854369,0.892505,1.147616,0.196934,0.801568,0.692039,0.793093,0.732264,0.62781,0.700873,0.742287,0.74316,0.161261,1.028982,1.563076,0.726649,0.325847,0.844091,0.496665,0.585217,0.149928,0.54806,0.302789,0.439372,1.355508"

        multipliers = [m.strip() for m in stack_string.split(",")]

        defaults = {
            "h_type_custom": True,
            "l_type_custom": True,
            "nH_r": "2.3",
            "nL_r": "1.45",
            "substrate_choice": "Custom",
            "nSub_custom": "1.73",
            "l0": "1500.0",
            "stack_multipliers": multipliers,
            "wl_range_start": "1200.0",
            "wl_range_end": "1700.0",
            "wl_step": "0.2",
            "scan_wl_min": "1200.0",
            "scan_wl_max": "1700.0",
            "scan_wl_step": "2.0",
            "dynamics_threshold": "0.025",
            "min_transmission_floor": "0.10",
            "min_spectral_resolution": "1.0",
            "iter_divider_start": "10",
            "iter_divider_end": "3",
            "screening_mc_runs": "20",
            "screening_keep_top_k": "5",
            "mc_runs_block": "100",
            "strategy_phase_timeout": "120",
            "trigger_tolerance": "0.1",
            "noise_distribution": "gaussian",
            "non_monotonic_mode": "attenuate",
            "sim_thickness_probe_offset_ratio": "80.0",
            "robustness_noise_factors": "0.5,1,2",
            "robustness_num_runs": "150",
            "execution_mode": "premium",
            "non_monotonic_error_factor": "2.0",
            "wavelength_change_penalty": "1.2",
            "force_first_layer_same_wl": False,
            "extrema_exclusion_ratio": "60.0",
            "nucleation_mc_runs": "40",
            "mining_candidates_limit": "3000",
            # ── MODELE MACHINE : les six sources d'erreur, 2026-08-12 ──────────
            #
            # 🔴 LES DEFAUTS SONT CEUX DE LA MACHINE REELLE, pas des valeurs neutres.
            # Un champ vide ou a zero decrirait un instrument parfait qui n'existe pas,
            # et c'est precisement ce que 👤 a demande de corriger: "je ne veux pas etre
            # optimiste sur les fentes mais realiste", "les biais d'indice doivent
            # toujours etre actifs, c'est la base", "le rate est le cas general".
            "slit_bias_enabled": "1",
            "monochromator_resolution_nm": "2.0",
            "search_resolution": "1",
            "index_corridor": "0.005",
            "photometric_curvature_amp": "0.00375",
            "allow_rate": "1",
            # Les deux qui restent INACTIFS, et leur motif est dans CLAUDE.md:
            # le lissage parce que les algorithmes de l'OMS ne sont pas connus,
            # la grille machine parce que 👤 "on ne fait pas un calcul tous les 4 Hz".
            "reading_smoothing_window": "1",
            "machine_sampling_dd": "0.0",
            "n_screen_runs": "25",
            "k_keep_survivors": "10",
            "top_k_parents": "20",
            "max_fusions_per_parent": "5",
            "phase_a_scan_limit": "300",
            "phase_a_keep_limit": "50",
            "nucleation_max_rmse": "1.5",
            "nucleation_degradation": "1.4",
            "step0_sigma": "1.0",
            "sym_enable": "1",
            "sym_weight": f"{SYM_DEFAULT_WEIGHT}",
            "sym_same_wl_bonus": f"{SYM_DEFAULT_SAME_WL_BONUS}",
            "sym_extrema_window": f"{SYM_DEFAULT_EXTREMA_WINDOW_OT}",
            "sym_continuity_weight": f"{SYM_DEFAULT_CONTINUITY_WEIGHT}",
            "sym_adaptive_same_wl": "1",
            "sym_allow_hybrid": "0",
            "sym_prefer_on_tie": "1",
            "sym_tie_epsilon": f"{SYM_DEFAULT_TIE_EPS_ABS}",
            "sym_tie_epsilon_rel": f"{SYM_DEFAULT_TIE_EPS_REL}",
            "sym_scoring_mode": SYM_DEFAULT_SCORING_MODE,
            "show_plots": True,
            "export_excel": True,
        }

        self.populate_gui_from_config(defaults)

    def _save_undo_state(self) -> None:
        """Save current state of stack_table for undo"""

        # Verify undo_stack exists (might not be initialized at start)

        if not hasattr(self, "undo_stack"):
            self.undo_stack = deque(maxlen=5)

        table = self.widgets.get("stack_table")

        if table is None:
            return

        state = []

        for row in range(table.rowCount()):
            mult_item = table.item(row, 2)

            mult_val = mult_item.text() if mult_item else "1.0"

            state.append(mult_val)

        if state:
            self.undo_stack.append(state.copy())

    def _undo_stack_table(self) -> None:
        """Undo the last modification of the stack_table"""

        # Verify that undo_stack existe

        if not hasattr(self, "undo_stack") or not self.undo_stack:
            self.logger.warning("No undo state available")

            return

        state = self.undo_stack.pop()

        table = self.widgets.get("stack_table")

        if table is None:
            return

        table.blockSignals(True)

        # Adjust number of rows if necessary (without saving to undo_stack)

        while table.rowCount() < len(state):
            row = table.rowCount()

            table.insertRow(row)

            item_num = QTableWidgetItem(str(row + 1))

            item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 0, item_num)

            type_str = "H" if row % 2 == 0 else "L"

            item_type = QTableWidgetItem(type_str)

            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

            table.setItem(row, 1, item_type)

            table.setItem(row, 2, QTableWidgetItem("1.0"))

        while table.rowCount() > len(state):
            table.removeRow(table.rowCount() - 1)

        # Restore values

        for row, mult_val in enumerate(state):
            mult_item = table.item(row, 2)

            if mult_item:
                mult_item.setText(str(mult_val))

        table.blockSignals(False)

        self.logger.info(f"Undo: Restored {len(state)} layers")

    def populate_gui_from_config(self, config: dict[str, Any]) -> None:
        """Populate GUI widgets from configuration dictionary.

        Order is critical:

        1. Set radio button states (determines which widgets will be enabled)

        2. Set ALL widget values first (including potentially disabled ones)

        3. Apply enable/disable states LAST

        """

        # Historical aliases from older example JSON payloads.
        if isinstance(config, dict):
            if "substratee_choice" in config and config.get("substrate_choice") is None:
                config["substrate_choice"] = config.get("substratee_choice")
            if "substrate_choice" in config and config.get("substratee_choice") is None:
                config["substratee_choice"] = config.get("substrate_choice")

            if isinstance(config.get("substrate_choice"), str):
                canonical_sub = self._resolve_strat_material_name(config["substrate_choice"], kind="substrate")
                config["substrate_choice"] = canonical_sub
                config["substratee_choice"] = canonical_sub

            for key in ("h_material_file", "l_material_file"):
                if isinstance(config.get(key), str):
                    config[key] = self._resolve_strat_material_name(config[key], kind="material")

            # Backward-compatible aliases expected by tests and older manifests.
            if "h_material_file" not in config and "h_material" in config:
                config["h_material_file"] = config["h_material"]
            if "l_material_file" not in config and "l_material" in config:
                config["l_material_file"] = config["l_material"]
            if "substrate_choice" not in config and "substratee_choice" in config:
                config["substrate_choice"] = config["substratee_choice"]

        # Step 1: Set radio button states

        self.widgets["h_type_custom"].setChecked(bool(config.get("h_type_custom", True)))

        self.widgets["h_type_file"].setChecked(not config.get("h_type_custom", True))

        self.widgets["l_type_custom"].setChecked(bool(config.get("l_type_custom", True)))

        self.widgets["l_type_file"].setChecked(not config.get("l_type_custom", True))

        # Step 2: Set ALL widget values (before enabling/disabling)

        def _set_combo_by_text(widget, value: str) -> bool:
            if widget is None:
                return False
            target = str(value).strip()
            if not target:
                return False
            idx = widget.findText(target)
            if idx >= 0:
                widget.setCurrentIndex(idx)
                return True
            # Fallbacks: try matching against normalized whitespace/hyphen variants.
            normalized_target = target.replace("_", "-").replace(" ", "-").lower()
            for i in range(widget.count()):
                candidate = str(widget.itemText(i)).strip()
                normalized_candidate = candidate.replace("_", "-").replace(" ", "-").lower()
                if candidate == target or normalized_candidate == normalized_target:
                    widget.setCurrentIndex(i)
                    return True
            return False

        for key, widget in self.widgets.items():
            if isinstance(widget, QLineEdit) and key in config:
                widget.setText(str(config[key]))

        for combo_key in [
            "h_material_file",
            "l_material_file",
            "substrate_choice",
            "noise_distribution",
            "non_monotonic_mode",
            "sym_scoring_mode",
            "execution_mode",
        ]:
            if combo_key in self.widgets and combo_key in config and config[combo_key]:
                _set_combo_by_text(self.widgets[combo_key], str(config[combo_key]))

        # Step 3: Apply enable/disable states LAST

        self._on_material_mode_changed("h", "H")

        self._on_material_mode_changed("l", "L")

        self._on_substrate_choice_changed(self.widgets["substrate_choice"].currentText())

        # Step 4: Handle stack table

        stack_mults = None

        if "stack_multipliers" in config:
            raw_mults = config["stack_multipliers"]

            if isinstance(raw_mults, list):
                stack_mults = []

                for i, val in enumerate(raw_mults):
                    try:
                        stack_mults.append(float(val))

                    except (ValueError, TypeError):
                        stack_mults.append(1.0)

        elif "stack_string" in config:
            try:
                stack_mults = [float(m.strip()) for m in str(config["stack_string"]).split(",") if m.strip()]

            except (ValueError, TypeError):
                stack_mults = None

        if stack_mults:
            try:
                table = self.widgets.get("stack_table")

                if table:
                    table.setEnabled(True)

                    table.setRowCount(0)

                    for i, m in enumerate(stack_mults):
                        table.insertRow(i)

                        item_num = QTableWidgetItem(str(i + 1))

                        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 0, item_num)

                        item_type = QTableWidgetItem("H" if i % 2 == 0 else "L")

                        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        table.setItem(i, 1, item_type)

                        table.setItem(i, 2, QTableWidgetItem(f"{float(m):.6f}"))

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Error populating table: {e}")

    @safe_ui_action
    def save_configuration(self) -> None:
        """Save current GUI configuration to a JSON file.

        Only saves relevant data based on selected modes:

        - If Custom mode: saves index value (nH_r/nL_r)

        - If Dispersive mode: saves material file selection

        - substrate custom index only saved if 'Custom' substrate selected

        """

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not filename:
            return

        set_certus_last_dir(filename)

        try:
            config = {
                "h_type_custom": self.widgets["h_type_custom"].isChecked(),
                "l_type_custom": self.widgets["l_type_custom"].isChecked(),
                "substrate_choice": self.widgets["substrate_choice"].currentText(),
                "l0": self.widgets["l0"].text(),
            }

            # Save only relevant H-index data

            if self.widgets["h_type_custom"].isChecked():
                config["nH_r"] = self.widgets["nH_r"].text()

            else:
                config["h_material_file"] = self.widgets["h_material_file"].currentText()

            # Save only relevant L-index data

            if self.widgets["l_type_custom"].isChecked():
                config["nL_r"] = self.widgets["nL_r"].text()

            else:
                config["l_material_file"] = self.widgets["l_material_file"].currentText()

            # Save custom substrate only if "Custom" is selected

            if self.widgets["substrate_choice"].currentText() == "Custom":
                config["nSub_custom"] = self.widgets["nSub_custom"].text()

            table = self.widgets["stack_table"]

            stack_multipliers = []

            for row in range(table.rowCount()):
                item = table.item(row, 2)

                if item:
                    try:
                        stack_multipliers.append(float(item.text()))

                    except ValueError:
                        stack_multipliers.append(1.0)

            config["stack_multipliers"] = stack_multipliers

            for key in [
                "wl_range_start",
                "wl_range_end",
                "wl_step",
                "scan_wl_min",
                "scan_wl_max",
                "scan_wl_step",
                "dynamics_threshold",
                "min_transmission_floor",
                "min_spectral_resolution",
                "mc_runs_block",
                "iter_divider_start",
                "iter_divider_end",
                "strategy_phase_timeout",
                "screening_mc_runs",
                "screening_keep_top_k",
                "trigger_tolerance",
                "sim_thickness_probe_offset_ratio",
                "non_monotonic_error_factor",
                "wavelength_change_penalty",
                "extrema_exclusion_ratio",
                "robustness_noise_factors",
                "robustness_num_runs",
                "nucleation_mc_runs",
                "mining_candidates_limit",
                "slit_bias_enabled",
                "monochromator_resolution_nm",
                "search_resolution",
                "index_corridor",
                "photometric_curvature_amp",
                "allow_rate",
                "reading_smoothing_window",
                "machine_sampling_dd",
                "n_screen_runs",
                "k_keep_survivors",
                "top_k_parents",
                "max_fusions_per_parent",
                "phase_a_scan_limit",
                "phase_a_keep_limit",
                "nucleation_max_rmse",
                "nucleation_degradation",
                "step0_sigma",
                "sym_enable",
                "sym_weight",
                "sym_same_wl_bonus",
                "sym_extrema_window",
                "sym_continuity_weight",
                "sym_adaptive_same_wl",
                "sym_allow_hybrid",
                "sym_prefer_on_tie",
                "sym_tie_epsilon",
                "sym_tie_epsilon_rel",
            ]:
                if key in self.widgets:
                    config[key] = self.widgets[key].text()

            # Save ComboBox values

            if "noise_distribution" in self.widgets:
                config["noise_distribution"] = self.widgets["noise_distribution"].currentText()

            if "non_monotonic_mode" in self.widgets:
                config["non_monotonic_mode"] = self.widgets["non_monotonic_mode"].currentText()

            if "sym_scoring_mode" in self.widgets:
                config["sym_scoring_mode"] = self.widgets["sym_scoring_mode"].currentText()

            if "execution_mode" in self.widgets:
                config["execution_mode"] = self.widgets["execution_mode"].currentText()

            config["show_plots"] = True

            config["export_excel"] = True

            config["force_first_layer_same_wl"] = True

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.logger.info("Configuration saved: %s", filename)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error saving: {e}")

    @safe_ui_action
    def load_configuration(self, filename=None) -> None:
        """Load configuration from a JSON file and populate the GUI.

        Handles both new format (stack_multipliers list) and legacy format (stack_string).

        Opens a JSON viewer window for inspection after loading.

        Args:

            filename: Optional path to JSON file. If None, opens file dialog.

        """

        if filename is None or isinstance(filename, bool):
            filename, _ = QFileDialog.getOpenFileName(
                self, "Load Configuration", get_certus_last_dir(), "JSON Files (*.json)"
            )

        if not filename:
            return

        set_certus_last_dir(filename)

        self._last_config_file = filename

        try:
            with open(filename, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                raise ValueError("Configuration JSON must be an object/dictionary.")

            # Validate that the file is not a DESIGN config loaded into STRAT
            if "front" in config and not config.get("stack_multipliers") and not config.get("stack_string") and not config.get("blocks"):
                raise ValueError(
                    "This file appears to be a DESIGN configuration. "
                    "Please load a valid STRAT strategy configuration containing stack multipliers or blocks."
                )

            try:
                validated = StratConfigDTO.model_validate(config)
                config = validated.model_dump(mode="python", exclude_none=False)
            except ValidationError as e:
                msg = f"Invalid STRAT configuration: {e}"
                self.logger.error(msg)
                QMessageBox.critical(self, "Invalid configuration", msg)
                return

            self._loaded_config = dict(config)

            if "stack_string" in config and "stack_multipliers" not in config:
                try:
                    config["stack_multipliers"] = [
                        float(m) for m in str(config["stack_string"]).split(",") if m.strip()
                    ]

                except (ValueError, TypeError):
                    logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

            validation_warnings = self._validate_strat_config(config)
            for warn in validation_warnings:
                self.logger.warning("[STRAT-CONFIG] %s", warn)

            self.populate_gui_from_config(config)

            post_warnings = self._validate_strat_gui_state(config)
            for warn in post_warnings:
                self.logger.warning("[STRAT-CONFIG] %s", warn)

            short_name = Path(filename).name

            viewer = JsonViewerWindow(self, f"Config - {short_name}", config)

            viewer.show()

            viewer.raise_()

            viewer.activateWindow()

            if not hasattr(self, "json_windows"):
                self.json_windows = []

            self.json_windows.append(viewer)

            self.logger.info("=" * 60)
            self.logger.info("CONFIGURATION LOADED: %s", short_name)
            self.logger.info("=" * 60)

            for key in sorted(config.keys()):
                val = config[key]
                if isinstance(val, list) and len(val) > 10:
                    val_str = f"{val[:3]} ... ({len(val)} items) ...  {val[-3:]}"
                else:
                    val_str = str(val)

                self.logger.info("  %-35s: %s", key, val_str)

            self.logger.info("=" * 60)

            if os.environ.get("QT_QPA_PLATFORM", "").lower() != "offscreen":
                blocks = config.get("blocks") or [] if isinstance(config, dict) else []

                strat_id = str(config.get("strategy_id", "")).strip()

                n_blocks = int(config.get("n_blocks") or len(blocks)) if isinstance(config, dict) else 0

                # Two formats: (1) GUI session via save_configuration - no strategy_id/blocks;

                # (2) export mined strategy / external JSON - strategy_id + blocks required.

                is_session_cfg = isinstance(config, dict) and (
                    "stack_multipliers" in config or "h_material_file" in config
                )

                sub_label = "UNKNOWN"

                if isinstance(config, dict):
                    sub_label = str(config.get("substrate_choice", "UNKNOWN")).strip() or "UNKNOWN"

                summary_lines: list = [
                    f"SUBSTRATE: {sub_label}",
                    "FACES: ONE FACE (NO BACKSIDE)",
                    "",
                    f"File: {Path(filename).resolve()}",
                    "",
                ]

                if is_session_cfg and not (strat_id and isinstance(blocks, list) and len(blocks) > 0):
                    n_lay = len(config.get("stack_multipliers") or []) if isinstance(config, dict) else 0

                    summary_lines.extend(
                        [
                            "Format: GUI session (save_configuration)",
                            "  -> Material parameters, stack (multipliers), execution options.",
                            "  -> The strategy_id / blocks keys are not part of this format (normal).",
                            "  -> To load mined strategies: 'external strategies' menu / dedicated JSON.",
                            "",
                            "Structure (session)",
                            f"  stack_multipliers count (layers): {n_lay}",
                            "",
                            "Embedded Strategy",
                            "  (not present - this file is not a mined strategy export)",
                        ]
                    )

                else:
                    summary_lines.extend(
                        [
                            "General",
                            f"Strategy ID: {strat_id or '(missing)'}",
                            "",
                            "Structure",
                            (f"n_blocks: {n_blocks}", n_blocks <= 0),
                            (
                                f"blocks entries: {len(blocks) if isinstance(blocks, list) else 0}",
                                not isinstance(blocks, list) or len(blocks) == 0,
                            ),
                            "",
                            "Compatibility checks",
                            f"Keys in JSON: {len(config.keys()) if isinstance(config, dict) else 0}",
                            (
                                f"Contains required keys (strategy_id, blocks): {'yes' if ('strategy_id' in config and 'blocks' in config) else 'no'}",
                                not ("strategy_id" in config and "blocks" in config),
                            ),
                        ]
                    )

                summary = build_summary_plain_text("CERTUS STRAT - Config Summary", summary_lines)

                show_load_summary_dialog(self, "STRAT Load Summary", summary)

        except Exception as e:
            self.logger.error(f"Error loading: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(
                self,
                "Error Loading Configuration",
                f"Could not load configuration file:\n{e}"
            )

    def load_external_strategies(self) -> None:

        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Strategy Files", get_certus_last_dir(), "JSON Files (*.json)"
        )

        if not files:
            return

        set_certus_last_dir(files[0])

        loaded_strategies = []

        REQUIRED_KEYS = {"strategy_id", "blocks"}

        table = self.widgets.get("stack_table")

        expected_layers = table.rowCount() if table is not None else 0

        expected_layers = max(0, int(expected_layers))

        seen_ids: set[str] = set()

        try:
            for f_path in files:
                with open(f_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)

                    except json.JSONDecodeError:
                        continue

                    def validate_and_add(item) -> None:

                        if not (isinstance(item, dict) and all(k in item for k in REQUIRED_KEYS)):
                            return

                        strat_id = str(item.get("strategy_id", "")).strip()

                        if not strat_id:
                            return

                        if strat_id in seen_ids:
                            return

                        item_norm = dict(item)

                        if "n_blocks" not in item_norm:
                            item_norm["n_blocks"] = len(item_norm.get("blocks", []))

                        # Strong schema + contract validation before running Step 33

                        expected_n = item_norm.get("n_blocks", len(item_norm.get("blocks", [])))

                        if expected_layers > 0:
                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm, expected_layers, expected_n_blocks=expected_n
                            )

                            if not ok:
                                return

                        else:
                            # If no expected layer count is available, still hard-validate block typing.

                            max_end = 0

                            for blk in item_norm.get("blocks", []):
                                if isinstance(blk, dict):
                                    try:
                                        max_end = max(max_end, int(blk.get("end", 0)))

                                    except (TypeError, ValueError):
                                        logging.getLogger("CERTUS").debug(
                                            "Silenced exception in %s", __name__, exc_info=True
                                        )

                            ok, _ = _validate_strategy_blocks_contract(
                                item_norm,
                                num_layers=max(max_end, 1),
                                expected_n_blocks=expected_n,
                            )

                            if not ok:
                                return

                        loaded_strategies.append(item_norm)

                        seen_ids.add(strat_id)

                    if isinstance(data, list):
                        for item in data:
                            validate_and_add(item)

                    else:
                        validate_and_add(data)

            if not loaded_strategies:
                self.logger.warning("No valid strategy found.")

                return

            self.logger.info("Loaded %d valid strategies.", len(loaded_strategies))

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.logger.error(f"Error parsing strategy files: {e}")

            return

        params = self.collect_params()

        if self.opti_results is None:
            self.logger.info("Initializing context for external strategies (Matrices & Indices)...")

            try:
                self.opti_results = rebuild_visualization_context(params, self.logger)

            except NUMERICAL_FAULT_EXCEPTIONS as e:
                self.logger.error(f"Failed to initialize context: {e}")

                return

        params["loaded_strategies"] = loaded_strategies

        self.progress_bar.setValue(0)

        self.status_label.setText("Simulating Loaded Strategies...")

        for btn in [
            self.run_step0_btn,
            self.run_step2_btn,
            self.run_step3_btn,
            self.run_full_btn,
            self.load_strat_btn,
        ]:
            btn.setEnabled(False)

        self.worker = WorkerThread(
            step=StratTask.EXTERNAL_EVALUATION,
            params=params,
            opti_results=self.opti_results,
            timing_logger=self.timing_logger,
        )
        self._register_worker_thread(self.worker, "STRAT-external-evaluation")

        self.worker.signals.finished.connect(self.on_workflow_finished)

        self.worker.signals.error.connect(self.on_workflow_error)

        self.worker.signals.progress.connect(self.on_progress_update)

        self.worker.signals.plot.connect(self.on_plot_ready)

        self.worker.signals.excel_ready.connect(self.on_excel_ready)

        try:
            self.worker.signals.show_strategies_table.disconnect(self.on_show_strategies_table)
        except (TypeError, RuntimeError):
            pass
        self.worker.signals.show_strategies_table.connect(self.on_show_strategies_table)

        self.worker.start()

    def collect_params(self) -> dict[str, Any]:
        """Collect all GUI parameters into a dictionary for workflow execution.

        Intelligently resolves material clues:

        - Custom mode: uses constant float value from nH_r/nL_r field

        - Dispersive mode: uses material name string for database lookup

        Returns:

            Dict containing all parameters for the simulation workflow."""

        # Resolve H-index: either constant float or material name

        if self.widgets["h_type_custom"].isChecked():
            nH_id = float(self._get_float_safe("nH_r", 2.3))

        else:
            txt = self.widgets["h_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No H-material file selected. Reverting to Custom value (2.3).")

                nH_id = float(self._get_float_safe("nH_r", 2.3))

            else:
                nH_id = self._resolve_strat_material_name(txt, kind="material")

        if self.widgets["l_type_custom"].isChecked():
            nL_id = float(self._get_float_safe("nL_r", 1.45))

        else:
            txt = self.widgets["l_material_file"].currentText().strip()

            if not txt:
                self.logger.warning("⚠️ No L-material file selected. Reverting to Custom value (1.45).")

                nL_id = float(self._get_float_safe("nL_r", 1.45))

            else:
                nL_id = self._resolve_strat_material_name(txt, kind="material")

        sub_choice = self._resolve_strat_material_name(self.widgets["substrate_choice"].currentText(), kind="substrate")

        if sub_choice == "Custom" or not sub_choice:
            nSub_id = self._get_float_safe("nSub_custom", 1.73)

        else:
            nSub_id = sub_choice

        table = self.widgets["stack_table"]

        multipliers = [float(table.item(r, 2).text()) for r in range(table.rowCount()) if table.item(r, 2)]

        stack_string = ",".join(map(str, multipliers))

        try:
            noise_str = self.widgets["robustness_noise_factors"].text().strip().replace("[", "").replace("]", "")

            noise_factors = [float(x.strip()) for x in noise_str.split(",") if x.strip()]

        except (ValueError, TypeError):
            noise_factors = [0.5, 1.0, 2.0]

        if str(nSub_id).strip() in {"Silice", "SiO2", "H800-SiO2", "H800 SiO2", "H800_SiO2"}:
            nSub_id = "SiO2"
        elif str(nSub_id).strip() in {"Sapphire", "Sapphire (Al2O3)"}:
            nSub_id = "Sapphire (Al2O3)"

        params_out = {
            "nH_id": nH_id,
            "nL_id": nL_id,
            "nSub_id": nSub_id,
            "substrate_choice": sub_choice,
            "h_material_file": self.widgets["h_material_file"].currentText(),
            "l_material_file": self.widgets["l_material_file"].currentText(),
            "l0": self._get_float_safe("l0", 1500.0),
            "stack_string": stack_string,
            "wl_range": (
                self._get_float_safe("wl_range_start", 1200.0),
                self._get_float_safe("wl_range_end", 1700.0),
            ),
            "wl_step": self._get_float_safe("wl_step", 0.2),
            "scan_wl_min": self._get_float_safe("scan_wl_min", 1200.0),
            "scan_wl_max": self._get_float_safe("scan_wl_max", 1700.0),
            "scan_wl_step": self._get_float_safe("scan_wl_step", 2.0),
            "dynamics_threshold": self._get_float_safe("dynamics_threshold", 0.025),
            "min_transmission_floor": self._get_float_safe("min_transmission_floor", 0.10),
            "strict_min_transmission_floor": True,
            "enforce_best_strategy_tmin_check": True,
            "min_spectral_resolution": self._get_float_safe("min_spectral_resolution", 1.0),
            "mc_runs_block": int(self._get_float_safe("mc_runs_block", 100)),
            "iter_divider_start": self._get_float_safe("iter_divider_start", 10.0),
            "iter_divider_end": self._get_float_safe("iter_divider_end", 3.0),
            "screening_mc_runs": int(self._get_float_safe("screening_mc_runs", 20)),
            "screening_keep_top_k": int(self._get_float_safe("screening_keep_top_k", 5)),
            "strategy_phase_timeout": self._get_float_safe("strategy_phase_timeout", 120.0),
            "reality_sim_params": {
                "trigger_tolerance": self._get_float_safe("trigger_tolerance", 0.1),
                "noise_distribution": NOISE_DISTRIBUTION_GAUSSIAN,
            },
            # Default None and not 1.0 — MEASURE of 2026-08-04.
            #
            # This parameter selects Phase B noise convention:
            #   not None -> noise = dT_dd * z * sigma_nm ("thickness tolerance nm" mode)
            #   None     -> noise = z * tolerance / 100  (PHOTOMETRIC mode)
            #
            # Photometric mode aligns Phase B with Phase A wavelength selection.
            "thickness_tolerance_nm": self._get_float_safe("thickness_tolerance_nm", None),
            "mse_tolerance_limit_pct": self._get_float_safe("mse_tolerance_limit_pct", 30.0),
            # Legacy/Fallback if needed (hidden from GUI by default now if we remove it, but user might have it in old logical flow)
            "sim_thickness_probe_offset_ratio": 80.0,  # Hardcoded fallback or self._get_float_safe("sim_thickness_probe_offset_ratio", 80.0),
            "non_monotonic_error_factor": self._get_float_safe("non_monotonic_error_factor", 2.0),
            "non_monotonic_mode": NON_MONOTONIC_MODE_REJECT
            if self.widgets.get("non_monotonic_mode") and self.widgets["non_monotonic_mode"].currentText() == "reject"
            else NON_MONOTONIC_MODE_ATTENUATE,
            "wavelength_change_penalty": self._get_float_safe("wavelength_change_penalty", 1.2),
            "robustness_noise_factors": noise_factors,
            "robustness_num_runs": int(self._get_float_safe("robustness_num_runs", 150)),
            "nucleation_mc_runs": int(self._get_float_safe("nucleation_mc_runs", 40)),
            "mining_candidates_limit": int(self._get_float_safe("mining_candidates_limit", 3000)),
            "n_screen_runs": int(self._get_float_safe("n_screen_runs", 25)),
            "k_keep_survivors": int(self._get_float_safe("k_keep_survivors", 10)),
            "top_k_parents": int(self._get_float_safe("top_k_parents", 20)),
            "max_fusions_per_parent": int(self._get_float_safe("max_fusions_per_parent", 5)),
            "phase_a_scan_limit": int(self._get_float_safe("phase_a_scan_limit", 300)),
            "phase_a_keep_limit": int(self._get_float_safe("phase_a_keep_limit", 50)),
            "nucleation_max_rmse": self._get_float_safe("nucleation_max_rmse", 1.5),
            "nucleation_degradation": self._get_float_safe("nucleation_degradation", 1.4),
            "step0_sigma": self._get_float_safe("step0_sigma", 1.0),
            "show_plots": True,
            "export_excel": True,
            "extrema_exclusion_ratio": self._get_float_safe("extrema_exclusion_ratio", 60.0),
            # ── AXIS 1.1: READING noise of monitoring signal ─────────────
            #
            # BY DEFAULT INACTIVE, and not due to superficial caution: it is a
            # first-order model change. It will INCREASE the crash
            # rates (a flat extremum will sometimes be missed or split) and
            # DECREASE the apparent benefit of POEM (its anchors will cease to be
            # exact values to become measurements). It is the measurement of both
            # sides that must decide, not intuition.
            #
            # No widget: these flags are read in the configuration
            # file, like `consensus_seed_list`. A JSON boolean, "1"/"0"
            # or "true"/"false" are accepted.
            #
            # `poem_anchor_noise` governs BOTH PHASES, because the rule it
            # enforces is a single physical statement — 👤 "a control
            # wavelength of layer i (i > 1) is forbidden if, when the
            # signal is noisy, there is a risk of miscounting the number of
            # turning points or not stopping at the desired level; all this is
            #valid in phase A as well as in phase B". See the comment of
            # `_validate_candidates_phase_a`.
            #
            # `poem_anchor_noise_phase_a` ONLY exists for attribution: it allows
            # isolating the effect of a stage in an A/B. Its default follows the master, and
            # it must not be used to permanently leave Phase A noiseless.
            "poem_anchor_noise": _config_flag(
                getattr(self, "_loaded_config", {}), "poem_anchor_noise"
            ),
            "poem_anchor_noise_phase_a": _config_flag(
                getattr(self, "_loaded_config", {}),
                "poem_anchor_noise_phase_a",
                _config_flag(getattr(self, "_loaded_config", {}), "poem_anchor_noise"),
            ),
            # ── AXIS 1.2: Turning point detection rule ──────────────
            #
            # Detector hysteresis, in MULTIPLE of the noise amplitude
            # `trigger_tolerance`. 0 = historical rule (sign change beyond
            # a numerical guard of 1e-12), which is not a physical rule.
            #
            # 👤 "The 4%, for me, was a wild guess, to be certain that we will
            # get there" (2026-08-06). This threshold is NOT the 4% starting
            # amplitude: the 4% pre-selects a wavelength, this describes
            # how the machine READS. Its reference magnitude is the noise, which is
            # measured: the draw being bounded to +/- A, the maximum apparent deviation that the
            # noise alone can produce is 2A, so from factor 2 the noise can
            # no longer create a turning point.
            #
            # The value is not set here: it is swept and decided by the
            # measurement. Default 0 = path unchanged.
            "tp_hysteresis_factor": _config_float(
                getattr(self, "_loaded_config", {}), "tp_hysteresis_factor"
            ),
            # ── Safety margin at turning point, in noise multiples ──────
            #
            # > 0 : the stopping level must be separated from neighboring turning points
            # by at least `factor x trigger_tolerance/100`, IN TRANSMISSION. Activates at the
            # same time the true accumulated matrix in Phase A — the zeros placeholder
            # made the turning points rule inert. 0 = previous path.
            "phase_a_level_margin_factor": _config_float(
                getattr(self, "_loaded_config", {}), "phase_a_level_margin_factor"
            ),
            # ── YIELD weight in DP objective (axis 4.1) ──────────
            #
            # cost = cost_nm + w x (-log(1 - p)), where p is the rate of non-
            # terminable depositions measured by Phase A for this (layer, lambda). 0 = the
            # crash does not enter the objective, previous behavior.
            "dp_yield_weight": _config_float(
                getattr(self, "_loaded_config", {}), "dp_yield_weight"
            ),
            # ── Photometric affine distortion (a, b) & POEM enable ──────────────
            "affine_scale_amp": _config_float(
                getattr(self, "_loaded_config", {}), "affine_scale_amp"
            ),
            "affine_offset_amp": _config_float(
                getattr(self, "_loaded_config", {}), "affine_offset_amp"
            ),
            "poem_enabled": _config_flag(
                getattr(self, "_loaded_config", {}), "poem_enabled", True
            ),
            # ── Machine reading smoothing window k (T4) ───────────────────────
            "reading_smoothing_window": int(
                _config_float(getattr(self, "_loaded_config", {}), "reading_smoothing_window") or 1
            ),
            # ── 👤 MONOCHROMATOR SLIT, part of the strategy to report ──────────
            #
            # "Finding a strategy is finding the control wavelengths or the rate layers,
            # AND giving the user a slit value." So it is an OUTPUT, not just a machine
            # setting -- a strategy is not executable in the chamber without it.
            # 2 nm is the nominal, the one the measured noise amplitude corresponds to,
            # so the default leaves every existing result bit-identical.
            "monochromator_resolution_nm": (
                self._get_float_safe("monochromator_resolution_nm", 0.0)
                or _config_float(getattr(self, "_loaded_config", {}), "monochromator_resolution_nm")
                or 2.0
            ),
            # ── 👤 RATE MODE: allowed or refused, from the final table ─────────
            #
            # "The user must be able, in the final table, to allow or refuse the rate.
            # Then the best strategies appear." Rate is therefore not a fallback the
            # machine trips into: switching it on ADDS candidate strategies carrying one
            # Rate layer each, which then stand or fall on the same statistics.
            #
            # 🔴 Default FALSE. With the key absent the candidate list is untouched and
            # every downstream bit is what it was -- constraint C1.
            # 🔴 LE WIDGET D'ABORD, comme les autres sources d'erreur. Cette ligne lisait
            # UNIQUEMENT le fichier de design: le champ de l'interface affichait 1, le run
            # tournait a False, et le bandeau d'etat disait "ACTIF". Trouve le 2026-08-12
            # en verifiant que l'affichage correspond a ce que `collect_params` rend --
            # un bandeau qui ment est pire que pas de bandeau du tout.
            "allow_rate": bool(self._get_float_safe(
                "allow_rate",
                _config_float(getattr(self, "_loaded_config", {}), "allow_rate", 1.0),
            ) > 0.5),
            # ── Index corridor uncertainty delta_max (T5) ──────────────────────
            "index_corridor": float(self._get_float_safe(
                "index_corridor",
                _config_float(getattr(self, "_loaded_config", {}), "index_corridor",
                              INDEX_CORRIDOR_DEFAULT),
            )),
            # ── The four remaining error sources, 👤 2026-08-12 ─────────────────
            #
            # 🔴 THESE FOUR WERE ONLY REACHABLE FROM CODE DEFAULTS. Writing them into a
            # design file did nothing, so a configuration could not describe the machine
            # it was run on -- which is 17-7 in another form: a run whose settings cannot
            # be recovered is comparable to nothing.
            #
            # ⚠️ `None` means "not stated, take the code default", and that is deliberate:
            # an absent key must not read as "off". The defaults themselves changed on
            # 2026-08-12 to describe the real machine (bias on, Rate on, corridor on,
            # curvature on), so silence now means the realistic setting, not the empty one.
            # 🔴 LE WIDGET FAIT FOI QUAND IL EXISTE. Sans cela l'utilisateur regle un
            # champ dans l'interface, le run n'en tient pas compte, et rien ne le dit --
            # exactement le mode de defaillance que ce depot documente. `_get_float_safe`
            # rend le defaut quand le widget est absent (chemin sans interface), et le
            # fichier de design reste la source dans ce cas.
            "slit_bias_enabled": bool(self._get_float_safe(
                "slit_bias_enabled",
                1.0 if _config_flag_default(
                    getattr(self, "_loaded_config", {}), "slit_bias_enabled", True) else 0.0,
            ) > 0.5),
            "search_resolution": bool(self._get_float_safe(
                "search_resolution",
                1.0 if _config_flag_default(
                    getattr(self, "_loaded_config", {}), "search_resolution", True) else 0.0,
            ) > 0.5),
            "photometric_curvature_amp": float(self._get_float_safe(
                "photometric_curvature_amp",
                _config_float(getattr(self, "_loaded_config", {}),
                              "photometric_curvature_amp", PHOTOMETRIC_CURVATURE_AMP),
            )),
            # Grille TMM : 0 = grille actuelle. 👤 "on ne fait pas un calcul tous les 4 Hz,
            # c'est la base de ce code qui doit etre ultra rapide" -- donc 0 reste le defaut.
            "machine_sampling_dd": _config_float(
                getattr(self, "_loaded_config", {}), "machine_sampling_dd", 0.0
            ),
            # Porte de plantage : 0 = comparaison historique du taux ESTIME au seuil fixe,
            # bit pour bit. Une valeur dans (0, 1) la remplace par une borne de confiance
            # de Clopper-Pearson a ce niveau -- voir `_crash_gate_rejects`. Inactive par
            # defaut, contrainte C1 : le correctif change tous les resultats, donc il doit
            # etre ARME explicitement et mesure seul.
            "crash_gate_confidence": _config_float(
                getattr(self, "_loaded_config", {}), "crash_gate_confidence", 0.0
            ),
            # ── AXIS 3: the spectral target, routed from the configuration ───
            #
            # 👤 "The most important is the respected spectral target." STRAT ranked
            # on the deviation to the NOMINAL spectrum and had never received the target.
            #
            # Same format as DESIGN — a list of zones
            # {on, lmin, lmax, tmin, tmax, w} — so that both modules talk about the
            # same thing and the functional is the one DESIGN already minimizes.
            #
            # Absent = documented fallback on the unweighted nominal, so behavior
            # unchanged. It is the PRESENCE of zones that activates axis 3.
            "targets": (
                getattr(self, "_loaded_config", {}).get("targets")
                if isinstance(getattr(self, "_loaded_config", None), dict)
                else None
            ),
            "logger": self.logger,
            "materials_db": self.materials_db,
            "force_first_layer_same_wl": True,
            "include_secondary_rmse_stats": bool(self._get_float_safe("include_secondary_rmse_stats", 0)),
            "keep_full_mc_top_k": int(self._get_float_safe("keep_full_mc_top_k", 30)),
            "robustness_seed": int(self._get_float_safe("robustness_seed", 42)),
            "phase_a_seed": int(self._get_float_safe("phase_a_seed", self._get_float_safe("robustness_seed", 42))),
            "sym_enable": True,
            "sym_weight": self._get_float_safe("sym_weight", SYM_DEFAULT_WEIGHT),
            "sym_same_wl_bonus": self._get_float_safe("sym_same_wl_bonus", SYM_DEFAULT_SAME_WL_BONUS),
            "sym_extrema_window": self._get_float_safe("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT),
            "sym_continuity_weight": self._get_float_safe("sym_continuity_weight", SYM_DEFAULT_CONTINUITY_WEIGHT),
            "sym_adaptive_same_wl": bool(self._get_float_safe("sym_adaptive_same_wl", 1.0) > 0.5),
            "sym_allow_hybrid": bool(self._get_float_safe("sym_allow_hybrid", 0.0) > 0.5),
            "sym_prefer_on_tie": bool(self._get_float_safe("sym_prefer_on_tie", 1.0) > 0.5),
            "sym_tie_epsilon": self._get_float_safe("sym_tie_epsilon", SYM_DEFAULT_TIE_EPS_ABS),
            "sym_tie_epsilon_rel": self._get_float_safe("sym_tie_epsilon_rel", SYM_DEFAULT_TIE_EPS_REL),
            "sym_scoring_mode": (
                self.widgets["sym_scoring_mode"].currentText()
                if self.widgets.get("sym_scoring_mode")
                else SYM_DEFAULT_SCORING_MODE
            ),
            "enable_consensus_ranking": bool(self._get_float_safe("enable_consensus_ranking", 1.0) > 0.5),
            "consensus_num_seeds": int(self._get_float_safe("consensus_num_seeds", 3)),
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "consensus_seed_stride": int(self._get_float_safe("consensus_seed_stride", 1)),
            "consensus_top_k": int(self._get_float_safe("consensus_top_k", 12)),
            "consensus_num_runs": int(self._get_float_safe("consensus_num_runs", 150)),
            "consensus_std_weight": self._get_float_safe("consensus_std_weight", 0.35),
            "consensus_score_mode": "mean_std",
            "consensus_seed_list": str(getattr(self, "_loaded_config", {}).get("consensus_seed_list", "")),
            "execution_mode": (
                self.widgets["execution_mode"].currentText().strip().lower()
                if self.widgets.get("execution_mode")
                else "premium"
            ),
            "fast_auto_blocks": True,
        }

        mode = str(params_out.get("execution_mode", "premium")).strip().lower()
        if mode == "fast":
            params_out["execution_mode"] = "fast"
            params_out["robustness_num_runs"] = 50
            params_out["consensus_num_runs"] = 50
            params_out["n_screen_runs"] = 10
            params_out["elite_rounds"] = 1
            params_out["dp_top_k"] = 20
            params_out["k_keep_survivors"] = 6
        elif mode == "deep":
            params_out["execution_mode"] = "deep"
            params_out["robustness_num_runs"] = 300
            params_out["consensus_num_runs"] = 300
            params_out["n_screen_runs"] = 50
            params_out["elite_rounds"] = 3
            params_out["dp_top_k"] = 100
            params_out["k_keep_survivors"] = 25
            params_out["mining_candidates_limit"] = 10000
        else:
            params_out["execution_mode"] = "premium"
            params_out["robustness_num_runs"] = 150
            params_out["consensus_num_runs"] = 150
            params_out["n_screen_runs"] = 25
            params_out["elite_rounds"] = 2
            params_out["dp_top_k"] = 40
            params_out["k_keep_survivors"] = 10
            params_out["mining_candidates_limit"] = 3000

        return params_out

    def _normalize_alias_key(self, value: Any) -> str:
        """Return a canonical lookup key for a user-facing material/substrate name."""
        txt = str(value).strip()
        if not txt:
            return ""
        return "".join(ch for ch in txt.lower().replace("_", "-") if not ch.isspace())

    def _resolve_strat_material_name(self, value: Any, kind: str = "material") -> str:
        """Resolve a raw STRAT material/substrate name to a canonical combo-box label."""
        txt = str(value).strip()
        if not txt:
            return ""

        alias_map = {
            "substrate": {
                "silice": "SiO2",
                "sio2": "SiO2",
                "h800-sio2": "SiO2",
                "h800sio2": "SiO2",
                "h800_siO2": "SiO2",
                "sapphire": "Sapphire (Al2O3)",
                "sapphire(al2o3)": "Sapphire (Al2O3)",
                "sapphire (al2o3)": "Sapphire (Al2O3)",
            },
            "material": {
                "h800-nb2o5": "H800-Nb2O5",
                "h800nb2o5": "H800-Nb2O5",
                "h800-nb": "H800-Nb2O5",
                "h800nb": "H800-Nb2O5",
                "h800-sio2": "H800-SiO2",
                "h800sio2": "H800-SiO2",
                "ir-h400-nb2o5": "IR-H400-Nb2O5",
                "ir-h400-sio2": "IR-H400-SiO2",
                "ir-syrus-nb2o5": "IR-Syrus-Nb2O5",
                "ir-syrus-sio2": "IR-Syrus-SiO2",
            },
        }
        key = self._normalize_alias_key(txt)
        resolved = alias_map.get(kind, {}).get(key, txt)
        return resolved

    def _get_float_safe(self, widget_name, default=0.0) -> Any:

        if widget_name not in self.widgets:
            return default

        text = self.widgets[widget_name].text().strip()

        if not text:
            return default

        try:
            return float(text)

        except ValueError:
            return default

