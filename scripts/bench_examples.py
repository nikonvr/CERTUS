"""Banc de mesure CERTUS sur les EXEMPLES REELS de `example/`.

Pilote chaque module en headless, sans mock, et chronometre le calcul reel.
Remplace `tests/headless/` comme banc de mesure : ces tests-la remplacent le
calcul de DESIGN et de STRAT par un mock et ne mesurent donc rien.

    python scripts/bench_examples.py <module> [options]

Modules : metal_single metal_bilayer index index_spline re field design strat

Options
    --auto-yes      repond OUI aux boites modales. INDISPENSABLE : la reponse
                    par defaut est "No", ce qui fait SAUTER la phase IR d'INDEX
                    et divise son temps par deux sans qu'on le voie.
    --sample        profil par echantillonnage de piles, tous threads confondus
    --time-cost     cout par evaluation de cost_numba_fast (DESIGN)
    --instrument    statistiques de SplineBasisCache
    --trace-nk      compte les appels a get_nk_from_spline
    --force-cache   force use_cache=True (anticipe PLAN_OPTIMISATION §2.4)
    --watchdog N    dump des piles de tous les threads toutes les N secondes
    --out CHEMIN    duplique la sortie dans un fichier

Sortie : SETUP_S (chargement), RUN_S (calcul pur), RESULT (grandeur physique,
pour verifier qu'une optimisation n'a pas change le resultat).

--- QUATRE PIEGES, tous rencontres en ecrivant ce fichier ---

1. La QApplication doit etre gardee dans une variable VIVANTE. Sans reference,
   le GC la ramasse et la creation du premier QWidget abat le processus avec le
   code de sortie 127 (ERROR_PROC_NOT_FOUND), sans aucune trace Python.
2. Les apps CERTUS detournent sys.stdout vers leurs fichiers de log. Tout print
   d'un banc disparait : on garde une reference sur le flux d'origine.
3. Ne pas importer numpy/scipy avant la creation de la QApplication : l'ordre de
   chargement des DLL compte sur Windows (meme code 127).
4. `_is_busy` ne veut rien dire dans DESIGN : lu en certus_design_ui.py:339,
   jamais ecrit. Attendre qu'il repasse a False bloque pour toujours. Le vrai
   critere de fin est `app.optim_thread.isRunning()` plus un delai de silence.

Et cProfile ne trace QUE son propre thread : le calcul de DESIGN, INDEX, METAL et
STRAT tourne dans un QThread. D'ou l'echantillonneur de --sample.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# Pas d'import numpy ici : voir piege 3.

_REAL_STDOUT = sys.stdout  # voir piege 2
_LOG = None


def emit(msg: str) -> None:
    try:
        _REAL_STDOUT.write(msg + "\n")
        _REAL_STDOUT.flush()
    except (ValueError, OSError):
        pass
    if _LOG is not None:
        _LOG.write(msg + "\n")
        _LOG.flush()


# --------------------------------------------------------------------------- #
# Qt
# --------------------------------------------------------------------------- #

_QAPP = None


def qapp():
    """QApplication unique, gardee dans un global (voir piege 1)."""
    global _QAPP
    from PyQt6.QtWidgets import QApplication

    if _QAPP is None:
        _QAPP = QApplication.instance() or QApplication(sys.argv[:1])
    return _QAPP


def autoanswer_dialogs(yes: bool = True) -> None:
    """Repond automatiquement aux boites modales.

    Sans cela, un banc headless mesure surtout des dialogues en attente, et la
    reponse par defaut "No" fait sauter des phases entieres de pipeline.
    """
    from PyQt6.QtWidgets import QMessageBox

    ans = QMessageBox.StandardButton.Yes if yes else QMessageBox.StandardButton.No
    QMessageBox.exec = lambda self: int(ans)
    QMessageBox.question = staticmethod(lambda *a, **k: ans)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    emit("dialogues: reponse automatique OUI")


def wait_for(worker, timeout_ms: int = 1_800_000):
    """Attend la fin d'un worker Qt et renvoie son resultat."""
    from PyQt6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    box: dict = {"result": None, "error": None}

    def on_done(res=None):
        box["result"] = res
        loop.quit()

    def on_error(err=None):
        box["error"] = err
        loop.quit()

    sig = getattr(worker, "signals", worker)
    if hasattr(sig, "finished"):
        sig.finished.connect(on_done)
    if hasattr(sig, "error"):
        sig.error.connect(on_error)

    t = QTimer()
    t.setSingleShot(True)
    t.timeout.connect(loop.quit)
    t.start(timeout_ms)
    loop.exec()
    t.stop()
    if box["error"] is not None:
        emit(f"WORKER_ERROR: {box['error']}")
    return box["result"]


