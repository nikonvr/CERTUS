"""Pipeline STRAT complet sur le juge de paix, drapeau `poem_anchor_noise` ferme puis ouvert.

    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py off    # reference
    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py on     # bruit seul
    .venv/Scripts/python.exe scripts/probe_anchor_noise_pipeline.py full   # modele complet

Reutilise TEL QUEL l'analyse par bande de `probe_spectral_error.py` — meme code, donc
chiffres comparables par construction au baseline qu'il a produit :

    RMSE global med 1,904 / p95 4,041 | passante p95 2,74 | FRONT p95 14,28
    BLOQUEE p95 0,0050 max|E| 0,019 % | decalage du front p95 1,80 nm

⚠️ LE FICHIER D'EXEMPLE N'EST PAS TOUCHE. Le drapeau est injecte en surchargeant
`collect_params` apres coup. Recopier `JSON-strat-example.json` pour y poser le
drapeau serait exactement le mode de defaillance que ce depot a paye trois fois : le
fichier de reference qui derive du defaut du code sans que personne ne le voie.

N'ecrit rien hors reports/. Ne modifie aucun code de production.
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
#: 👤 « c'est bien un seuil d'amplitude, qui doit etre a environ 5 sigmas du bruit »
#: (2026-08-06). Le tirage suit N(0, A/3) tronque a +/-A, donc sigma = 0,332 A et
#: 5 sigma = 1,66 A. Voir docs/PLAN_STRAT.md §2.2.
FIVE_SIGMA: float = 1.66


def patch_flag(mode: str, scan_step: float | None = None, seed: int | None = None) -> None:
    """Force la configuration du modele dans les params, sans toucher a l'exemple.

    ``off``  chemin historique, reference.
    ``on``   bruit de lecture seul (axe 1.1), sans regle de detection ni marge.
    ``full`` LE MODELE PHYSIQUE COMPLET tel que le physicien l'a specifie : signal
             bruite, detection a 5 sigma, et marge de securite au point tournant a
             5 sigma — donc la vraie matrice cumulee branchee en Phase A.

    ``scan_step`` force le PAS DE LA GRILLE DES LAMBDA DE CONTROLE, en nanometres.

    🔴 IL SERT A TRANCHER 1 nm CONTRE 2 nm PAR LE CALCUL, et a lever un confondu de ma
    part. En corrigeant `_resolve_available_wavelengths`, DEUX choses ont change
    ensemble : le PAS (l'union avec la grille d'affichage donnait 1 nm) et la PLAGE
    (cette union debordait sous 450 nm, hors du balayage). J'ai attribue le gain mesure
    au seul pas. Ici la plage est identique des deux cotes — c'est la grille de balayage
    dans les deux cas — donc seul le pas varie.

    ⚠️ Le pas ne touche pas que l'etage ELITE : il change le nombre de candidates que la
    Phase A evalue par couche (126 a 2 nm, 251 a 1 nm sur 450-700). C'est bien la
    question posee — une grille de controle plus fine aide-t-elle, de bout en bout ?
    """
    from certus.ui.certus_strat_ui_state import CertusStratStateMixin

    orig = CertusStratStateMixin.collect_params
    noise = mode in {"on", "full"}
    hyst = FIVE_SIGMA if mode == "full" else 0.0
    margin = FIVE_SIGMA if mode == "full" else 0.0

    def patched(self):
        params = orig(self)
        if scan_step is not None:
            params["scan_wl_step"] = float(scan_step)
        if seed is not None:
            # Replication : la recherche est deterministe A GRAINE DONNEE, mais elle
            # echantillonne l'espace des strategies. Changer la graine donne un SECOND
            # tirage independant — c'est ce qui transforme un n=1 en n=2.
            params["robustness_seed"] = int(seed)
            params["phase_a_seed"] = int(seed)
            params["consensus_seed_list"] = ",".join(str(seed + i) for i in range(5))
        params["poem_anchor_noise"] = noise
        params["poem_anchor_noise_phase_a"] = noise
        params["tp_hysteresis_factor"] = hyst
        params["phase_a_level_margin_factor"] = margin
        return params

    CertusStratStateMixin.collect_params = patched
    B.emit(
        f"MODE={mode} | poem_anchor_noise={noise} | tp_hysteresis_factor={hyst:g} "
        f"| phase_a_level_margin_factor={margin:g} "
        f"| scan_wl_step={'(config)' if scan_step is None else f'{scan_step:g} nm'}"
        f"| seed={'(config)' if seed is None else seed}"
    )


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "off").strip().lower()
    if mode not in {"on", "off", "full"}:
        raise SystemExit("usage: probe_anchor_noise_pipeline.py [off|on|full] [pas_nm] [graine]")
    scan_step = float(sys.argv[2]) if len(sys.argv) > 2 else None
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else None
    tag = mode if scan_step is None else f"{mode}_step{scan_step:g}".replace(".", "p")
    if seed is not None:
        tag = f"{tag}_seed{seed}"

    B.qapp()
    B.autoanswer_dialogs(True)
    from certus_physics import calculate_RT_batch_kernel  # noqa: F401  echec immediat si absent

    patch_flag(mode, scan_step, seed)
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
    PSE.OUT.parent.mkdir(parents=True, exist_ok=True)
    PSE.OUT.write_text(json.dumps(r, indent=1), encoding="utf-8")
    B.emit(f"PROBE_WRITTEN={PSE.OUT}  strategies={r['n']}")
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
