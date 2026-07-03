from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class CertusIndexSplineSmartInitMixin:
    """CertusIndexSplineSmartInitMixin."""

    def _on_smart_init_keep(
        self, dlg: QDialog, cfg: "SplineOptConfig", state: _SmartInitState, ui_ctx: dict[str, Any]
    ) -> None:
        if cfg is None:
            dlg.accept()
            return

        d_final = float(state.preview_d_nm)
        n_phys_final = np.asarray(state.n_phys, dtype=np.float64).copy()
        L_nodes_final = np.asarray(state.L_nodes, dtype=np.float64).copy()
        sk_final = np.asarray(getattr(self, "smart_preview_sk_arr", state.sk), dtype=np.float64).ravel().copy()

        rmse_preview_mesh = float(state.current_rmse)
        rmse_worker_mesh = rmse_preview_mesh
        sk_canon_keep: np.ndarray | None = None
        relax_si_mono = bool(ui_ctx.get("relax_si_mono", False))
        chk_si_deep = ui_ctx.get("chk_si_deep")
        chk_si_two_phase = ui_ctx.get("chk_si_two_phase")

        try:
            lam_c = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
            lam_min_c = float(np.min(lam_c))
            lam_max_c = float(np.max(lam_c))
            _mdl_ck = float(getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.0) or 0.0)
            sk_canon = bridge_sigma_knots_preserve_manual(
                sk_final,
                lam_min_c,
                lam_max_c,
                rmse_fit_lambda_nm=getattr(cfg, "rmse_fit_lambda_nm", None),
                min_delta_lambda_over_lambda_mean=_mdl_ck if _mdl_ck > 0.0 else None,
            )
            sk_canon_keep = sk_canon
            n_on_canon, L_on_canon = interp_n_L_pwlnk_to_sigmas(sk_final, n_phys_final, L_nodes_final, sk_canon)
            _, rmse_worker_mesh = rmse_at_spline_stage_x0_init(
                cfg,
                sk_canon,
                n_on_canon,
                L_on_canon,
                d_final,
                relax_n_mono=False,
            )
            if self.logger:
                log_rmse_mesh_bridge_diagnosis(
                    cfg,
                    sk_final,
                    n_phys_final,
                    L_nodes_final,
                    sk_canon,
                    n_on_canon,
                    L_on_canon,
                    d_final,
                    self.logger,
                    relax_preview_mono=relax_si_mono,
                )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            if self.logger:
                self.logger.warning(
                    "[INDEX_SPLINE.SMART_INIT] keep-preview recalculation failed on worker mesh: %s",
                    exc,
                )
            rmse_worker_mesh = rmse_preview_mesh

        self._preview_ret = (
            sk_final.copy(),
            n_phys_final.copy(),
            L_nodes_final.copy(),
            d_final,
            float(rmse_worker_mesh),
        )

        cfg.smart_preview_node_override = (n_phys_final.copy(), L_nodes_final.copy())
        cfg.smart_preview_exact_sigma_knots = sk_final.copy()
        cfg.smart_preview_exact_n_L = (n_phys_final.copy(), L_nodes_final.copy())
        cfg.smart_preview_d_nm_override = d_final
        cfg.smart_preview_accepted_rmse = float(rmse_worker_mesh)

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SMART_INIT_DEEP, bool(chk_si_deep is not None and chk_si_deep.isChecked())
        )
        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(
            _QS_SMART_INIT_TWO_PHASE, bool(chk_si_two_phase is not None and chk_si_two_phase.isChecked())
        )

        cfg.gui_run_pglobal_opt_in = False
        cfg.spline_local_only = True
        cfg.spline_smart_init_deep_two_phase = False

        if self.logger:
            self.logger.info(
                "GUI Smart Init [Keep] | retained preview transferred to worker in forced local-only mode."
            )
            _k_gui = int(sk_final.size)
            _k_wrk = int(sk_canon_keep.size) if sk_canon_keep is not None else _k_gui
            self.logger.info(
                "[INDEX_SPLINE.SMART_INIT] keep-preview reference | preview_rmse=%.6f (k=%d) -> worker_rmse=%.6f (k=%d) | worker uses the second value for optimization",
                rmse_preview_mesh,
                _k_gui,
                rmse_worker_mesh,
                _k_wrk,
            )

        from certus.spline.spline_workers import _pack_spline_stage_result
        from certus.spline.spline_objective import physical_nodes_to_x_slice_n

        n_xi = physical_nodes_to_x_slice_n(n_phys_final, sk_final, cfg.n_mono_band_nm)
        x_final = np.concatenate(([d_final], n_xi, L_nodes_final))
        ui_snap = _pack_spline_stage_result(cfg, sk_final, x_final, float(rmse_worker_mesh**2), 0, 0)
        self._plot_result(ui_snap, plot_source="smart_init_retenir")
        dlg.accept()

    def _execute_smart_init_preset_logic(
        self, cfg: "SplineOptConfig", projector: Any, relax_si_mono: bool, state: "_SmartInitState"
    ) -> None:
        target_sk = np.asarray(state.sk, dtype=np.float64).ravel()
        new_sk, new_n, new_L, new_d = projector(target_sk)
        state.sk = np.asarray(new_sk, dtype=np.float64).ravel().copy()
        state.n_phys = new_n.copy()
        state.L_nodes = new_L.copy()

        if getattr(self, "sk_sorted", None) is not None:
            try:
                _ss = np.asarray(self.sk_sorted, dtype=np.float64).ravel()
                if _ss.size == state.sk.size:
                    self.sk_sorted[:] = state.sk
            except (TypeError, ValueError, IndexError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        from scipy.optimize import minimize_scalar

        def obj_d_only(dv: float) -> float:
            _, rm = rmse_at_spline_stage_x0_init(
                cfg, state.sk, state.n_phys, state.L_nodes, float(dv), relax_n_mono=relax_si_mono
            )
            return float(rm)

        res_d = minimize_scalar(obj_d_only, bounds=(cfg.d_lo, cfg.d_hi), method="bounded", options={"xatol": 0.01})
        if res_d.success:
            state.preview_d_nm = float(res_d.x)

    def _execute_smart_init_run_auto(
        self,
        cfg: "SplineOptConfig",
        row: int,
        is_ln_k: bool,
        L_lo_g: float,
        L_hi_g: float,
        relax_si_mono: bool,
        state: "_SmartInitState",
    ) -> str | None:
        cur_sk = np.asarray(state.sk, dtype=np.float64).ravel()
        n_loc = np.asarray(state.n_phys, dtype=np.float64).ravel()
        L_loc = np.asarray(state.L_nodes, dtype=np.float64).ravel()

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            spn = getattr(self, "smart_preview_n_phys", None)
            spl = getattr(self, "smart_preview_L_nodes", None)
            if spn is not None and spl is not None:
                spn_a = np.asarray(spn, dtype=np.float64).ravel()
                spl_a = np.asarray(spl, dtype=np.float64).ravel()
                if spn_a.size == spl_a.size == cur_sk.size:
                    n_loc = spn_a.copy()
                    L_loc = spl_a.copy()

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            sk_snap = getattr(self, "_si_mesh_sk_snap", None)
            if sk_snap is not None:
                sk_snap = np.asarray(sk_snap, dtype=np.float64).ravel()
                if sk_snap.size >= 2 and sk_snap.size == n_loc.size == L_loc.size and cur_sk.size >= 2:
                    n_loc, L_loc = interp_n_L_pwlnk_to_sigmas(sk_snap, n_loc, L_loc, cur_sk)

        if n_loc.size != cur_sk.size or L_loc.size != cur_sk.size:
            return f"Inconsistent sigma / n / ln k (k_sigma={cur_sk.size}, len_n={n_loc.size}, len_l={L_loc.size}). Try again after recalculation."

        try:
            out = smart_init_sweep_node_thickness_rmse(
                cfg,
                cur_sk,
                n_loc,
                L_loc,
                int(row),
                is_ln_k=bool(is_ln_k),
                d_lo=float(cfg.d_lo),
                d_hi=float(cfg.d_hi),
                L_lo=L_lo_g,
                L_hi=L_hi_g,
                time_budget_s=2.9,
                d_nm_current=float(state.preview_d_nm),
                relax_n_mono=relax_si_mono,
            )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            return str(exc)

        state.n_phys = np.asarray(out["n_nodes_physical"], dtype=np.float64).ravel().copy()
        state.L_nodes = np.asarray(out["L_nodes"], dtype=np.float64).ravel().copy()
        state.preview_d_nm = float(out["d_nm"])
        return None

    def _execute_smart_init_recall_best(self, state: _SmartInitState) -> str | None:
        if not np.isfinite(state.best_rmse):
            return None
        cur_k = int(np.asarray(state.sk).size)
        if state.best_n.size != cur_k or state.best_L.size != cur_k:
            return f"The sigma mesh has changed since this 'best': impossible to recall n and ln k (best K={state.best_n.size}, current K={cur_k})."
        state.n_phys = state.best_n.copy()
        state.L_nodes = state.best_L.copy()
        return None

    def _execute_smart_init_recalc_logic(
        self, cfg: "SplineOptConfig", grids: dict[str, Any], relax_si_mono: bool, state: "_SmartInitState"
    ) -> dict[str, Any] | None:
        out = recalc_smart_init_spectral_preview(
            cfg,
            state.sk,
            state.n_phys,
            state.L_nodes,
            grids,
            d_nm_fixed=float(state.preview_d_nm),
            relax_n_mono=relax_si_mono,
        )
        if out is None:
            return None

        state.n_phys = np.asarray(out["n_nodes_physical"], dtype=np.float64).ravel().copy()
        state.L_nodes = np.asarray(out["L_nodes"], dtype=np.float64).ravel().copy()
        state.preview_d_nm = float(out["d_best_nm"])
        state.sk = np.asarray(out.get("sigma_knots", state.sk), dtype=np.float64).ravel().copy()

        self.smart_preview_sk_arr = state.sk.copy()
        self.smart_preview_n_phys = state.n_phys.copy()
        self.smart_preview_L_nodes = state.L_nodes.copy()
        self._si_mesh_sk_snap = state.sk.copy()

        state.current_t_th = np.asarray(out["t_theo"], dtype=np.float64).ravel()

        _, rm_depart = rmse_at_spline_stage_x0_init(
            cfg, state.sk, state.n_phys, state.L_nodes, state.preview_d_nm, relax_n_mono=relax_si_mono
        )
        state.current_rmse = rm_depart
        if state.current_rmse < state.best_rmse:
            state.best_rmse = state.current_rmse
            state.best_n = state.n_phys.copy()
            state.best_L = state.L_nodes.copy()

        return out

    def _pick_best_smart_init_material_preset(
        self, cfg: "SplineOptConfig", target_sk: np.ndarray, preview_d_nm: float, relax_si_mono: bool
    ) -> tuple[str, float, float] | None:
        try:
            picked = pick_best_manual_material_preset(
                cfg, target_sk, d_nm_hint=float(preview_d_nm), relax_n_mono=relax_si_mono
            )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            if self.logger:
                self.logger.warning("INDEX_SPLINE [Smart Init] Auto-selection of 3 material presets: %s", exc)
            return None

        if picked is None:
            if self.logger:
                self.logger.info(
                    "INDEX_SPLINE [Smart Init] Material presets: no valid RMSE score - keeping current profile."
                )
            return None

        winner, rm_w, d_w, _nw, _Lw, score_rows = picked
        if self.logger:
            parts = [f"{pid}->RMSE={rm:.6f}" for pid, rm in score_rows]
            self.logger.info(
                "INDEX_SPLINE [Smart Init] Material presets (d mini-opt for each): %s | kept **%s** (RMSE=%.6f, d~%.2f nm)",
                " ; ".join(parts),
                winner,
                rm_w,
                d_w,
            )
        return winner, rm_w, d_w

    def _load_smart_init_index_config(
        self,
        state: "_SmartInitState",
        dlg,
        L_lo_g: float,
        L_hi_g: float,
        d_lo_nm: float,
        d_hi_nm: float,
        refresh_knot_lines_and_ui_fn: "Callable[[], None]",
        btn_load_cfg,
    ) -> None:
        """Load a Smart Init index configuration from JSON file and update state."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            dlg, "Load index config (Smart Init)", "", "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from certus.utils.certus_result_schema import validate_project_dict
            validate_project_dict(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(dlg, "Load index config", f"Load failed: {exc}")
            return
        except Exception as exc:
            from certus.utils.errors import CorruptedProjectError
            if isinstance(exc, CorruptedProjectError):
                QMessageBox.warning(dlg, "Load failed - Invalid Config", exc.full_message)
            else:
                QMessageBox.warning(dlg, "Load index config", f"Validation error: {exc}")
            return

        loaded_sk = np.asarray(data.get("sigma_knots"), dtype=np.float64).ravel()
        loaded_n = np.asarray(data.get("n_nodes_physical"), dtype=np.float64).ravel()
        loaded_L = np.asarray(data.get("L_nodes"), dtype=np.float64).ravel()
        loaded_d = float(data.get("d_nm"))


        order = np.argsort(loaded_sk, kind="mergesort")
        loaded_sk = loaded_sk[order]
        loaded_n = np.clip(loaded_n[order], N_MIN_LIMIT, N_MAX_LIMIT)
        loaded_L = np.clip(loaded_L[order], L_lo_g, L_hi_g)
        loaded_d = float(np.clip(loaded_d, d_lo_nm, d_hi_nm))

        state.sk = loaded_sk.copy()
        state.n_phys = loaded_n.copy()
        state.L_nodes = loaded_L.copy()
        state.preview_d_nm = loaded_d

        self.smart_preview_sk_arr = state.sk.copy()
        self.smart_preview_n_phys = state.n_phys.copy()
        self.smart_preview_L_nodes = state.L_nodes.copy()
        self.smart_preview_d_nm = float(state.preview_d_nm)
        self.smart_preview_sig2 = self.smart_preview_sk_arr ** 2

        refresh_knot_lines_and_ui_fn()
        from PyQt6.QtCore import QTimer
        btn_load_cfg.setText("Loaded")
        QTimer.singleShot(1200, lambda: btn_load_cfg.setText("Load"))

    def _apply_smart_init_preset(
        self,
        state: "_SmartInitState",
        cfg: "SplineOptConfig",
        projector: "Callable",
        relax_si_mono: bool,
        refresh_knot_lines_and_ui_fn: "Callable[[], None]",
        feedback_btn=None,
        idle_label: str = "",
    ) -> None:
        """Apply a material preset projector and refresh the dialog UI."""
        self._execute_smart_init_preset_logic(cfg, projector, relax_si_mono, state)

        state.sk = self.smart_preview_sk_arr = state.sk.copy()
        state.n_phys = self.smart_preview_n_phys = state.n_phys.copy()
        state.L_nodes = self.smart_preview_L_nodes = state.L_nodes.copy()
        state.preview_d_nm = self.smart_preview_d_nm = state.preview_d_nm
        self.smart_preview_sig2 = self.smart_preview_sk_arr ** 2

        refresh_knot_lines_and_ui_fn()

        if feedback_btn is not None:
            from PyQt6.QtCore import QTimer
            feedback_btn.setText(f"OK - {len(state.sk)} nodes")
            QTimer.singleShot(1500, lambda b=feedback_btn, t=idle_label: b.setText(t))

    def _execute_smart_init_do_recalc(
        self,
        state: "_SmartInitState",
        cfg: "SplineOptConfig",
        grids,
        relax_si_mono: bool,
        sk_arr: np.ndarray,
        curve_editor_holder: list,
        ui_callbacks: dict,
    ) -> None:
        """Recompute spectra from current n/L/d state and refresh all UI elements.

        ui_callbacks must contain: 'update_main_x_axes', 'sync_knot_labels',
        'refresh_stats', 'refresh_nk_plots_aux', 'refresh_nk_plots_mon'.
        """
        cur_sk = getattr(self, "smart_preview_sk_arr", sk_arr)
        state.sk = cur_sk

        out = self._execute_smart_init_recalc_logic(cfg, grids, relax_si_mono, state)
        if out is None:
            return

        ui_callbacks["update_main_x_axes"]()
        ui_callbacks["sync_knot_labels"]()
        ui_callbacks["refresh_stats"](state.preview_d_nm, state.current_rmse)

        lam_u_src = out.get("lam_nm")
        if lam_u_src is None:
            lam_u_src = np.asarray(cfg.lam_nm, dtype=np.float64).ravel()
            if self.logger:
                self.logger.warning("Smart-init preview: out.lam_nm missing; fallback to cfg.lam_nm.")
        lam_u = np.asarray(lam_u_src, dtype=np.float64).ravel()
        ou = np.argsort((1.0 / np.maximum(lam_u, 1e-9)) ** 2)

        if "n_lam" in out and "k_lam" in out:
            n_lam_u = np.asarray(out["n_lam"], dtype=np.float64).ravel()
            k_lam_u = np.asarray(out["k_lam"], dtype=np.float64).ravel()
            ui_callbacks["refresh_nk_plots_aux"](lam_u[ou], n_lam_u[ou], k_lam_u[ou])
            ui_callbacks["refresh_nk_plots_mon"](lam_u[ou], n_lam_u[ou], k_lam_u[ou])

        for _ce in curve_editor_holder:
            try:
                _ce.refresh_plots()
            except (AttributeError, RuntimeError):
                logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

    def _smart_mesh_objective_lam_mask_float(self, lam_r: np.ndarray) -> np.ndarray:
        """Same lambda mask as the spline objective on grid ``lam_r`` (result / SMART)."""

        lam_r = np.asarray(lam_r, dtype=np.float64).ravel()

        cfg_opt = self._build_opt_config(notify=False)

        if cfg_opt is not None:
            return objective_lam_mask_on_target_grid(cfg_opt, lam_r).astype(np.float64, copy=False)

        rw = self._rmse_fit_lambda_tuple_for_report()

        m = np.isfinite(lam_r).astype(np.float64, copy=False)

        if rw is not None:
            lo = float(min(rw[0], rw[1]))

            hi = float(max(rw[0], rw[1]))

            m *= ((lam_r >= lo) & (lam_r <= hi)).astype(np.float64)

        return m

    @pyqtSlot(object)
    def _on_smart_preview_requested(self, payload: object) -> None:

        # FIX: After dict->SmartInitPayload conversion, isinstance(payload, dict) was always False
        # causing the dialog to NEVER open. Normalize payload then show dialog unconditionally.
        if isinstance(payload, dict):
            payload = SmartInitPayload.from_dict(payload)

        logger.info(
            "Smart Init GUI slot enter | payload_type=%s | has_wait_event=%s | thread=%s",
            type(payload).__name__,
            getattr(self, "_preview_wait_event", None) is not None,
            type(QThread.currentThread()).__name__,
        )

        try:
            if type(payload).__name__ == "SmartInitPayload":
                logger.info(
                    "Smart Init GUI slot: opening dialog | K_sigma=%d | incoming_d_best_nm=%.6f | preview_shown=%s",
                    int(np.asarray(payload.sigma_knots, dtype=np.float64).size),
                    float(payload.d_best_nm),
                    bool(getattr(self, "_preview_result", None) is not None),
                )

                self._preview_result = bool(self._show_smart_init_preview_dialog(payload))

                logger.info(
                    "Smart Init GUI slot: dialog returned preview_result=%s | preview_ret=%s | wait_event=%s",
                    bool(self._preview_result),
                    getattr(self, "_preview_ret", None) is not None,
                    getattr(self, "_preview_wait_event", None) is not None,
                )

            else:
                logger.warning(
                    "Smart Init preview: unexpected payload type %s, skipping dialog.", type(payload).__name__
                )

                self._preview_result = False
                logger.error("Smart Init preview: unexpected payload, aborting preview safely")

        except NUMERICAL_FAULT_EXCEPTIONS :
            logger.exception("Smart Init preview: GUI error (full traceback)")

            self._preview_result = False

        finally:
            if self._preview_wait_event is not None:
                logger.info(
                    "Smart Init GUI slot: releasing wait_event | preview_result=%s | preview_ret=%s",
                    bool(getattr(self, "_preview_result", False)),
                    getattr(self, "_preview_ret", None) is not None,
                )
                self._preview_wait_event.set()
            else:
                logger.warning("Smart Init GUI slot finished without wait_event; preview stage cannot block safely")