# --------------------------------------------------------------------------- #
# Echantillonneur de piles, tous threads confondus
# --------------------------------------------------------------------------- #

SAMPLER: dict = {"self": None, "cum": None, "lines": None, "stop": None, "n": 0}


def start_sampler(interval: float = 0.005) -> None:
    """Echantillonne sys._current_frames() depuis un thread de service.

    Effet de bord utile : le temps passe dans les noyaux @njit, qui n'ont aucune
    frame Python, est impute a leur APPELANT Python. C'est exactement ce qu'on
    veut : il revele le cout de dispatch autant que le cout de calcul.
    """
    import collections
    import threading

    self_c: collections.Counter = collections.Counter()
    cum_c: collections.Counter = collections.Counter()
    line_c: collections.Counter = collections.Counter()
    stop = threading.Event()
    main_tid = threading.main_thread().ident
    me: list = [None]

    def fmt(frame) -> str:
        c = frame.f_code
        name = c.co_filename.replace(str(ROOT) + os.sep, "").replace("\\", "/")
        return f"{name}:{c.co_firstlineno}:{c.co_name}"

    def loop() -> None:
        me[0] = threading.get_ident()
        while not stop.wait(interval):
            SAMPLER["n"] += 1
            for tid, frame in sys._current_frames().items():
                if tid == me[0]:
                    continue
                tag = "MAIN" if tid == main_tid else "WORK"
                self_c[f"[{tag}] " + fmt(frame)] += 1
                cn = frame.f_code.co_filename
                if str(ROOT) in cn:
                    short = cn.replace(str(ROOT) + os.sep, "").replace("\\", "/")
                    line_c[f"{short}:{frame.f_lineno}"] += 1
                seen = set()
                f = frame
                while f is not None:
                    k = fmt(f)
                    if k not in seen:
                        seen.add(k)
                        cum_c[k] += 1
                    f = f.f_back

    threading.Thread(target=loop, daemon=True, name="certus-bench-sampler").start()
    SAMPLER.update({"self": self_c, "cum": cum_c, "lines": line_c, "stop": stop})


def dump_sampler(top: int = 22) -> None:
    if SAMPLER["stop"] is None:
        return
    SAMPLER["stop"].set()
    n = max(SAMPLER["n"], 1)
    emit("")
    emit(f"--- echantillons: {n} (intervalle 5 ms) ---")
    emit("TEMPS PROPRE (ou le processus est reellement occupe)")
    for k, v in SAMPLER["self"].most_common(top):
        emit(f"  {100.0 * v / n:5.1f} %  {v:6d}  {k}")
    emit("LIGNES LES PLUS CHERES")
    for k, v in SAMPLER["lines"].most_common(top):
        emit(f"  {100.0 * v / n:5.1f} %  {v:6d}  {k}")
    emit("TEMPS CUMULE (qui declenche ce travail)")
    for k, v in SAMPLER["cum"].most_common(top):
        emit(f"  {100.0 * v / n:5.1f} %  {v:6d}  {k}")


def start_watchdog(period_s: float) -> None:
    """Dump periodique des piles de TOUS les threads.

    Repond a une seule question : quand le processus n'avance plus, ou est-il ?
    Un compteur de progression qui stagne ne le dit pas.
    """
    import threading
    import traceback

    def loop() -> None:
        n = 0
        while True:
            time.sleep(period_s)
            n += 1
            frames = sys._current_frames()
            names = {t.ident: t.name for t in threading.enumerate()}
            emit(f"===== WATCHDOG #{n} : {len(frames)} threads =====")
            for tid, frame in frames.items():
                label = names.get(tid, "?")
                if label.startswith("certus-bench-"):
                    continue
                emit(f"--- thread {tid} ({label})")
                for line in traceback.format_stack(frame)[-14:]:
                    emit("    " + line.rstrip())

    threading.Thread(target=loop, daemon=True, name="certus-bench-watchdog").start()


