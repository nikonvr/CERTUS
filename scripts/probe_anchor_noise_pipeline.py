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
)


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
        params["affine_scale_amp"] = float(os.environ.get("CERTUS_AFFINE_SCALE_AMP", "0.0"))
        params["affine_offset_amp"] = float(os.environ.get("CERTUS_AFFINE_OFFSET_AMP", "0.0"))
        params["poem_enabled"] = os.environ.get("CERTUS_POEM_ENABLED", "1") not in {"0", "false", "False"}
        params["reading_smoothing_window"] = int(os.environ.get("CERTUS_SMOOTHING_WINDOW", "1"))
        params["index_corridor"] = float(os.environ.get("CERTUS_INDEX_CORRIDOR", "0.0"))
        if "CERTUS_PHASE_A_MARGIN" in os.environ:
            params["phase_a_level_margin_factor"] = float(os.environ["CERTUS_PHASE_A_MARGIN"])
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

    # Half of the model comes from the environment, not from the command line. A run whose
    # smoothing window or index corridor is not in the file name silently OVERWRITES the
    # neutral report of the same name -- which is how two unattributable crash rates were
    # produced on 2026-08-09. Only non-neutral values are appended, so existing file names
    # are unchanged.
    for env_name, prefix, neutral in (
        ("CERTUS_SMOOTHING_WINDOW", "k", 1.0),
        ("CERTUS_INDEX_CORRIDOR", "corr", 0.0),
        ("CERTUS_AFFINE_SCALE_AMP", "as", 0.0),
        ("CERTUS_AFFINE_OFFSET_AMP", "ao", 0.0),
        ("CERTUS_PHASE_A_MARGIN", "marg", None),
    ):
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        value = float(raw)
        if neutral is not None and value == neutral:
            continue
        tag = f"{tag}_{prefix}{value:g}".replace(".", "p")
    # Same truthiness rule as `patched` above -- "false" is not a float.
    if os.environ.get("CERTUS_POEM_ENABLED", "1") in {"0", "false", "False"}:
        tag = f"{tag}_poemoff"

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
    PSE.OUT.parent.mkdir(parents=True, exist_ok=True)
    PSE.OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={PSE.OUT}  strategies={r['n']}")
    B.emit(f"CONFIG={json.dumps(r['config'], sort_keys=True)}")
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
