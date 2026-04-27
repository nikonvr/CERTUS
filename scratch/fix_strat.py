
import re
import os

with open('CERTUS_STRAT.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Fix indentation of the block that was messed up
# Looking for lines with 16 spaces that should have 12 spaces in _run_step_23_full
# Specifically after 'accumulated_strategies_results = self._execute_phase_b_exploration(...)'

target = """            accumulated_strategies_results = self._execute_phase_b_exploration(
                pre_calc_data=pre_calc_data,
                nucleation_info=nucleation_info,
                stats_queue=stats_queue,
                live_preview_queue=live_preview_queue,
            )"""

new_block = """            accumulated_strategies_results = self._execute_phase_b_exploration(
                pre_calc_data=pre_calc_data,
                nucleation_info=nucleation_info,
                stats_queue=stats_queue,
                live_preview_queue=live_preview_queue,
            )

            self.signals.progress.emit(100, "Finalizing results...")
            gc.collect()

            if not accumulated_strategies_results:
                raise RuntimeError("No strategies found.")

            accumulated_strategies_results.sort(key=lambda x: x["robustness_score"])

            if self.timing_logger:
                self.timing_logger.end_global("STRAT_Workflow")

            self.signals.show_strategies_table.emit(accumulated_strategies_results)

            best_res = accumulated_strategies_results[0]
            sim_context = pre_calc_data.copy()
            sim_context["blocks"] = best_res["strategy"]["blocks"]
            sim_context["all_strategies"] = [
                r["strategy"] for r in accumulated_strategies_results
            ]

            final_complete_structure = {
                "results_per_noise": best_res["results_per_noise"],
                "optimal_blocks": best_res["strategy"]["blocks"],
                "best_strategy": best_res["strategy"],
                "all_strategies_results": accumulated_strategies_results,
            }
"""

# We also need to fix the rest of the function (the plotting and excel export part)
# which is also likely over-indented now.

# Let's find the whole over-indented block and fix it.
pattern = r'            self\.signals\.progress\.emit\(100, "Finalizing results\.\.\."\)\n            gc\.collect\(\)\n\n            if not accumulated_strategies_results:\n                raise RuntimeError\("No strategies found\."\)\n\n                accumulated_strategies_results\.sort\(key=lambda x: x\["robustness_score"\]\)(.*?)\n                self\.signals\.finished\.emit\('
# This is complex. Let's just do a simpler string replacement for the over-indented lines.

src = src.replace('                accumulated_strategies_results.sort', '            accumulated_strategies_results.sort')
src = src.replace('                if self.timing_logger:', '            if self.timing_logger:')
src = src.replace('                    self.timing_logger.end_global', '                self.timing_logger.end_global')
src = src.replace('                self.signals.show_strategies_table', '            self.signals.show_strategies_table')
src = src.replace('                best_res = accumulated_strategies_results', '            best_res = accumulated_strategies_results')
src = src.replace('                sim_context = pre_calc_data.copy()', '            sim_context = pre_calc_data.copy()')
src = src.replace('                sim_context["blocks"]', '            sim_context["blocks"]')
src = src.replace('                sim_context["all_strategies"] = [', '            sim_context["all_strategies"] = [')
src = src.replace('                    r["strategy"] for r in accumulated_strategies_results', '                r["strategy"] for r in accumulated_strategies_results')
src = src.replace('                ]', '            ]')
src = src.replace('                final_complete_structure = {', '            final_complete_structure = {')
src = src.replace('                    "results_per_noise": best_res["results_per_noise"],', '                "results_per_noise": best_res["results_per_noise"],')
src = src.replace('                    "optimal_blocks": best_res["strategy"]["blocks"],', '                "optimal_blocks": best_res["strategy"]["blocks"],')
src = src.replace('                    "best_strategy": best_res["strategy"],', '                "best_strategy": best_res["strategy"],')
src = src.replace('                    "all_strategies_results": accumulated_strategies_results,', '                "all_strategies_results": accumulated_strategies_results,')
src = src.replace('                }', '            }')
src = src.replace('                if self.params.get("show_plots", True):', '            if self.params.get("show_plots", True):')
src = src.replace('                    try:', '                try:')
src = src.replace('                        heatmap_data = pre_calc_data.get("raw_results_thickness", None)', '                    heatmap_data = pre_calc_data.get("raw_results_thickness", None)')
src = src.replace('                        strat_data = {', '                    strat_data = {')
src = src.replace('                            "strategies": accumulated_strategies_results,', '                        "strategies": accumulated_strategies_results,')
src = src.replace('                            "p_thick_nominal": pre_calc_data["p_thick_nominal"],', '                        "p_thick_nominal": pre_calc_data["p_thick_nominal"],')
src = src.replace('                            "heatmap_data": heatmap_data,', '                        "heatmap_data": heatmap_data,')
src = src.replace('                        }', '                    }')
src = src.replace('                        self.signals.plot.emit(strat_data, "block_assignments")', '                    self.signals.plot.emit(strat_data, "block_assignments")')
src = src.replace('                    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:', '                except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:')
src = src.replace('                        self.params["logger"].warning(f"Plotting error: {e}")', '                    self.params["logger"].warning(f"Plotting error: {e}")')
src = src.replace('                    best_noise_results = _get_best_noise_results(best_res, self.params["logger"])', '                best_noise_results = _get_best_noise_results(best_res, self.params["logger"])')
src = src.replace('                    if best_noise_results:', '                if best_noise_results:')
src = src.replace('                        wl_arr = arange_inclusive(', '                    wl_arr = arange_inclusive(')
src = src.replace('                            self.params["wl_range"][0],', '                        self.params["wl_range"][0],')
src = src.replace('                            self.params["wl_range"][1],', '                        self.params["wl_range"][1],')
src = src.replace('                            self.params["wl_step"],', '                        self.params["wl_step"],')
src = src.replace('                        )', '                    )')
src = src.replace('                        local_db = self.params.get("materials_db_instance")', '                    local_db = self.params.get("materials_db_instance")')
src = src.replace('                        nH_arr = get_refractive_clues_vectorized(', '                    nH_arr = get_refractive_clues_vectorized(')
src = src.replace('                            self.params["nH_id"], wl_arr, db_instance=local_db', '                        self.params["nH_id"], wl_arr, db_instance=local_db')
src = src.replace('                        ).astype(np.complex128)', '                    ).astype(np.complex128)')
src = src.replace('                        nL_arr = get_refractive_clues_vectorized(', '                    nL_arr = get_refractive_clues_vectorized(')
src = src.replace('                            self.params["nL_id"], wl_arr, db_instance=local_db', '                        self.params["nL_id"], wl_arr, db_instance=local_db')
src = src.replace('                        nSub_arr = get_refractive_clues_vectorized(', '                    nSub_arr = get_refractive_clues_vectorized(')
src = src.replace('                            self.params["nSub_id"], wl_arr, db_instance=local_db', '                        self.params["nSub_id"], wl_arr, db_instance=local_db')
src = src.replace('                        _, T_clean_batch = calculate_RT_batch_kernel(', '                    _, T_clean_batch = calculate_RT_batch_kernel(')
src = src.replace('                            wl_arr,', '                        wl_arr,')
src = src.replace('                            nH_arr,', '                        nH_arr,')
src = src.replace('                            nL_arr,', '                        nL_arr,')
src = src.replace('                            nSub_arr,', '                        nSub_arr,')
src = src.replace('                            np.array(pre_calc_data["p_thick_nominal"], dtype=np.float64).reshape(', '                        np.array(pre_calc_data["p_thick_nominal"], dtype=np.float64).reshape(')
src = src.replace('                                1, -1', '                            1, -1')
src = src.replace('                            ),', '                        ),')
src = src.replace('                        nominal_results_display = {', '                    nominal_results_display = {')
src = src.replace('                            "wavelengths": wl_arr,', '                        "wavelengths": wl_arr,')
src = src.replace('                            "T_spectral_nominal": T_clean_batch[0],', '                        "T_spectral_nominal": T_clean_batch[0],')
src = src.replace('                        robust_data_pack = {', '                    robust_data_pack = {')
src = src.replace('                            "nominal": nominal_results_display,', '                        "nominal": nominal_results_display,')
src = src.replace('                            "best_noise": best_noise_results,', '                        "best_noise": best_noise_results,')
src = src.replace('                            "opti": sim_context,', '                        "opti": sim_context,')
src = src.replace('                        self.signals.plot.emit(robust_data_pack, "robustness_popout")', '                    self.signals.plot.emit(robust_data_pack, "robustness_popout")')
src = src.replace('                if self.params.get("export_excel", True):', '            if self.params.get("export_excel", True):')
src = src.replace('                    excel_data = generate_excel_report(', '                excel_data = generate_excel_report(')
src = src.replace('                        nominal_res, sim_context, final_complete_structure, self.params', '                    nominal_res, sim_context, final_complete_structure, self.params')
src = src.replace('                    best_rmse = 0.0', '                best_rmse = 0.0')
src = src.replace('                    if (', '                if (')
src = src.replace('                        "all_strategies_results" in final_complete_structure', '                    "all_strategies_results" in final_complete_structure')
src = src.replace('                        and final_complete_structure["all_strategies_results"]', '                    and final_complete_structure["all_strategies_results"]')
src = src.replace('                        best_rmse = final_complete_structure["all_strategies_results"][0].get(', '                    best_rmse = final_complete_structure["all_strategies_results"][0].get(')
src = src.replace('                            "robustness_score", 0.0', '                        "robustness_score", 0.0')
src = src.replace('                    metadata = {', '                metadata = {')
src = src.replace('                        "rmse": best_rmse,', '                    "rmse": best_rmse,')
src = src.replace('                        "strategies_count": len(', '                    "strategies_count": len(')
src = src.replace('                            final_complete_structure.get("all_strategies_results", [])', '                        final_complete_structure.get("all_strategies_results", [])')
src = src.replace('                        "params": {', '                    "params": {')
src = src.replace('                            k: v', '                        k: v')
src = src.replace('                            for k, v in self.params.items()', '                        for k, v in self.params.items()')
src = src.replace('                            if k not in ["logger", "materials_db", "clues_at_wl"]', '                        if k not in ["logger", "materials_db", "clues_at_wl"]')
src = src.replace('                        },', '                    },')
src = src.replace('                    self.signals.excel_ready.emit(excel_data, metadata)', '                self.signals.excel_ready.emit(excel_data, metadata)')
src = src.replace('                self.signals.finished.emit(', '            self.signals.finished.emit(')
src = src.replace('                    WorkerThreadResult.for_step_23(', '                WorkerThreadResult.for_step_23(')
src = src.replace('                        opti_results=sim_context,', '                    opti_results=sim_context,')
src = src.replace('                        final_results=final_complete_structure,', '                    final_results=final_complete_structure,')
src = src.replace('                    ).to_legacy_dict()', '                ).to_legacy_dict()')


# Add the function definition at the end of class or after _run_step_23_full
# We'll just append it to the file and then move it if needed, or just insert it before closeEvent
new_fn = """
    def _execute_phase_b_exploration(
        self,
        pre_calc_data: dict[str, Any],
        nucleation_info: dict[str, Any],
        stats_queue: mp.Queue,
        live_preview_queue: mp.Queue,
    ) -> list[dict[str, Any]]:
        \"\"\"
        Execute Phase B: Deep Exploration loop.
        \"\"\"
        import gc
        import concurrent.futures
        from concurrent.futures import ThreadPoolExecutor

        num_layers = pre_calc_data["num_layers"]
        blocks_range = _compute_blocks_range_for_params(num_layers, self.params, dense=True)
        n_screen = int(self.params.get("n_screen_runs", 25))
        k_keep = int(self.params.get("k_keep_survivors", 10))
        n_full = int(self.params.get("robustness_num_runs", 150))

        self.params["logger"].info(f"🔄 PHASE B: Deep Exploration ({len(blocks_range)} steps) - HYBRID ENGINE...")

        cost_map_sq_clean = {
            l: {x["wl"]: x["cost"] for x in items}
            for l, items in pre_calc_data["raw_results_sq"].items()
        }
        materials_db = self.params.get("materials_db") or APP_CONTEXT.get("materials_db")

        with SharedIndicesManager(pre_calc_data["clues_at_wl"]) as shm_manager, \\
             SharedArrayManager(pre_calc_data["nominal_matrix_cache"]) as shm_matrix:

            minimized_context = {
                "raw_results_thickness": pre_calc_data["raw_results_thickness"],
                "raw_results_sq": pre_calc_data["raw_results_sq"],
                "num_layers": pre_calc_data["num_layers"],
                "p_thick_nominal": pre_calc_data["p_thick_nominal"],
                "shared_clues_info": shm_manager.get_context_info(),
                "shared_matrix_info": shm_matrix.get_context_info(),
                "all_wls": pre_calc_data["all_wls"],
                "materials_data": materials_db.data if materials_db else {},
                "nH_id": self.params["nH_id"],
                "nL_id": self.params["nL_id"],
                "nSub_id": self.params["nSub_id"],
                "l0": self.params["l0"],
                "sym_bonus_map": pre_calc_data.get("sym_bonus_map", {}),
                "sym_layer_importance": pre_calc_data.get("sym_layer_importance", {}),
            }

            params_for_pool = {
                k: v for k, v in self.params.items()
                if k not in ["logger", "materials_db", "gui_parent", "worker_signals", "materials_db_instance"]
            }

            accumulated_strategies_results = []
            inherited_strategies = []
            stop_check = lambda: self.params.get("stop_requested", False)

            def monitor_live_feed():
                import time
                last_update = 0.0
                last_full_package = None
                LIVE_REFRESH_INTERVAL = 2.0
                while True:
                    try:
                        item = None
                        try:
                            while not live_preview_queue.empty():
                                item = live_preview_queue.get_nowait()
                        except (BrokenPipeError, OSError):
                            pass
                        if item is None:
                            try:
                                item = live_preview_queue.get(timeout=0.5)
                            except Exception:
                                break
                        if item == "STOP":
                            break
                        now = time.time()
                        if item:
                            if now - last_update > 0.4:
                                full_package = {
                                    "strategy": item["strategy"],
                                    "robustness_score": item["robustness_score"],
                                    "p_thick_nominal": pre_calc_data["p_thick_nominal"],
                                    "clues_at_wl": pre_calc_data["clues_at_wl"],
                                }
                                last_full_package = full_package
                                self.signals.update_live_growth.emit(full_package)
                                last_update = now
                        elif last_full_package is not None and (now - last_update) >= LIVE_REFRESH_INTERVAL:
                            self.signals.update_live_growth.emit(last_full_package)
                            last_update = now
                    except Exception as e:
                        import logging
                        logging.error(f"[MonitorThread] Error: {e}")
                        break

            import threading
            monitor_thread = threading.Thread(target=monitor_live_feed, daemon=True)
            monitor_thread.start()

            max_workers = get_safe_worker_count()
            self.params["logger"].info(f"   Using {max_workers} parallel workers")
            executor = None
            try:
                executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    initializer=_worker_init,
                    initargs=(stats_queue, live_preview_queue),
                )
                with executor:
                    for i, n_blk in enumerate(blocks_range):
                        if stop_check():
                            self.params["logger"].warning(f"🛑 Stopping Optimization at {n_blk} blocks...")
                            break
                        self.signals.progress.emit(
                            int((i / len(blocks_range)) * 90) + 5,
                            f"Optimizing ({n_blk} blocks) - Gen {i+1}/{len(blocks_range)}",
                        )
                        args = (n_blk, minimized_context, params_for_pool, n_screen, k_keep, n_full, inherited_strategies, nucleation_info)
                        try:
                            future = executor.submit(_parallel_block_worker, args)
                            result_batch = future.result(timeout=300)
                            if int(result_batch.get("n_blk", n_blk)) != int(n_blk):
                                self.params["logger"].error(f"    [Block {n_blk}] ❌ Worker returned wrong n_blk={result_batch.get('n_blk')}")
                                inherited_strategies = []
                                continue

                            if "error" in result_batch and result_batch.get("strategies_results") == []:
                                self.params["logger"].error(f"    [Block {n_blk}] ❌ Error: {result_batch['error']}")
                                inherited_strategies = []
                            else:
                                strategies_this_step_raw = result_batch.get("strategies_results", [])
                                strategies_this_step = []
                                for s_res in strategies_this_step_raw:
                                    s = s_res.get("strategy", {}) if isinstance(s_res, dict) else {}
                                    ok, reason = _validate_strategy_blocks_contract(s, num_layers, expected_n_blocks=n_blk)
                                    if ok:
                                        strategies_this_step.append(s_res)
                                    else:
                                        self.params["logger"].warning(f"    [Block {n_blk}] Dropped invalid strategy payload: {reason}")
                                
                                accumulated_strategies_results.extend(strategies_this_step)
                                
                                if strategies_this_step:
                                    from certus_strat_service import derive_strategies_exhaustive
                                    inherited_strategies = derive_strategies_exhaustive(
                                        strategies_this_step, cost_map_sq_clean,
                                        top_k_parents=int(self.params.get("top_k_parents", 20)),
                                        max_fusions_per_parent=int(self.params.get("max_fusions_per_parent", 5)),
                                    )
                                else:
                                    inherited_strategies = []
                                del strategies_this_step
                                gc.collect()
                        except Exception as e:
                            self.params["logger"].error(f"   [Block {n_blk}] ❌ Error: {e}")
                            inherited_strategies = []
            except Exception as e:
                self.params["logger"].error(f"ProcessPoolExecutor error: {e}")
                raise
            finally:
                if executor is not None:
                    executor.shutdown(wait=True)

            live_preview_queue.put("STOP")
            monitor_thread.join()

        return accumulated_strategies_results
"""

# Insert before on_live_growth_update
src = src.replace('    def on_live_growth_update(self, strategy_data):', new_fn + '\n    def on_live_growth_update(self, strategy_data):')

with open('CERTUS_STRAT.py', 'w', encoding='utf-8') as f:
    f.write(src)