# --------------------------------------------------------------------------- #
# Instrumentation optionnelle
# --------------------------------------------------------------------------- #

STATS = {"calls": 0, "hits": 0, "misses": 0, "clears": 0, "distinct": set(), "build_s": 0.0}
NK = {"calls": 0, "knots": set(), "cache_true": 0, "cache_false": 0}
COST = {"calls": 0, "s": 0.0}
OPTS: dict = {}


def install_spline_cache_probe() -> None:
    import numpy as np

    from certus.physics import certus_optical_models as com

    cls = com.SplineBasisCache
    orig = cls.get.__func__

    def wrapped(c, knot_wavelengths, target_wavelengths, extrapolate=True):
        kk = np.round(np.asarray(knot_wavelengths, dtype=np.float64), 6).tobytes()
        tk = np.round(np.asarray(target_wavelengths, dtype=np.float64), 4).tobytes()
        key = (kk, tk, bool(extrapolate))
        STATS["calls"] += 1
        STATS["distinct"].add(key)
        present = key in c._cache
        STATS["hits" if present else "misses"] += 1
        t0 = time.perf_counter()
        out = orig(c, knot_wavelengths, target_wavelengths, extrapolate)
        if not present:
            STATS["build_s"] += time.perf_counter() - t0
        return out

    cls.get = classmethod(wrapped)

    # Sous-classe du type REEL du cache : la version LRU est un OrderedDict et
    # utilise move_to_end/popitem, absents d'un dict nu.
    base = type(cls._cache)

    class CountingCache(base):  # type: ignore[misc, valid-type]
        def clear(self):
            STATS["clears"] += 1
            super().clear()

    cls._cache = CountingCache(cls._cache)


def patch_nk() -> None:
    """Enveloppe get_nk_from_spline PARTOUT ou le symbole a ete importe.

    Les appelants font `from ... import get_nk_from_spline` : patcher le module
    d'origine ne suffit pas, le nom est deja lie dans chaque module appelant.
    """
    if not (OPTS.get("trace_nk") or OPTS.get("force_cache")):
        return
    import numpy as np

    from certus.physics import certus_optical_models as com

    orig = com.get_nk_from_spline

    def wrapped(p_vals, knots, targets, use_cache=True):
        if OPTS.get("trace_nk"):
            NK["calls"] += 1
            NK["knots"].add(np.ascontiguousarray(knots, dtype=np.float64).tobytes())
            NK["cache_true" if use_cache else "cache_false"] += 1
        if OPTS.get("force_cache"):
            use_cache = True
        return orig(p_vals, knots, targets, use_cache)

    n = 0
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        try:
            if getattr(mod, "get_nk_from_spline", None) is orig:
                setattr(mod, "get_nk_from_spline", wrapped)
                n += 1
        except (AttributeError, TypeError):
            continue
    emit(f"patch_nk: {n} modules")


def time_cost_kernel() -> None:
    """Chronometre cost_numba_fast, le noyau ou DESIGN passe son temps.

    Le temps total d'un run DESIGN va de 43 a 93 s d'un essai a l'autre :
    l'optimiseur est stochastique et ne suit jamais deux fois la meme
    trajectoire. Le cout PAR EVALUATION, lui, est comparable — c'est donc lui
    qu'il faut mesurer pour opposer deux versions.
    """
    from certus.core import certus_design_core as dc

    orig = dc.cost_numba_fast

    def wrapped(*a, **k):
        t0 = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            COST["s"] += time.perf_counter() - t0
            COST["calls"] += 1

    dc.cost_numba_fast = wrapped
    emit("cost_numba_fast chronometre")


