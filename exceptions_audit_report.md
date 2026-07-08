# CERTUS - Rapport d'Audit des Blocs Try/Except

Ce rapport répertorie tous les blocs `try/except` contenant des `bare except`, des captures d'exceptions génériques (`Exception`), ou des gestions silencieuses.

**Total de blocs problématiques identifiés :** 650 répartis sur 148 fichiers.

## Table des Matières

- [certus\core\_certus_physics_impl.py](#certus\core\certusphysicsimplpy)
- [certus\core\certus_config.py](#certus\core\certusconfigpy)
- [certus\core\certus_core.py](#certus\core\certuscorepy)
- [certus\core\certus_index_objectives.py](#certus\core\certusindexobjectivespy)
- [certus\core\certus_index_solvers.py](#certus\core\certusindexsolverspy)
- [certus\core\certus_lazy_imports.py](#certus\core\certuslazyimportspy)
- [certus\core\certus_logging.py](#certus\core\certusloggingpy)
- [certus\core\certus_metrology.py](#certus\core\certusmetrologypy)
- [certus\core\certus_re_objectives.py](#certus\core\certusreobjectivespy)
- [certus\core\certus_re_solvers.py](#certus\core\certusresolverspy)
- [certus\core\certus_strat_audit.py](#certus\core\certusstratauditpy)
- [certus\core\certus_strat_consensus.py](#certus\core\certusstratconsensuspy)
- [certus\core\certus_strat_objectives.py](#certus\core\certusstratobjectivespy)
- [certus\core\certus_strat_ranking.py](#certus\core\certusstratrankingpy)
- [certus\core\certus_strat_robustness.py](#certus\core\certusstratrobustnesspy)
- [certus\core\certus_substrate_index.py](#certus\core\certussubstrateindexpy)
- [certus\metal\certus_metal_common.py](#certus\metal\certusmetalcommonpy)
- [certus\metal\pglobal_adapter.py](#certus\metal\pglobaladapterpy)
- [certus\physics\certus_optimizers.py](#certus\physics\certusoptimizerspy)
- [certus\physics\certus_strat_batch.py](#certus\physics\certusstratbatchpy)
- [certus\physics\certus_warmup.py](#certus\physics\certuswarmuppy)
- [certus\spline\certus_corridor_bootstrap.py](#certus\spline\certuscorridorbootstrappy)
- [certus\spline\certus_corridor_config.py](#certus\spline\certuscorridorconfigpy)
- [certus\spline\certus_corridor_fitter.py](#certus\spline\certuscorridorfitterpy)
- [certus\spline\certus_corridor_orchestrator_utils.py](#certus\spline\certuscorridororchestratorutilspy)
- [certus\spline\certus_corridor_utils.py](#certus\spline\certuscorridorutilspy)
- [certus\spline\certus_index_spline_config.py](#certus\spline\certusindexsplineconfigpy)
- [certus\spline\certus_index_spline_core.py](#certus\spline\certusindexsplinecorepy)
- [certus\spline\certus_index_spline_corridors.py](#certus\spline\certusindexsplinecorridorspy)
- [certus\spline\certus_index_spline_excel_export.py](#certus\spline\certusindexsplineexcelexportpy)
- [certus\spline\certus_index_spline_execution.py](#certus\spline\certusindexsplineexecutionpy)
- [certus\spline\certus_index_spline_io.py](#certus\spline\certusindexsplineiopy)
- [certus\spline\certus_index_spline_rendering.py](#certus\spline\certusindexsplinerenderingpy)
- [certus\spline\certus_index_spline_settings.py](#certus\spline\certusindexsplinesettingspy)
- [certus\spline\certus_index_spline_smart_init.py](#certus\spline\certusindexsplinesmartinitpy)
- [certus\spline\spline_finalize.py](#certus\spline\splinefinalizepy)
- [certus\spline\spline_pipeline_corridors_runner.py](#certus\spline\splinepipelinecorridorsrunnerpy)
- [certus\spline\spline_pipeline_mesh_clean.py](#certus\spline\splinepipelinemeshcleanpy)
- [certus\spline\spline_pipeline_mesh_insert.py](#certus\spline\splinepipelinemeshinsertpy)
- [certus\spline\spline_pipeline_orchestrator.py](#certus\spline\splinepipelineorchestratorpy)
- [certus\spline\spline_pipeline_utils.py](#certus\spline\splinepipelineutilspy)
- [certus\spline\spline_smart_init.py](#certus\spline\splinesmartinitpy)
- [certus\spline\spline_workers.py](#certus\spline\splineworkerspy)
- [certus\ui\certus_a11y.py](#certus\ui\certusa11ypy)
- [certus\ui\certus_animations.py](#certus\ui\certusanimationspy)
- [certus\ui\certus_base_app.py](#certus\ui\certusbaseapppy)
- [certus\ui\certus_design_ui_core.py](#certus\ui\certusdesignuicorepy)
- [certus\ui\certus_design_ui_events.py](#certus\ui\certusdesignuieventspy)
- [certus\ui\certus_design_ui_export.py](#certus\ui\certusdesignuiexportpy)
- [certus\ui\certus_design_ui_optimization.py](#certus\ui\certusdesignuioptimizationpy)
- [certus\ui\certus_design_ui_plot.py](#certus\ui\certusdesignuiplotpy)
- [certus\ui\certus_design_ui_state.py](#certus\ui\certusdesignuistatepy)
- [certus\ui\certus_design_ui_worker.py](#certus\ui\certusdesignuiworkerpy)
- [certus\ui\certus_empty_state.py](#certus\ui\certusemptystatepy)
- [certus\ui\certus_field_common.py](#certus\ui\certusfieldcommonpy)
- [certus\ui\certus_field_events_mixin.py](#certus\ui\certusfieldeventsmixinpy)
- [certus\ui\certus_field_plot.py](#certus\ui\certusfieldplotpy)
- [certus\ui\certus_field_plot_mixin.py](#certus\ui\certusfieldplotmixinpy)
- [certus\ui\certus_field_state_mixin.py](#certus\ui\certusfieldstatemixinpy)
- [certus\ui\certus_field_ui.py](#certus\ui\certusfielduipy)
- [certus\ui\certus_field_workers_mixin.py](#certus\ui\certusfieldworkersmixinpy)
- [certus\ui\certus_icons.py](#certus\ui\certusiconspy)
- [certus\ui\certus_index_spline_common.py](#certus\ui\certusindexsplinecommonpy)
- [certus\ui\certus_index_spline_eventsextras_mixin.py](#certus\ui\certusindexsplineeventsextrasmixinpy)
- [certus\ui\certus_index_spline_manualmesh_mixin.py](#certus\ui\certusindexsplinemanualmeshmixinpy)
- [certus\ui\certus_index_spline_mixins_ui.py](#certus\ui\certusindexsplinemixinsuipy)
- [certus\ui\certus_index_spline_monitor_ui.py](#certus\ui\certusindexsplinemonitoruipy)
- [certus\ui\certus_index_spline_smartinit_mixin.py](#certus\ui\certusindexsplinesmartinitmixinpy)
- [certus\ui\certus_index_spline_ui.py](#certus\ui\certusindexsplineuipy)
- [certus\ui\certus_index_ui.py](#certus\ui\certusindexuipy)
- [certus\ui\certus_index_ui_events.py](#certus\ui\certusindexuieventspy)
- [certus\ui\certus_index_ui_export.py](#certus\ui\certusindexuiexportpy)
- [certus\ui\certus_index_ui_layout.py](#certus\ui\certusindexuilayoutpy)
- [certus\ui\certus_index_ui_plot.py](#certus\ui\certusindexuiplotpy)
- [certus\ui\certus_index_ui_worker.py](#certus\ui\certusindexuiworkerpy)
- [certus\ui\certus_manual_sigma_knot_dialog.py](#certus\ui\certusmanualsigmaknotdialogpy)
- [certus\ui\certus_onboarding.py](#certus\ui\certusonboardingpy)
- [certus\ui\certus_plot.py](#certus\ui\certusplotpy)
- [certus\ui\certus_re_excel_mixin.py](#certus\ui\certusreexcelmixinpy)
- [certus\ui\certus_re_layout_mixin.py](#certus\ui\certusrelayoutmixinpy)
- [certus\ui\certus_re_state_mixin.py](#certus\ui\certusrestatemixinpy)
- [certus\ui\certus_re_table_mixin.py](#certus\ui\certusretablemixinpy)
- [certus\ui\certus_re_workers_mixin.py](#certus\ui\certusreworkersmixinpy)
- [certus\ui\certus_recent.py](#certus\ui\certusrecentpy)
- [certus\ui\certus_recent_strip.py](#certus\ui\certusrecentstrippy)
- [certus\ui\certus_shortcuts_overlay.py](#certus\ui\certusshortcutsoverlaypy)
- [certus\ui\certus_smart_init_curve_editor.py](#certus\ui\certussmartinitcurveeditorpy)
- [certus\ui\certus_spectrum_eval_ui.py](#certus\ui\certusspectrumevaluipy)
- [certus\ui\certus_splash.py](#certus\ui\certussplashpy)
- [certus\ui\certus_strat_common.py](#certus\ui\certusstratcommonpy)
- [certus\ui\certus_strat_json_ui.py](#certus\ui\certusstratjsonuipy)
- [certus\ui\certus_strat_mixins_ui.py](#certus\ui\certusstratmixinsuipy)
- [certus\ui\certus_strat_plots_ui.py](#certus\ui\certusstratplotsuipy)
- [certus\ui\certus_strat_table_ui.py](#certus\ui\certusstrattableuipy)
- [certus\ui\certus_strat_thickness_ui.py](#certus\ui\certusstratthicknessuipy)
- [certus\ui\certus_strat_ui.py](#certus\ui\certusstratuipy)
- [certus\ui\certus_strat_ui_events.py](#certus\ui\certusstratuieventspy)
- [certus\ui\certus_strat_ui_export.py](#certus\ui\certusstratuiexportpy)
- [certus\ui\certus_strat_ui_plot.py](#certus\ui\certusstratuiplotpy)
- [certus\ui\certus_strat_ui_state.py](#certus\ui\certusstratuistatepy)
- [certus\ui\certus_strat_ui_worker.py](#certus\ui\certusstratuiworkerpy)
- [certus\ui\certus_strat_welcome_ui.py](#certus\ui\certusstratwelcomeuipy)
- [certus\ui\certus_substrate_presenter.py](#certus\ui\certussubstratepresenterpy)
- [certus\ui\certus_substrate_ui.py](#certus\ui\certussubstrateuipy)
- [certus\ui\certus_svg.py](#certus\ui\certussvgpy)
- [certus\ui\certus_theme.py](#certus\ui\certusthemepy)
- [certus\ui\certus_toast_stack.py](#certus\ui\certustoaststackpy)
- [certus\ui\certus_tooltips.py](#certus\ui\certustooltipspy)
- [certus\ui\certus_tours_catalog.py](#certus\ui\certustourscatalogpy)
- [certus\ui\certus_ui_shared.py](#certus\ui\certusuisharedpy)
- [certus\ui\certus_ui_utils.py](#certus\ui\certusuiutilspy)
- [certus\ui\certus_ui_widgets_cards.py](#certus\ui\certusuiwidgetscardspy)
- [certus\ui\certus_ui_widgets_layout.py](#certus\ui\certusuiwidgetslayoutpy)
- [certus\ui\certus_ui_widgets_utils.py](#certus\ui\certusuiwidgetsutilspy)
- [certus\ui\certus_worker_manager.py](#certus\ui\certusworkermanagerpy)
- [certus\utils\certus_badges.py](#certus\utils\certusbadgespy)
- [certus\utils\certus_command_palette.py](#certus\utils\certuscommandpalettepy)
- [certus\utils\certus_curve_smoother.py](#certus\utils\certuscurvesmootherpy)
- [certus\utils\certus_data.py](#certus\utils\certusdatapy)
- [certus\utils\certus_design_services.py](#certus\utils\certusdesignservicespy)
- [certus\utils\certus_export.py](#certus\utils\certusexportpy)
- [certus\utils\certus_index_utils.py](#certus\utils\certusindexutilspy)
- [certus\utils\certus_progress_tracker.py](#certus\utils\certusprogresstrackerpy)
- [certus\utils\certus_re_helpers.py](#certus\utils\certusrehelperspy)
- [certus\utils\certus_reports.py](#certus\utils\certusreportspy)
- [certus\utils\certus_reset_framework.py](#certus\utils\certusresetframeworkpy)
- [certus\utils\certus_sample_data.py](#certus\utils\certussampledatapy)
- [certus\utils\certus_services.py](#certus\utils\certusservicespy)
- [certus\utils\certus_skeleton.py](#certus\utils\certusskeletonpy)
- [certus\utils\certus_spectral_preproc.py](#certus\utils\certusspectralpreprocpy)
- [certus\utils\certus_spline_report.py](#certus\utils\certussplinereportpy)
- [certus\utils\certus_strat_context.py](#certus\utils\certusstratcontextpy)
- [certus\utils\certus_strat_service.py](#certus\utils\certusstratservicepy)
- [certus\utils\certus_strat_stability.py](#certus\utils\certusstratstabilitypy)
- [certus\utils\certus_validation.py](#certus\utils\certusvalidationpy)
- [certus\utils\errors.py](#certus\utils\errorspy)
- [certus\workers\certus_design_worker_utils.py](#certus\workers\certusdesignworkerutilspy)
- [certus\workers\certus_design_workers.py](#certus\workers\certusdesignworkerspy)
- [certus\workers\certus_field_workers.py](#certus\workers\certusfieldworkerspy)
- [certus\workers\certus_field_workers_dto.py](#certus\workers\certusfieldworkersdtopy)
- [certus\workers\certus_index_workers.py](#certus\workers\certusindexworkerspy)
- [certus\workers\certus_re_worker_utils.py](#certus\workers\certusreworkerutilspy)
- [certus\workers\certus_re_workers.py](#certus\workers\certusreworkerspy)
- [certus\workers\certus_re_workers_math.py](#certus\workers\certusreworkersmathpy)
- [certus\workers\certus_re_workers_phase3.py](#certus\workers\certusreworkersphase3py)
- [certus\workers\certus_strat_workers.py](#certus\workers\certusstratworkerspy)
- [certus\workers\certus_strat_workers_pipeline.py](#certus\workers\certusstratworkerspipelinepy)
- [ui\mixins\certus_base_core_mixins.py](#ui\mixins\certusbasecoremixinspy)

---

### certus\core\_certus_physics_impl.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 646 | `Exception` | 🛑 Oui | `except Exception:` |
| 818 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 836 | `tuple` | 🛑 Oui | `except (KeyError, ValueError, AttributeError):` |
| 842 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 845 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 876 | `tuple` | 🛑 Oui | `except (KeyError, ValueError, AttributeError):` |
| 886 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 1422 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1436 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1448 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1456 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1468 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1492 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError):` |
| 1511 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError, NameError):` |
| 1522 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError, NameError):` |
| 1532 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError, NameError):` |
| 1546 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError, NameError, ImportError):` |

### certus\core\certus_config.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 70 | `tuple` | 🛑 Oui | `except (OSError, IOError, json.JSONDecodeError, TypeError):` |

### certus\core\certus_core.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 167 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 186 | `tuple` | 🛑 Oui | `except (ImportError, ModuleNotFoundError):` |
| 277 | `OSError` | 🛑 Oui | `except OSError:` |
| 343 | `Exception` | 🛑 Oui | `except Exception:` |
| 454 | `Exception` | 🛑 Oui | `except Exception:` |
| 1084 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 1091 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\core\certus_index_objectives.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 1922 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 1961 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\core\certus_index_solvers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 248 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 289 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 302 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 315 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 506 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\core\certus_lazy_imports.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 231 | `tuple` | 🛑 Oui | `except (ImportError, ModuleNotFoundError, ValueError):` |

### certus\core\certus_logging.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 32 | `Exception` | 🛑 Oui | `except Exception:` |
| 116 | `tuple` | 🛑 Oui | `except (OSError, PermissionError):` |
| 122 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |

### certus\core\certus_metrology.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 24 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 138 | `OSError` | 🛑 Oui | `except OSError:` |
| 214 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 221 | `PackageNotFoundError` | 🛑 Oui | `except PackageNotFoundError:` |
| 230 | `tuple` | 🛑 Oui | `except (RuntimeError, ValueError, AttributeError):` |
| 240 | `tuple` | 🛑 Oui | `except (ValueError, OSError):` |
| 250 | `tuple` | 🛑 Oui | `except (OSError, ValueError):` |

### certus\core\certus_re_objectives.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 964 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\core\certus_re_solvers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 149 | `REUserStopRequested` | 🛑 Oui | `except REUserStopRequested:` |
| 479 | `REUserStopRequested` | 🛑 Oui | `except REUserStopRequested:` |
| 1203 | `REUserStopRequested` | 🛑 Oui | `except REUserStopRequested:` |
| 1412 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\core\certus_strat_audit.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 87 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 91 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 106 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 134 | `Exception` | 🛑 Oui | `except Exception as exc:` |

### certus\core\certus_strat_consensus.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 126 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 230 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\core\certus_strat_objectives.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 201 | `KeyError` | 🛑 Oui | `except KeyError:` |
| 552 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\core\certus_strat_ranking.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 383 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 441 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 454 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\core\certus_strat_robustness.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 112 | `Exception` | 🛑 Oui | `except Exception:` |
| 133 | `Exception` | 🛑 Oui | `except Exception:` |
| 149 | `tuple` | 🛑 Oui | `except (KeyError, TypeError):` |
| 187 | `Exception` | 🛑 Oui | `except Exception:` |
| 241 | `tuple` | 🛑 Oui | `except (KeyError, ValueError, TypeError):` |
| 358 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 353 | `Exception` | 🛑 Oui | `except Exception:` |
| 399 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 394 | `Exception` | 🛑 Oui | `except Exception:` |
| 795 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\core\certus_substrate_index.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 1490 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 1593 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexErro` |

### certus\metal\certus_metal_common.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 177 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 472 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 812 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1257 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError):` |
| 1883 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 1894 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 1941 | `tuple` | 🛑 Oui | `except (ValueError, KeyError) as e:` |
| 2073 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 2079 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 2143 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, OSError):` |

### certus\metal\pglobal_adapter.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 28 | `Exception` | 🛑 Oui | `except Exception:` |
| 108 | `Exception` | 🛑 Oui | `except Exception:` |
| 128 | `Exception` | 🛑 Oui | `except Exception:` |
| 140 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 308 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 350 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |

### certus\physics\certus_optimizers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 41 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 54 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 121 | `tuple` | 🛑 Oui | `except (ValueError, RuntimeError, TypeError):` |
| 245 | `tuple` | 🛑 Oui | `except (ValueError, RuntimeError, np.linalg.LinAlgError):` |
| 646 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 682 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 737 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError):` |
| 816 | `tuple` | 🛑 Oui | `except (ValueError, RuntimeError):` |
| 853 | `tuple` | 🛑 Oui | `except (ValueError, RuntimeError, TypeError, ArithmeticError):` |

### certus\physics\certus_strat_batch.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 273 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\physics\certus_warmup.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 24 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 31 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 38 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 45 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\spline\certus_corridor_bootstrap.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 65 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\certus_corridor_config.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 616 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\spline\certus_corridor_fitter.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 93 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\spline\certus_corridor_orchestrator_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 214 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError):` |
| 261 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError):` |
| 451 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 683 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError):` |
| 862 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError):` |
| 818 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError):` |

### certus\spline\certus_corridor_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 363 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 491 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 534 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 543 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |

### certus\spline\certus_index_spline_config.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 324 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 356 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\certus_index_spline_core.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 676 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 906 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1288 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1312 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 1362 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |

### certus\spline\certus_index_spline_corridors.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 140 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 215 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError):` |
| 780 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 792 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 864 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 912 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 926 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1554 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError, AttributeError):` |
| 2504 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError, AttributeError):` |

### certus\spline\certus_index_spline_excel_export.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 62 | `ValueError` | 🛑 Oui | `except ValueError:` |

### certus\spline\certus_index_spline_execution.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 43 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 46 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 64 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError):` |
| 390 | `tuple` | 🛑 Oui | `except (OSError, ValueError, TypeError, RuntimeError) as exc:` |
| 465 | `OSError` | 🛑 Oui | `except OSError as e:` |
| 874 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 898 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\certus_index_spline_io.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 83 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 102 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 112 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 122 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 132 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\certus_index_spline_rendering.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 65 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError):` |
| 241 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 661 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 741 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError):` |

### certus\spline\certus_index_spline_settings.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 157 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 197 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 450 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError):` |
| 1340 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\spline\certus_index_spline_smart_init.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 861 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 903 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 917 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |

### certus\spline\spline_finalize.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 589 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 833 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 862 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\spline_pipeline_corridors_runner.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 133 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 235 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 408 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 413 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 516 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 667 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 671 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 722 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 771 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\spline\spline_pipeline_mesh_clean.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 285 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 364 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\spline_pipeline_mesh_insert.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 170 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 934 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 960 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\spline\spline_pipeline_orchestrator.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 624 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\spline_pipeline_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 339 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 522 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\spline\spline_smart_init.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 934 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, AttributeError, RuntimeError):` |
| 962 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, AttributeError, RuntimeError):` |
| 1111 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\spline\spline_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 395 | `LBFGSBStop` | 🛑 Oui | `except LBFGSBStop:` |
| 913 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1791 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, AttributeError, KeyError):` |
| 1933 | `SmartInitPreviewCancelled` | 🛑 Oui | `except SmartInitPreviewCancelled:` |

### certus\ui\certus_a11y.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 112 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 158 | `AttributeError` | 🛑 Oui | `except AttributeError:` |
| 172 | `tuple` | 🛑 Oui | `except (AttributeError, TypeError):` |
| 190 | `tuple` | 🛑 Oui | `except (RuntimeError, TypeError, ValueError):` |
| 217 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 227 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError):` |
| 252 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 238 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 244 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ValueError):` |
| 250 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 274 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 281 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_animations.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 103 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 134 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 158 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 195 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 237 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 313 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ValueError):` |
| 319 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 328 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 342 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_base_app.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 623 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 646 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 748 | `Exception` | 🛑 Oui | `except Exception:` |
| 889 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 947 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1526 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 2374 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 2458 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_design_ui_core.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 716 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |

### certus\ui\certus_design_ui_events.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 234 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 262 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 541 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 547 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 553 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |

### certus\ui\certus_design_ui_export.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 250 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 273 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 383 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 483 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 504 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_design_ui_optimization.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 918 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_design_ui_plot.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 44 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 62 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 261 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 626 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexErro` |
| 998 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\ui\certus_design_ui_state.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 306 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as rebuild_err:` |
| 468 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as plot_err:` |

### certus\ui\certus_design_ui_worker.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 147 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 498 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 767 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 773 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 813 | `Exception` | 🛑 Oui | `except Exception:` |
| 818 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_empty_state.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 118 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 197 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 260 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 294 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 308 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 324 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_field_common.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 255 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 265 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 271 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 277 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 330 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 341 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 360 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_field_events_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 46 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 66 | `Exception` | 🛑 Oui | `except Exception as e:` |
| 84 | `ValueError` | 🛑 Oui | `except ValueError as e:` |
| 96 | `ValueError` | 🛑 Oui | `except ValueError as e:` |
| 126 | `ValueError` | 🛑 Oui | `except ValueError as e:` |
| 160 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 199 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 224 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 316 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_field_plot.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 28 | `Exception` | 🛑 Oui | `except Exception:` |
| 139 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_field_plot_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 53 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_field_state_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 22 | `ValueError` | 🛑 Oui | `except ValueError as err:` |
| 51 | `tuple` | 🛑 Oui | `except (AttributeError, ValueError):` |
| 83 | `Exception` | 🛑 Oui | `except Exception:` |
| 203 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 218 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 238 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 232 | `Exception` | 🛑 Oui | `except Exception:` |
| 357 | `Exception` | 🛑 Oui | `except Exception:` |
| 392 | `Exception` | 🛑 Oui | `except Exception as e:` |
| 441 | `Exception` | 🛑 Oui | `except Exception as e:` |
| 629 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 517 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 522 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 527 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 586 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 638 | `Exception` | 🛑 Oui | `except Exception:` |
| 652 | `Exception` | 🛑 Oui | `except Exception:` |
| 674 | `Exception` | 🛑 Oui | `except Exception:` |
| 734 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 803 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 836 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 990 | `Exception` | 🛑 Oui | `except Exception:` |
| 1010 | `Exception` | 🛑 Oui | `except Exception:` |
| 1024 | `Exception` | 🛑 Oui | `except Exception:` |
| 1096 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_field_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 49 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 78 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_field_workers_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 28 | `Exception` | 🛑 Oui | `except Exception:` |
| 135 | `ValueError` | 🛑 Oui | `except ValueError as e:` |
| 169 | `ValueError` | 🛑 Oui | `except ValueError as e:` |
| 198 | `Exception` | 🛑 Oui | `except Exception:` |
| 222 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_icons.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 254 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError):` |

### certus\ui\certus_index_spline_common.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 422 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 507 | `tuple` | 🛑 Oui | `except (AttributeError, TypeError):` |

### certus\ui\certus_index_spline_eventsextras_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 13 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 27 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 39 | `Exception` | 🛑 Oui | `except Exception:` |
| 122 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 722 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 792 | `Exception` | 🛑 Oui | `except Exception:` |
| 968 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_index_spline_manualmesh_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 370 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_index_spline_mixins_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 44 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 345 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 484 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 491 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_index_spline_monitor_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 121 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, RuntimeError):` |

### certus\ui\certus_index_spline_smartinit_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 196 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as exc:` |
| 307 | `tuple` | 🛑 Oui | `except (OSError, json.JSONDecodeError, ValueError) as exc:` |
| 310 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |

### certus\ui\certus_index_spline_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 199 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_index_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 299 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\ui\certus_index_ui_events.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 359 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 652 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError) as e:` |
| 841 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError) as e:` |
| 864 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError) as e:` |

### certus\ui\certus_index_ui_export.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 374 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 380 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1287 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 1278 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 1385 | `tuple` | 🛑 Oui | `except (TypeError, AttributeError):` |

### certus\ui\certus_index_ui_layout.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 216 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError) as e:` |
| 234 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError) as e:` |

### certus\ui\certus_index_ui_plot.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 340 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\ui\certus_index_ui_worker.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 147 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 238 | `Exception` | 🛑 Oui | `except Exception:` |
| 637 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 853 | `ValueError` | 🛑 Oui | `except ValueError:` |

### certus\ui\certus_manual_sigma_knot_dialog.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 587 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 651 | `AttributeError` | 🛑 Oui | `except AttributeError:` |
| 864 | `Exception` | 🛑 Oui | `except Exception:` |
| 996 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1152 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1215 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1203 | `AttributeError` | 🛑 Oui | `except AttributeError:` |

### certus\ui\certus_onboarding.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 99 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 156 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 318 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 411 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_plot.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 210 | `Exception` | 🛑 Oui | `except Exception:` |
| 379 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexErro` |
| 406 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 441 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 558 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 617 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 650 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 646 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, ValueError, TypeError):` |

### certus\ui\certus_re_excel_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 168 | `tuple` | 🛑 Oui | `except (OSError, ValueError):` |
| 453 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 690 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, KeyError):` |
| 1342 | `tuple` | 🛑 Oui | `except (TypeError, RuntimeError):` |
| 1589 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 1995 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 2022 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 2197 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as exc:` |
| 2145 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 2166 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_re_layout_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 235 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\ui\certus_re_state_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 191 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 220 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 385 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 423 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ValueError):` |

### certus\ui\certus_re_table_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 166 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 232 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 771 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 1035 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_re_workers_mixin.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 335 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 593 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 632 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 651 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 740 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1103 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 1202 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_recent.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 71 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 81 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 106 | `Exception` | 🛑 Oui | `except Exception:` |
| 174 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 196 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\ui\certus_recent_strip.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 147 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 170 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 199 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_shortcuts_overlay.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 61 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 142 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 124 | `tuple` | 🛑 Oui | `except (RuntimeError, TypeError, ValueError):` |
| 157 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_smart_init_curve_editor.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 146 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 271 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 568 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\ui\certus_spectrum_eval_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 37 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 43 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |

### certus\ui\certus_splash.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 61 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_strat_common.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 50 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\ui\certus_strat_json_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 74 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |

### certus\ui\certus_strat_mixins_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 52 | `AttributeError` | 🛑 Oui | `except AttributeError:` |

### certus\ui\certus_strat_plots_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 106 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_strat_table_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 214 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 297 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 351 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 963 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ZeroDivisionError):` |

### certus\ui\certus_strat_thickness_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 383 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\ui\certus_strat_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 328 | `tuple` | 🛑 Oui | `except (OSError, AttributeError, ImportError):` |

### certus\ui\certus_strat_ui_events.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 84 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 103 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |

### certus\ui\certus_strat_ui_export.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 20 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 28 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 92 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 103 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, OSError):` |
| 142 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, AttributeError):` |
| 155 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 575 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, AttributeError):` |
| 590 | `ValueError` | 🛑 Oui | `except ValueError:` |

### certus\ui\certus_strat_ui_plot.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 39 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError) as e:` |
| 65 | `queue.Empty` | 🛑 Oui | `except queue.Empty:` |
| 162 | `tuple` | 🛑 Oui | `except (TypeError, AttributeError):` |
| 347 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 369 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 393 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 417 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 498 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ValueError):` |
| 512 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ValueError):` |

### certus\ui\certus_strat_ui_state.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 318 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 325 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 420 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 772 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 697 | `json.JSONDecodeError` | 🛑 Oui | `except json.JSONDecodeError:` |
| 785 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 825 | `tuple` | 🛑 Oui | `except (TypeError, RuntimeError):` |
| 893 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 1083 | `ValueError` | 🛑 Oui | `except ValueError:` |

### certus\ui\certus_strat_ui_worker.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 24 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 134 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 156 | `Exception` | 🛑 Oui | `except Exception:` |
| 200 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 223 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 234 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 270 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, ValueError):` |
| 285 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 294 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 357 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 366 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 463 | `tuple` | 🛑 Oui | `except (TypeError, RuntimeError):` |
| 497 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 576 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError):` |
| 600 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 612 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |

### certus\ui\certus_strat_welcome_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 190 | `tuple` | 🛑 Oui | `except (AttributeError, TypeError):` |

### certus\ui\certus_substrate_presenter.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 128 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 101 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 120 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_substrate_ui.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 233 | `Exception` | 🛑 Oui | `except Exception:` |
| 930 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 1209 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_svg.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 12 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\ui\certus_theme.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 407 | `Exception` | 🛑 Oui | `except Exception:` |
| 427 | `Exception` | 🛑 Oui | `except Exception:` |
| 435 | `Exception` | 🛑 Oui | `except Exception:` |
| 530 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_toast_stack.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 175 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError):` |
| 218 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 283 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 342 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 349 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 392 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_tooltips.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 133 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError):` |
| 162 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 181 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |
| 279 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError):` |
| 289 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 304 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\ui\certus_tours_catalog.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 255 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, AttributeError):` |
| 273 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\ui\certus_ui_shared.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 20 | `Exception` | 🛑 Oui | `except Exception:` |
| 25 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_ui_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 358 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, ValueError, TypeError):` |
| 619 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ValueError):` |
| 641 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 701 | `queue.Empty` | 🛑 Oui | `except queue.Empty:` |
| 779 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 729 | `Exception` | 🛑 Oui | `except Exception:` |
| 835 | `Exception` | 🛑 Oui | `except Exception:` |
| 880 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 970 | `Exception` | 🛑 Oui | `except Exception:` |
| 1031 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 991 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1015 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1027 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1039 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 1120 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1179 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |
| 1306 | `Exception` | 🛑 Oui | `except Exception:` |
| 1312 | `Exception` | 🛑 Oui | `except Exception:` |
| 1316 | `Exception` | 🛑 Oui | `except Exception:` |
| 1330 | `Exception` | 🛑 Oui | `except Exception:` |
| 1328 | `Exception` | 🛑 Oui | `except Exception:` |
| 1403 | `Exception` | 🛑 Oui | `except Exception:` |
| 1375 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\ui\certus_ui_widgets_cards.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 141 | `tuple` | 🛑 Oui | `except (ImportError, ModuleNotFoundError, AttributeError):` |
| 242 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 303 | `tuple` | 🛑 Oui | `except (ImportError, ModuleNotFoundError, AttributeError):` |
| 316 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |

### certus\ui\certus_ui_widgets_layout.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 277 | `tuple` | 🛑 Oui | `except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError):` |

### certus\ui\certus_ui_widgets_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 464 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |

### certus\ui\certus_worker_manager.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 32 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 46 | `Exception` | 🛑 Oui | `except Exception:` |
| 51 | `Exception` | 🛑 Oui | `except Exception:` |
| 86 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\utils\certus_badges.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 94 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, TypeError):` |
| 191 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |

### certus\utils\certus_command_palette.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 81 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |

### certus\utils\certus_curve_smoother.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 102 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\utils\certus_data.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 164 | `tuple` | 🛑 Oui | `except (pd.errors.ParserError, ValueError, UnicodeDecodeError, OSError):` |
| 148 | `tuple` | 🛑 Oui | `except (pd.errors.ParserError, ValueError, UnicodeDecodeError):` |
| 160 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 197 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |
| 422 | `tuple` | 🛑 Oui | `except (OSError, FileNotFoundError):` |
| 783 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 977 | `tuple` | 🛑 Oui | `except (ValueError, TypeError):` |

### certus\utils\certus_design_services.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 76 | `Exception` | 🛑 Oui | `except Exception:` |
| 79 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\utils\certus_export.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 49 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 87 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 127 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 176 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as e:` |
| 221 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\utils\certus_index_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 473 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 720 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1052 | `Exception` | 🛑 Oui | `except Exception:` |
| 1058 | `Exception` | 🛑 Oui | `except Exception:` |
| 1069 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\utils\certus_progress_tracker.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 192 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 206 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 218 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, TypeError):` |
| 402 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):` |

### certus\utils\certus_re_helpers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 643 | `ValueError` | 🛑 Oui | `except ValueError:` |
| 860 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 1554 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1567 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ValueError):` |

### certus\utils\certus_reports.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 455 | `TypeError` | 🛑 Oui | `except TypeError:` |
| 684 | `TypeError` | 🛑 Oui | `except TypeError:` |

### certus\utils\certus_reset_framework.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 70 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 68 | `OSError` | 🛑 Oui | `except OSError:` |
| 341 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\utils\certus_sample_data.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 60 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, OSError):` |
| 174 | `tuple` | 🛑 Oui | `except (OSError, UnicodeDecodeError, ValueError):` |

### certus\utils\certus_services.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 102 | `ValueError` | 🛑 Oui | `except ValueError:` |

### certus\utils\certus_skeleton.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 368 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 389 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |

### certus\utils\certus_spectral_preproc.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 68 | `Exception` | 🛑 Oui | `except Exception:` |
| 147 | `Exception` | 🛑 Oui | `except Exception:` |
| 231 | `Exception` | 🛑 Oui | `except Exception:` |
| 236 | `Exception` | 🛑 Oui | `except Exception:` |
| 350 | `Exception` | 🛑 Oui | `except Exception:` |
| 368 | `Exception` | 🛑 Oui | `except Exception:` |
| 449 | `Exception` | 🛑 Oui | `except Exception:` |
| 436 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\utils\certus_spline_report.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 54 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 511 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 805 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 968 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |

### certus\utils\certus_strat_context.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 162 | `tuple` | 🛑 Oui | `except (BrokenPipeError, OSError):` |
| 172 | `tuple` | 🛑 Oui | `except (BrokenPipeError, OSError):` |
| 371 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 376 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 392 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 480 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 492 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 547 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 557 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 566 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 577 | `Exception` | 🛑 Oui | `except Exception:` |

### certus\utils\certus_strat_service.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 38 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 41 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 260 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 286 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 293 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as exc:` |
| 335 | `tuple` | 🛑 Oui | `except (AttributeError, TypeError, ValueError):` |
| 373 | `tuple` | 🛑 Oui | `except (KeyError, TypeError, ValueError):` |
| 935 | `tuple` | 🛑 Oui | `except (ValueError, TypeError, KeyError):` |
| 1070 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1091 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 1150 | `tuple` | 🛑 Oui | `except (IndexError, AttributeError, KeyError):` |
| 1161 | `KeyError` | 🛑 Oui | `except KeyError:` |

### certus\utils\certus_strat_stability.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 62 | `tuple` | 🛑 Oui | `except (TypeError, ValueError, AttributeError):` |

### certus\utils\certus_validation.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 26 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 46 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 53 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\utils\errors.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 85 | `Exception` | 🛑 Oui | `except Exception:` |
| 91 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 649 | `KeyError` | 🛑 Oui | `except KeyError:` |

### certus\workers\certus_design_worker_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 503 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 967 | `AttributeError` | 🛑 Oui | `except AttributeError:` |

### certus\workers\certus_design_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 109 | `Exception` | 🛑 Oui | `except Exception:` |
| 290 | `RuntimeError` | 🛑 Oui | `except RuntimeError:` |

### certus\workers\certus_field_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 19 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 136 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |
| 175 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 676 | `Exception` | 🛑 Oui | `except Exception:` |
| 735 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\workers\certus_field_workers_dto.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 63 | `TypeError` | 🛑 Oui | `except TypeError:` |

### certus\workers\certus_index_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 307 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |
| 802 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS as _e_tlu:` |
| 808 | `NUMERICAL_FAULT_EXCEPTIONS` | 🛑 Oui | `except NUMERICAL_FAULT_EXCEPTIONS:` |

### certus\workers\certus_re_worker_utils.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 366 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\workers\certus_re_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 152 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\workers\certus_re_workers_math.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 100 | `Exception` | 🟢 Non (log/raise présent) | `except Exception:` |

### certus\workers\certus_re_workers_phase3.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 60 | `tuple` | 🛑 Oui | `except (TypeError, ValueError):` |
| 79 | `ImportError` | 🛑 Oui | `except ImportError:` |

### certus\workers\certus_strat_workers.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 742 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 514 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 525 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 726 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 752 | `tuple` | 🛑 Oui | `except (OSError, AttributeError):` |
| 790 | `queue.Empty` | 🛑 Oui | `except queue.Empty:` |
| 792 | `tuple` | 🛑 Oui | `except (BrokenPipeError, OSError, ValueError):` |
| 911 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 889 | `tuple` | 🛑 Oui | `except (queue.Empty, IndexError, AttributeError):` |
| 1011 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1083 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1292 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1346 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1400 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 1552 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |

### certus\workers\certus_strat_workers_pipeline.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 218 | `Exception` | 🛑 Oui | `except Exception:` |
| 223 | `Exception` | 🛑 Oui | `except Exception:` |
| 227 | `Exception` | 🛑 Oui | `except Exception:` |
| 241 | `Exception` | 🛑 Oui | `except Exception:` |

### ui\mixins\certus_base_core_mixins.py

| Ligne | Type Exception | Silencieux ? | Code / Extrait |
|---|---|---|---|
| 64 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 71 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ValueError):` |
| 83 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ValueError):` |
| 102 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError, ZeroDivisionError):` |
| 107 | `tuple` | 🛑 Oui | `except (AttributeError, RuntimeError, TypeError):` |
| 143 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 210 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 261 | `tuple` | 🛑 Oui | `except (ImportError, AttributeError):` |
| 326 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 340 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 347 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 354 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 361 | `tuple` | 🛑 Oui | `except (ImportError, RuntimeError, AttributeError, TypeError, ValueError):` |
| 371 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 388 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 421 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 448 | `Exception` | 🟢 Non (log/raise présent) | `except Exception as e:` |
| 480 | `ImportError` | 🛑 Oui | `except ImportError:` |
| 499 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError):` |
| 512 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 519 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 535 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |
| 559 | `tuple` | 🛑 Oui | `except (RuntimeError, AttributeError, TypeError, ValueError, ImportError):` |

