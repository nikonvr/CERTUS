"""Pipeline STRAT complet sur le juge de paix, drapeau `poem_anchor_noise` ferme puis ouvert.

    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py off    # reference
    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py on     # bruit seul
    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py full   # modele complet

Reuses AS IS the band analysis of `probe_spectral_error.py` — same code, so
chiffres comparables par construction au baseline qu'il a produit :

    RMSE global med 1,904 / p95 4,041 | passante p95 2,74 | FRONT p95 14,28
    BLOQUEE p95 0,0050 max|E| 0,019 % | decalage du front p95 1,80 nm

⚠️ THE EXAMPLE FILE IS NOT AFFECTED. The flag is injected by overloading
`collect_params` apres coup. Recopier `JSON-strat-example.json` pour y poser le
drapeau serait exactement le mode de defaillance que ce depot a paye trois fois : le
reference file that derives from the code defect without anyone seeing it.

Does not write anything except reports/. Does not modify any production code.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402
import probe_spectral_error as PSE  # noqa: E402


#: 5 sigma du bruit de lecture, exprime en multiple de l'amplitude crete a crete A.
#: 👤 “it is indeed an amplitude threshold, which must be approximately 5 sigmas from the noise”
#: (2026-08-06). The draw follows N(0, A/3) truncates a +/-A, so sigma = 0.332 A and
#: 5 sigma = 1.66 A. See CLAUDE.md §11 and §12.2 — UNDERDIMENSIONED value, the terminal
#: anti-fabrication est 2 A. Surchargeable par le 5e argument de la ligne de commande.
FIVE_SIGMA: float = 1.66

#: Effective model configuration, captured on the first `collect_params` call and
#: written verbatim into the report JSON.
#:
#: 🔴 Without this, a report is unreadable. Half of the model is driven by environment
#: variables that appear neither in the command line nor in the file name: on 2026-08-09
#: two runs were produced whose `reading_smoothing_window` cannot be recovered, which
#: makes their crash rates -- 0.76 and 0.45 -- impossible to attribute. See CLAUDE.md
#: 17bis, finding 7.
APPLIED_CONFIG: dict[str, object] = {}

#: Keys whose value must appear in the report and in the file name. Anything that
#: changes the physics of the model belongs here.
TRACED_KEYS: tuple[str, ...] = (
    "poem_anchor_noise",
    "tp_hysteresis_factor",
    "phase_a_level_margin_factor",
    "dp_yield_weight",
    "scan_wl_step",
    "robustness_seed",
    "reading_smoothing_window",
    "index_corridor",
    "affine_scale_amp",
    "affine_offset_amp",
    "poem_enabled",
    "robustness_num_runs",
    "n_screen_runs",
    "k_keep_survivors",
    "enable_consensus_ranking",
)


#: Environment overrides. One row per variable: the variable, the params key it
#: drives, how to parse it, the value at which it is INACTIVE, and the prefix it
#: contributes to the report file name.
#:
#: 🔴 This table is the single source for BOTH the configuration and the file name.
#: They used to be read separately, and that is exactly how two runs of 2026-08-09
#: were named `full_step1_seed42` while their operator believed POEM was off.
_OVERRIDES: tuple[tuple[str, str, str, object, str], ...] = (
    ("CERTUS_AFFINE_SCALE_AMP", "affine_scale_amp", "float", 0.0, "as"),
    ("CERTUS_AFFINE_OFFSET_AMP", "affine_offset_amp", "float", 0.0, "ao"),
    ("CERTUS_SMOOTHING_WINDOW", "reading_smoothing_window", "int", 1, "k"),
    ("CERTUS_INDEX_CORRIDOR", "index_corridor", "float", 0.0, "corr"),
    ("CERTUS_PHASE_A_MARGIN", "phase_a_level_margin_factor", "float", None, "marg"),
    ("CERTUS_POEM_ENABLED", "poem_enabled", "flag", True, "poemoff"),
    # --- Monte-Carlo depth. Nothing in the code SIZES these: they are defaults typed
    # into a UI dictionary. Exposing them is what makes the sizing measurable.
    ("CERTUS_NUM_RUNS", "robustness_num_runs", "int", 150, "N"),
    ("CERTUS_SCREEN_RUNS", "n_screen_runs", "int", 25, "scr"),
    ("CERTUS_KEEP_SURVIVORS", "k_keep_survivors", "int", 10, "keep"),
    ("CERTUS_CONSENSUS", "enable_consensus_ranking", "flag", False, "consensus"),
)

_TRUE_WORDS = frozenset({"1", "true", "yes", "on"})
_FALSE_WORDS = frozenset({"0", "false", "no", "off"})


def _refuse(name: str, raw: str, expected: str) -> None:
    raise SystemExit(
        f"\n{name}={raw!r} is not {expected}.\n"
        "Refusing to run. A probe that silently falls back to its default measures\n"
        "something other than what was asked, and says nothing about it.\n"
    )


def _resolve_env_config() -> dict[str, object]:
    """Read every environment override ONCE, strictly, into one dictionary.

    🔴 Why this is strict. On 2026-08-09 two runs launched with
    ``CERTUS_POEM_ENABLED=0`` reported ``poem_enabled: true`` and returned results
    bit-identical to the POEM-on runs. ``set VAR=0`` in cmd.exe stores ``"0 "`` when
    the line carries a trailing space, and ``"0 " not in {"0", ...}`` is ``True``.
    The affine amplitudes survived the same stray space because ``float("0.05 ")``
    strips it -- which is precisely why nothing looked wrong.

    So: every value is stripped, and anything unparseable RAISES rather than falling
    back. An empty value is treated as "not set", because that is what an operator
    means by it.
    """
    cfg: dict[str, object] = {
        param: neutral for _env, param, _kind, neutral, _pfx in _OVERRIDES if neutral is not None
    }
    for env_name, param, kind, _neutral, _pfx in _OVERRIDES:
        raw = os.environ.get(env_name)
        if raw is None or not raw.strip():
            continue
        text = raw.strip()
        if kind == "flag":
            low = text.lower()
            if low in _TRUE_WORDS:
                cfg[param] = True
            elif low in _FALSE_WORDS:
                cfg[param] = False
            else:
                _refuse(env_name, raw, "a boolean (1/0, true/false, yes/no, on/off)")
        elif kind == "int":
            try:
                cfg[param] = int(text)
            except ValueError:
                _refuse(env_name, raw, "an integer")
        else:
            try:
                cfg[param] = float(text)
            except ValueError:
                _refuse(env_name, raw, "a number")
    return cfg


def env_tag_suffix(cfg: dict[str, object]) -> str:
    """File-name suffix, derived from the SAME dictionary that configures the run.

    Only non-neutral values appear, so a neutral run keeps its historical file name
    and a non-neutral one can never silently overwrite it.
    """
    parts: list[str] = []
    for _env, param, kind, neutral, prefix in _OVERRIDES:
        if param not in cfg:
            continue
        value = cfg[param]
        if neutral is not None and value == neutral:
            continue
        parts.append(prefix if kind == "flag" else f"{prefix}{float(value):g}".replace(".", "p"))
    return "".join(f"_{p}" for p in parts)


def patch_flag(
    mode: str,
    scan_step: float | None = None,
    seed: int | None = None,
    yield_weight: float | None = None,
    tp_hyst: float | None = None,
) -> None:
    """Forces the configuration of the model in the params, without touching the example.

    ``tp_hyst`` — surcharge du SEUL facteur de detection de point tournant, en
    multiples de l'amplitude de bruit A = trigger_tolerance/100. ``None`` laisse
    the value of the mode, therefore the behavior before this parameter.

    📏 Mesure du 2026-08-08 (signal propre PLAT, bruit reel, 20 000 tirages) :
    a 1.66 A noise alone MAKES a turning point in 32.9% of layers a
    la densite de grille actuelle, et 99,9 % a la cadence reelle de la machine.
    Le docstring de `detect_turning_points` etablit la borne de suffisance a 2 A ;
    1,66 A est 17 % en dessous. A 2,4 A la fabrication tombe a 0,000 %.

    ⚠ Ne PAS confondre avec `phase_a_level_margin_factor`, qui partage aujourd'hui
    the same value 1.66 but meets another criterion (see CLAUDE.md §12.2). He
    is deliberately not touched here: one thing at a time.
    """
    from certus.ui.certus_strat_ui_state import CertusStratStateMixin

    orig = CertusStratStateMixin.collect_params
    noise = mode in {"on", "full"}
    hyst = FIVE_SIGMA if mode == "full" else 0.0
    if tp_hyst is not None:
        hyst = float(tp_hyst)
    margin = FIVE_SIGMA if mode == "full" else 0.0
    env_cfg = _resolve_env_config()

    def patched(self):
        params = orig(self)
        if scan_step is not None:
            params["scan_wl_step"] = float(scan_step)
        if seed is not None:
            params["robustness_seed"] = int(seed)
            params["phase_a_seed"] = int(seed)
            params["consensus_seed_list"] = ",".join(str(seed + i) for i in range(5))
        if yield_weight is not None:
            params["dp_yield_weight"] = float(yield_weight)
        params["poem_anchor_noise"] = noise
        params["poem_anchor_noise_phase_a"] = noise
        params["tp_hysteresis_factor"] = hyst
        params["phase_a_level_margin_factor"] = margin
        params["enable_local_search"] = (mode == "full")
        # One dictionary, resolved once, drives both the run and the file name.
        for key, value in env_cfg.items():
            params[key] = value
        if not APPLIED_CONFIG:
            APPLIED_CONFIG.update({k: params.get(k) for k in TRACED_KEYS})
        return params

    CertusStratStateMixin.collect_params = patched
    B.emit(
        f"MODE={mode} | poem_anchor_noise={noise} | tp_hysteresis_factor={hyst:g} "
        f"| phase_a_level_margin_factor={margin:g} "
        f"| scan_wl_step={'(config)' if scan_step is None else f'{scan_step:g} nm'}"
        f"| seed={'(config)' if seed is None else seed}"
        f"| dp_yield_weight={'(config)' if yield_weight is None else f'{float(yield_weight):g}'}"
    )


#: 👤 "SEEL must be computed or given to a precision of 0.1 nm, that is all."
SEEL_STEP_NM: float = 0.1


def quantise_seel(value: float | None) -> float | None:
    """Round to the 0.1 nm the physicist specified.

    🔑 This is NOT a display rule. The fit pins alpha = 1, so SEEL = k x RMSE and a
    sort on the continuous value reproduces the RMSE order exactly -- a sort that
    sorts nothing. Quantised, it creates TIES, and ties are broken by the yield.
    That is what makes SEEL a distinct ranking criterion.
    """
    if value is None:
        return None
    return round(round(float(value) / SEEL_STEP_NM) * SEEL_STEP_NM, 1)


def _layer_wavelengths(row: dict) -> list[float]:
    """Per-layer monitoring wavelength, rebuilt from the block boundaries."""
    out: list[float] = []
    wls = row.get("wavelengths") or []
    for (start, end), wl in zip(row.get("block_bounds") or [], wls):
        out.extend([float(wl)] * max(0, int(end) - int(start)))
    return out


def common_prefix_length(rows: list[dict]) -> int:
    """How many leading layers every strategy monitors at the SAME wavelength.

    🔴 WHY THIS EXISTS. Measured 2026-08-11: nine of the ten strategies tied at
    SEEL 0.3 nm returned the very same critical layer and the very same margin --
    0.83 A at layer 6. Not a bug: all ten open with a 544 nm block, so layer 6 is
    literally the same physics in all nine, and an identical margin is the correct
    answer. But a quantity describing what strategies SHARE cannot rank them.

    The tenth had its critical layer at 42, in the second block where the wavelengths
    diverge -- and a margin four times worse. That one the margin did separate.

    So: keep the global margin for the OPERATOR (it is what will give way in the
    chamber, shared prefix included) and use the margin beyond this prefix to RANK.
    """
    grids = [_layer_wavelengths(r) for r in rows]
    grids = [g for g in grids if g]
    if len(grids) < 2:
        return 0
    n = min(len(g) for g in grids)
    k = 0
    while k < n and all(abs(g[k] - grids[0][k]) < 1e-6 for g in grids):
        k += 1
    return k


def discriminating_margin(row: dict, prefix: int) -> tuple[float, int, str]:
    """Smallest margin (in A) strictly beyond the common prefix, with where and why.

    Returns `(1e9, -1, "")` when nothing beyond the prefix is constrained -- which is
    a real answer, not a failure, and must not be read as a large margin.
    """
    best, best_layer, best_cause = 1e9, -1, ""
    for cause, hits in (row.get("margin_by_layer") or {}).items():
        for layer_s, margin in hits.items():
            layer = int(layer_s)
            if layer < prefix:
                continue
            if float(margin) < best:
                best, best_layer, best_cause = float(margin), layer, cause
    return best, best_layer, best_cause


def _rank_by_seel_rule(ranking: list[dict]) -> list[dict]:
    """Re-order a ranking by the 14 rule and report what it changed.

    Returns the top rows in the new order, each carrying the rank it HAD, so the two
    orders can be compared at a glance. A rule that never reorders anything would be
    an inert filter with a nice docstring -- control 4 of 20.
    """
    from certus.core.certus_strat_ranking import rank_key_seel_yield_margin

    rows = [r for r in ranking if r.get("seel_nm") is not None]
    if not rows:
        return []
    for i, r in enumerate(ranking):
        r["rank_score_order"] = i + 1
    # The equivalence class is what the tie-break has to order. The common prefix is
    # computed on THAT set, not on all 228: strategies far apart in score share almost
    # nothing, and a prefix taken over them would be empty and mask nothing.
    best_seel = rows[0].get("seel_nm")
    cls = [r for r in rows if r.get("seel_nm") == best_seel]
    prefix = common_prefix_length(cls)
    for r in rows:
        m, lay, cause = discriminating_margin(r, prefix)
        r["_disc_margin"] = m
        r["_disc_layer"] = lay
        r["_disc_cause"] = cause
    ordered = sorted(
        rows,
        key=lambda r: rank_key_seel_yield_margin(
            float(r.get("seel_nm") or 0.0),
            float(r.get("crash") or 0.0),
            float(r.get("_disc_margin", 1e9)),
        ),
    )
    return [
        {
            "id": r.get("id"),
            "rank_score_order": r.get("rank_score_order"),
            "seel_nm": r.get("seel_nm"),
            "crash": r.get("crash"),
            "n_blocks": r.get("n_blocks"),
            # For the operator: what gives way, shared prefix included.
            "critical_layer": r.get("critical_layer") or {},
            # For the ranking: the same, restricted to where strategies differ.
            "discriminating_margin_A": (
                None if r.get("_disc_margin", 1e9) >= 1e8 else r.get("_disc_margin")
            ),
            "discriminating_layer": r.get("_disc_layer"),
            "discriminating_cause": r.get("_disc_cause"),
            "common_prefix_layers": prefix,
        }
        for r in ordered[:15]
    ]


def seel_block(result: float | None, report: dict) -> dict:
    """Read the run in NANOMETRES: the equivalent random per-layer error.

    Calibrates once on the nominal design -- perturb every layer by N(0, sigma) for
    six sigmas, measure the spectral RMSE, fit sigma = k x RMSE -- then converts.
    About a second of compute against the twenty-five minutes of the run itself.

    ⚠️ `result` and the per-strategy RMSE are NOT at the same noise level (10: RESULT
    is the WORST of three, the strategy rows are at NOMINAL). Both are converted, and
    both are labelled, but they must never be compared with each other.
    """
    out: dict[str, object] = {"step_nm": SEEL_STEP_NM}
    try:
        data = PSE.SEEL_DATA
        if not data:
            out["status"] = "unavailable: calculate_seel_analysis was not called"
            return out
        k = float(data.get("fit_k", 0.0))
        out["fit_k"] = k
        out["fit_alpha"] = float(data.get("fit_alpha", 1.0))
        out["sigmas"] = list(data.get("sigmas", []))
        out["avg_rmse"] = list(data.get("avg_rmse", []))
        if result is not None and k > 0.0:
            out["result_seel_nm"] = quantise_seel(k * float(result))
            out["result_seel_raw_nm"] = k * float(result)
        ranking = report.get("ranking") or []
        for row in ranking:
            score = row.get("score")
            row["seel_nm"] = quantise_seel(k * float(score)) if (score is not None and k > 0) else None
        # 👤 The ranking rule of 14, applied HERE because this is where SEEL exists.
        #
        # 🔴 NOT a replacement of the pipeline's own order -- that one still decides
        # RESULT, and changing it is a separate action (14 item 1: SEEL has to move out
        # of the GUI first). This is a second, EXPLICIT ordering written alongside, so
        # the two can be compared on the same run before anything is switched.
        #
        # 17-26 is why it exists: at N = 150 the top eight lie within 2 sigma and all
        # read the same SEEL. The continuous order is separating noise.
        out["ranking_seel_rule"] = _rank_by_seel_rule(ranking)
        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 -- never let the readout kill a 25-min run
        out["status"] = f"failed: {exc!r}"
    return out


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "off").strip().lower()
    if mode not in {"on", "off", "full"}:
        raise SystemExit(
            "usage: probe_anchor_noise_pipeline.py [off|on|full] [pas_nm] [graine] "
            "[yield_weight] [tp_hysteresis_factor]"
        )
    scan_step = float(sys.argv[2]) if len(sys.argv) > 2 else None
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else None
    yield_weight = float(sys.argv[4]) if len(sys.argv) > 4 else None
    tp_hyst = float(sys.argv[5]) if len(sys.argv) > 5 else None
    tag = mode if scan_step is None else f"{mode}_step{scan_step:g}".replace(".", "p")
    if seed is not None:
        tag = f"{tag}_seed{seed}"
    if yield_weight is not None:
        tag = f"{tag}_yw{yield_weight:g}".replace(".", "p")
    if tp_hyst is not None:
        tag = f"{tag}_hyst{tp_hyst:g}".replace(".", "p")

    # Half of the model comes from the environment, not from the command line. The tag
    # and the configuration come from the SAME resolved dictionary, so a file name can
    # never disagree with the run it names.
    env_cfg = _resolve_env_config()
    tag += env_tag_suffix(env_cfg)

    # 🔴 ANNOUNCE THE CONFIGURATION BEFORE SPENDING 25 MINUTES ON IT.
    #
    # This block used to be printed only at the end. On 2026-08-09 two runs were
    # launched believing POEM was off; the report said otherwise, and it said so
    # 25 minutes too late, twice. Whoever launches this can now compare two lines
    # within two seconds and kill the run if they disagree.
    B.emit("")
    B.emit("=" * 70)
    B.emit("CONFIGURATION EFFECTIVE -- verifie-la MAINTENANT, avant d'attendre 25 min")
    B.emit("=" * 70)
    for _env, param, _kind, neutral, _pfx in _OVERRIDES:
        if param not in env_cfg:
            continue
        value = env_cfg[param]
        flag = "  <-- ACTIF" if (neutral is None or value != neutral) else ""
        B.emit(f"  {param:<30s} = {value!r}{flag}")
    B.emit(f"  fichier de sortie              = probe_anchor_noise_pipeline_{tag}.json")
    B.emit("=" * 70)
    B.emit("")
    sys.stdout.flush()

    B.qapp()
    B.autoanswer_dialogs(True)
    from certus_physics import calculate_RT_batch_kernel  # noqa: F401  echec immediat si absent

    patch_flag(mode, scan_step, seed, yield_weight, tp_hyst)
    PSE.OUT = ROOT / "reports" / f"probe_anchor_noise_pipeline_{tag}.json"
    PSE.install_probe()

    setup, run, val = B.run_strat()
    B.emit(f"MODE={tag}  SETUP_S={setup:.3f}  RUN_S={run:.3f}  RESULT={val}")
    if not PSE.CAPTURED or not PSE.OPTICS:
        B.emit(f"PROBE_INCOMPLETE captured={len(PSE.CAPTURED)} optics={bool(PSE.OPTICS)}")
        sys.stdout.flush()
        os._exit(0)

    r = PSE.analyse()
    r["mode"] = mode
    r["result"] = val
    r["config"] = dict(APPLIED_CONFIG)
    r["seel"] = seel_block(val, r)
    PSE.OUT.parent.mkdir(parents=True, exist_ok=True)
    PSE.OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={PSE.OUT}  strategies={r['n']}")
    B.emit(f"CONFIG={json.dumps(r['config'], sort_keys=True)}")

    # One line per run, appended to a compact ledger. A campaign transcript runs to
    # megabytes and nobody reads it while it is still useful; this is twenty lines,
    # so an anomaly can be spotted between two runs instead of after all of them.
    ledger = ROOT / "reports" / "probe_runs.tsv"
    if not ledger.exists():
        ledger.write_text(
            "tag\tsetup_s\trun_s\tresult\tn_strategies\tconfig\n", encoding="utf-8"
        )
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{tag}\t{setup:.3f}\t{run:.3f}\t{val!r}\t{r['n']}\t"
            f"{json.dumps(r['config'], sort_keys=True)}\n"
        )
    B.emit(f"LEDGER={ledger}")
    B.emit("")
    B.emit(f"  ERREUR SPECTRALE, en POINTS DE TRANSMISSION — poem_anchor_noise={mode.upper()}")
    B.emit("  id        nb  crash | RMSE global med/p95 | passante p95 | FRONT p95 | BLOQUEE p95 max|E| | decalage front p95")
    for s in r["strategies"][:8]:
        g, pa, fr, st = s["global"], s["passante"], s["front"], s["bloquee"]
        B.emit(
            f"  {str(s['id'])[:9]:>9} {s['n_blocks']:>2} {s['crash']:.3f} | "
            f"{g['rmse_median'] * 100:6.3f}/{g['rmse_p95'] * 100:6.3f} | "
            f"{pa['rmse_p95'] * 100:7.3f} | {fr['rmse_p95'] * 100:8.3f} | "
            f"{st['rmse_p95'] * 100:7.4f} {st['max_abs_p95'] * 100:7.4f} | "
            f"{s['front_shift_nm']['abs_p95']:6.2f} nm"
        )
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