def dump_probes() -> None:
    if OPTS.get("instrument"):
        from certus.physics import certus_optical_models as com

        c = STATS["calls"]
        emit("--- SplineBasisCache ---")
        emit(f"CACHE_CALLS={c}")
        emit(f"CACHE_DISTINCT={len(STATS['distinct'])}")
        emit(f"CACHE_HITS={STATS['hits']}")
        emit(f"CACHE_MISSES={STATS['misses']}")
        if c:
            emit(f"CACHE_HITRATE={100.0 * STATS['hits'] / c:.1f}")
        emit(f"CACHE_CLEARS={STATS['clears']}")
        emit(f"CACHE_BUILD_S={STATS['build_s']:.3f}")
        emit(f"CACHE_FINAL_SIZE={len(com.SplineBasisCache._cache)}")

    if OPTS.get("trace_nk"):
        emit("--- get_nk_from_spline ---")
        emit(f"NK_CALLS={NK['calls']}")
        emit(f"NK_DISTINCT_KNOTS={len(NK['knots'])}")
        if NK["calls"]:
            emit(f"NK_REPEAT={100.0 * (1 - len(NK['knots']) / NK['calls']):.1f}")
        emit(f"NK_USE_CACHE_TRUE={NK['cache_true']}")
        emit(f"NK_USE_CACHE_FALSE={NK['cache_false']}")

    if COST["calls"]:
        emit(f"COST_CALLS={COST['calls']}")
        emit(f"COST_TOTAL_S={COST['s']:.3f}")
        emit(f"COST_US_PER_CALL={1e6 * COST['s'] / COST['calls']:.2f}")


# --------------------------------------------------------------------------- #
# Modules
# --------------------------------------------------------------------------- #

EX = ROOT / "example"


def run_metal_single():
    qapp()
    import certus_physics
    from CERTUS_METAL_SINGLE import CertusMetalSingleApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusMetalSingleApp()
    app.combo_substrate.setCurrentText("SiO2")
    app._post_load_config = lambda *a: None
    app.load_config(str(EX / "example_metal_single/JSON-metal-example.json"))
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    app.start_optimization()
    res = wait_for(app.worker)
    run = time.perf_counter() - t1

    val = None
    if res:
        r = res.get("result")
        if r is not None and hasattr(r, "fun"):
            val = float(r.fun) ** 0.5
    return setup, run, val


def run_metal_bilayer():
    qapp()
    import certus_physics
    from CERTUS_METAL_BILAYER import CertusMetalBilayerApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusMetalBilayerApp()
    if hasattr(app, "combo_substrate"):
        app.combo_substrate.setCurrentText("SiO2")
    app._post_load_config = lambda *a: None
    app.load_config(str(EX / "example_metal_bilayer/JSON-metal-bilayer-example.json"))
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    app.start_optimization()
    res = wait_for(app.worker)
    run = time.perf_counter() - t1

    val = None
    if res:
        r = res.get("result")
        if r is not None and hasattr(r, "fun"):
            val = float(r.fun) ** 0.5
    return setup, run, val


def run_index():
    qapp()
    import certus_physics
    from CERTUS_INDEX import CertusIndexApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusIndexApp()
    app.load_file(str(EX / "example_index/H400-RTNBrel-sapphire.xlsx"))
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    app.run_optimization()
    worker = getattr(app, "worker", None) or getattr(app, "_worker", None)
    res = wait_for(worker) if worker else None
    run = time.perf_counter() - t1

    # OptimizationResults (certus/core/certus_index_config.py:261) expose final_mse,
    # PAS rmse_final, et porte __slots__ : ni getattr("rmse_final") ni le repli
    # isinstance(dict) ne pouvaient aboutir. RESULT valait donc None sur INDEX, ce
    # qui privait le module du seul ancrage de correction du banc.
    # RMSE = sqrt(MSE), cf. calculate_index_rmse (certus/utils/certus_index_utils.py:1109)
    # et la convention des autres runners (float(r.fun) ** 0.5).
    val = None
    if res is not None:
        mse = getattr(res, "final_mse", None)
        if mse is not None:
            val = float(mse) ** 0.5
        elif isinstance(res, dict):
            val = res.get("rmse")
    return setup, run, val


def run_index_spline():
    qapp()
    import threading

    import certus_physics
    from certus.spline.spline_pipeline_orchestrator import worker_spline_optimization
    from certus.ui.certus_index_spline_ui import CertusIndexSplineApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusIndexSplineApp()
    app._on_load(path=str(EX / "example_index_spline/TSIO2-1700-1.xlsx"))
    cfg = app._build_opt_config(notify=False)
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    res = worker_spline_optimization(cfg, threading.Event(), progress_cb=lambda *a: None)
    run = time.perf_counter() - t1
    return setup, run, res.get("rmse") if isinstance(res, dict) else None


def run_re():
    qapp()
    import certus_physics
    from CERTUS_RE import CertusREApp
    from certus.workers.certus_re_workers import REWorker

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusREApp()
    app.load_reverse_engineering_from_path(str(EX / "example_RE/reverse_sample.xlsx"))
    cfg = app.build_re_worker_cfg()
    setup = time.perf_counter() - t0

    box: dict = {}
    worker = REWorker(cfg)
    worker.signals.result.connect(lambda r: box.update({"r": r}))
    t1 = time.perf_counter()
    worker.run()
    run = time.perf_counter() - t1
    return setup, run, (box.get("r") or {}).get("rmse")


def run_field():
    qapp()
    import certus_physics
    from certus.ui.certus_field_ui import CertusFieldApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusFieldApp()
    data = json.loads((EX / "example_field/test_hr_mirror.json").read_text())
    for key, combo in [
        ("mat_H", app.combo_mat_H),
        ("mat_L", app.combo_mat_L),
        ("mat_Sub", app.combo_mat_Sub),
        ("mat_Sup", app.combo_mat_Sup),
    ]:
        if key in data:
            i = combo.findText(data[key])
            if i >= 0:
                combo.setCurrentIndex(i)
    for key, w in [
        ("l0", app.edit_l0),
        ("seuil1", app.edit_seuil1),
        ("seuil2", app.edit_seuil2),
        ("alpha", app.edit_alpha),
        ("theta_inc_deg", app.edit_angle),
    ]:
        if key in data:
            w.setValue(float(data[key]))
    if "pol_idx" in data:
        app.combo_pol.setCurrentIndex(int(data["pol_idx"]))
    if "lcalc" in data:
        app.edit_lcalc.setText(str(data["lcalc"]))

    app._is_updating_table = True
    try:
        if "emp_factors" in data:
            lt = data.get("layer_types", [])
            app.table_layers.setRowCount(0)
            for i, f in enumerate(data["emp_factors"]):
                app.table_layers.insertRow(i)
                mat = ("H" if lt[i] == 0 else "L") if lt and i < len(lt) else None
                app.stack_panel.add_row_to_table(i, float(f), mat_str=mat)
    finally:
        app._is_updating_table = False
    app._update_thicknesses()
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    app.run_auto_calc()
    res = wait_for(app.worker) if getattr(app, "worker", None) else None
    run = time.perf_counter() - t1
    return setup, run, (type(res).__name__ if res is not None else None)


def run_design():
    qapp()
    import certus_physics
    from CERTUS_DESIGN import CertusDesignApp
    from PyQt6.QtCore import QEventLoop, QTimer

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusDesignApp()
    if OPTS.get("time_cost"):
        time_cost_kernel()
    app._post_load_config = lambda *a: None
    app.load_config(str(EX / "example_design/JSON-design-example.json"))
    setup = time.perf_counter() - t0

    # Detection de fin : voir piege 4. On suit le thread d'optimisation et les
    # emissions successives de optimization_finished_signal (une par passe).
    passes = {"n": 0, "quiet": 0.0}
    app.optimization_finished_signal.connect(lambda: passes.update(n=passes["n"] + 1))

    t1 = time.perf_counter()
    app.run_optim("global")

    loop = QEventLoop()
    tick_ms = 250
    elapsed = {"s": 0.0}

    def tick() -> None:
        elapsed["s"] += tick_ms / 1000.0
        th = getattr(app, "optim_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:  # objet C++ deja detruit
            running = False
        if running:
            passes["quiet"] = 0.0
        else:
            passes["quiet"] += tick_ms / 1000.0
            if passes["quiet"] >= 20.0 and passes["n"] > 0:
                loop.quit()
        if elapsed["s"] >= 1800.0:
            emit("TIMEOUT 1800 s")
            loop.quit()

    t = QTimer()
    t.timeout.connect(tick)
    t.start(tick_ms)
    loop.exec()
    t.stop()
    run = time.perf_counter() - t1 - passes["quiet"]

    emit(f"DESIGN_PASSES={passes['n']}")
    return setup, run, getattr(app, "_workflow_best_rmse", None)


def run_strat():
    qapp()
    import certus_physics
    from CERTUS_STRAT import CertusStratApp

    certus_physics.warmup_physics()
    patch_nk()
    t0 = time.perf_counter()
    app = CertusStratApp()
    app._post_load_config = lambda *a: None
    app.load_configuration(str(EX / "example_strat/JSON-strat-example.json"))
    setup = time.perf_counter() - t0

    t1 = time.perf_counter()
    app.run_workflow(23)  # StratTask.FULL_PIPELINE
    res = wait_for(app.worker) if getattr(app, "worker", None) else None
    run = time.perf_counter() - t1

    # Le pipeline STRAT emet un WorkerThreadResult
    # (certus/workers/certus_strat_workers_dto.py:132), PAS un dict : la cle
    # portant le RMSE est `rmse`, dans son champ `final_results`. Le banc
    # cherchait `best_rmse` sur un dict — les deux etaient faux, donc RESULT
    # valait None sur STRAT et le module n'avait aucun ancrage de correction.
    # La charge utile est le to_legacy_dict() d'un WorkerThreadResult
    # (certus/workers/certus_strat_workers_dto.py:132) : un dict a DEUX cles,
    # `final_results` et `opti_results` (constate par instrumentation).
    #
    # Le RMSE n'y figure PAS directement. La cle "rmse" du module appartient a
    # `metadata`, qui part vers un AUTRE signal, excel_ready, pour l'export Excel
    # (certus_strat_workers.py, juste avant le for_step_23). Le RMSE se derive de
    # final_results["all_strategies_results"] par extract_best_rmse — exactement
    # ce que fait le module lui-meme deux lignes plus haut.
    val = None
    final_results = res.get("final_results") if isinstance(res, dict) else None
    if isinstance(final_results, dict):
        from certus.utils.certus_strat_service import extract_best_rmse

        try:
            val = float(extract_best_rmse(final_results.get("all_strategies_results", [])))
        except BaseException as exc:  # noqa: BLE001 - un ancrage manquant doit se voir, pas tuer le banc
            emit(f"WARN_RESULT_EXTRACTION={exc!r}")
    return setup, run, val


RUNNERS = {
    "metal_single": run_metal_single,
    "metal_bilayer": run_metal_bilayer,
    "index": run_index,
    "index_spline": run_index_spline,
    "re": run_re,
    "field": run_field,
    "design": run_design,
    "strat": run_strat,
}


def main() -> None:
    global _LOG

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("module", choices=sorted(RUNNERS))
    p.add_argument("--auto-yes", action="store_true")
    p.add_argument("--sample", action="store_true")
    p.add_argument("--time-cost", action="store_true")
    p.add_argument("--instrument", action="store_true")
    p.add_argument("--trace-nk", action="store_true")
    p.add_argument("--force-cache", action="store_true")
    p.add_argument("--watchdog", type=float, default=0.0)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    OPTS.update(vars(args))

    if args.out:
        _LOG = open(args.out, "a", encoding="utf-8")

    emit(f"=== START {args.module} ===")

    # QApplication AVANT tout import de certus : voir pieges 1 et 3.
    qapp()

    if args.auto_yes:
        autoanswer_dialogs(True)
    if args.instrument:
        install_spline_cache_probe()
    if args.watchdog:
        start_watchdog(args.watchdog)
    if args.sample:
        start_sampler()

    import traceback

    try:
        setup, run, val = RUNNERS[args.module]()
    except BaseException as exc:  # noqa: BLE001 - on veut la trace, quoi qu'il arrive
        emit(f"EXC {exc!r}")
        emit(traceback.format_exc())
        os._exit(3)

    emit(f"MODULE={args.module}")
    emit(f"SETUP_S={setup:.3f}")
    emit(f"RUN_S={run:.3f}")
    emit(f"RESULT={val}")
    if val is None:
        # RESULT=None a longtemps passe inapercu sur INDEX puis sur STRAT : le banc
        # sortait la ligne sans rien signaler, et ces modules ont donc ete
        # optimisables sans aucun garde-fou de correction. Un module sans ancrage
        # doit desormais le CRIER, pas le taire.
        emit(
            f"WARN=RESULT est None sur {args.module} : ce module n'a AUCUN ancrage "
            "de correction. Ne conclus RIEN d'un A/B sur lui tant que l'extraction "
            "de son runner n'est pas reparee — un changement qui supprime du calcul "
            "passerait pour un gain sans qu'on voie qu'il a change le resultat."
        )
    dump_probes()
    if args.sample:
        dump_sampler()

    # os._exit : les apps CERTUS laissent des threads Qt vivants.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
