"""LE CRITERE PAR SWING TROUVERAIT-IL SEULEMENT QUELQUE CHOSE ? -- verification AVANT de mesurer.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\probe_swing_par_couche.py

👤 2026-08-19 : « continue avec le rate by swing ».

## Pourquoi cette sonde AVANT le run

`rate_by_swing` ajoute des candidates Rate sur les couches dont le swing de croissance est sous
`dynamics_threshold`. Si AUCUNE couche n'est sous le seuil, le parametre est INERTE sur ce
composant : le run couterait 40 min pour rendre exactement le meme resultat, et on l'attribuerait
a tort a « le Rate par besoin n'aide pas ».

📏 Cout : quelques secondes par composant, aucune Phase B, aucun Monte-Carlo.

## Ce qu'elle mesure, et a quelle lambda

Deux lectures, et elles ne disent PAS la meme chose :

    MEILLEUR CAS   le swing a la lambda la PLUS FAVORABLE de la grille pour cette couche.
                   Si meme lui est sous le seuil, la couche est indefendable optiquement.
    CAS REEL       le swing a la lambda que la Phase A a REELLEMENT retenue (best_wl, lu dans
                   le dernier STRAT_observability). C'est celui que `rate_by_swing` verra.

🔴 ET UNE LIMITE QU'IL FAUT DIRE. Le swing est calcule sur le signal NOMINAL, sans convolution
par la fente. Il est donc INDEPENDANT de la resolution du monochromateur -- le critere selectionne
les memes couches a 2 nm et a 0,5 nm. Il capture « cette couche a un signal intrinsequement
pauvre », PAS « ce run a un signal degrade par le bruit de fente ». Les deux sont des raisons
d'employer le Rate, et ce critere-ci n'en couvre qu'une.
"""

from __future__ import annotations

import glob
import importlib.util
import json
import os
import sys
from pathlib import Path

import numpy as np

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _pm():
    s = importlib.util.spec_from_file_location("pm", ROOT / "scripts" / "profil_monitorabilite.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _swing_matrix(cfg: str):
    """La matrice swing(couche, lambda), par le MEME parcours que profil_monitorabilite.

    Reprend son noyau exactement -- meme forme fermee, meme grille -- mais rend la VALEUR du
    swing au lieu du booleen d'admissibilite, parce que c'est elle que le seuil compare.
    """
    from certus.physics.certus_opt_tmm import arange_inclusive
    from certus.utils.certus_strat_service import (
        get_refractive_clues_vectorized,
        get_refractive_index,
    )
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    prm = app.collect_params()
    db = prm.get("materials_db_instance") or prm.get("materials_db")
    l0 = float(prm["l0"])
    mult = [float(e) for e in str(prm["stack_string"]).split(",") if e.strip()]
    N = len(mult)
    s_dyn = float(prm.get("dynamics_threshold", 0.025))
    lams = arange_inclusive(float(prm["scan_wl_min"]), float(prm["scan_wl_max"]),
                            float(prm.get("scan_wl_step", 2.0)))
    nH = get_refractive_clues_vectorized(prm["nH_id"], lams, db_instance=db)
    nL = get_refractive_clues_vectorized(prm["nL_id"], lams, db_instance=db)
    nS = get_refractive_clues_vectorized(prm["nSub_id"], lams, db_instance=db)
    nH0 = float(np.real(get_refractive_index(prm["nH_id"], l0, db_instance=db)))
    nL0 = float(np.real(get_refractive_index(prm["nL_id"], l0, db_instance=db)))
    d = np.array([(m * l0) / (4.0 * (nH0 if i % 2 == 0 else nL0)) for i, m in enumerate(mult)])

    sw = np.zeros((N, len(lams)), dtype=np.float64)
    for j, lam in enumerate(lams):
        M = np.eye(2, dtype=np.complex128)
        for i in range(N):
            n_i = nH[j] if i % 2 == 0 else nL[j]
            X = M[0, 0] + nS[j] * M[0, 1]
            Y = M[1, 0] + nS[j] * M[1, 1]
            C, S = X + Y, Y / n_i + n_i * X
            P = 0.5 * ((C.real**2 + C.imag**2) + (S.real**2 + S.imag**2))
            Q = 0.5 * ((C.real**2 + C.imag**2) - (S.real**2 + S.imag**2))
            R = C.imag * S.real - C.real * S.imag
            dfin = 2.0 * np.pi * float(np.real(n_i)) * d[i] / float(lam)
            u = np.linspace(0.0, dfin, 300)
            T = 4.0 * float(np.real(nS[j])) / (P + Q * np.cos(2 * u) + R * np.sin(2 * u))
            sw[i, j] = float(T.max() - T.min())
            ph = 2.0 * np.pi * n_i * d[i] / lam
            c_, s_ = np.cos(ph), np.sin(ph)
            M = M @ np.array([[c_, 1j * s_ / n_i], [1j * n_i * s_, c_]], dtype=np.complex128)
    return sw, np.asarray(lams, dtype=np.float64), s_dyn, N


def _best_wl_du_dernier_run(n_attendu: int):
    """Les lambda que la Phase A a reellement retenues, si un artefact les porte."""
    for f in sorted(glob.glob("reports/STRAT_observability_*.json"), reverse=True):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        couches = d.get("layers") or []
        if len(couches) != n_attendu:
            continue
        wls = [c.get("best_wl") for c in couches]
        if all(w is not None for w in wls):
            return [float(w) for w in wls], os.path.basename(f)
    return None, None


def main() -> int:
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    pm = _pm()
    connus = dict(pm.COMPOSANTS)
    noms = sys.argv[1:] or ["35c", "48c", "75c", "99c"]

    print(f"  {'composant':<10}{'couches':>8}{'seuil':>8}{'sous seuil AU MIEUX':>21}"
          f"{'sous seuil au CHOIX REEL':>26}")
    print("  " + "-" * 74)
    for nom in noms:
        cfg = connus.get(nom)
        if cfg is None:
            print(f"  {nom:<10} inconnu")
            continue
        sw, lams, seuil, N = _swing_matrix(cfg)
        au_mieux = int(np.count_nonzero(sw.max(axis=1) < seuil))
        wls, src = _best_wl_du_dernier_run(N)
        if wls:
            idx = [int(np.argmin(np.abs(lams - w))) for w in wls]
            reel = int(np.count_nonzero([sw[i, idx[i]] < seuil for i in range(N)]))
            aff = f"{reel} / {N}"
        else:
            aff = "pas d'artefact"
        print(f"  {nom:<10}{N:>8}{seuil:>8.3f}{f'{au_mieux} / {N}':>21}{aff:>26}")
        if wls:
            bas = [(i, float(sw[i, idx[i]])) for i in range(N) if sw[i, idx[i]] < seuil]
            if bas:
                print(f"             couches concernees (indice, swing) : "
                      f"{[(i, round(v, 4)) for i, v in bas[:8]]}")
            print(f"             lambda lues dans {src}")

    print("\n  🔑 « AU MIEUX » = swing a la meilleure lambda de la grille : une couche sous le")
    print("     seuil y est indefendable optiquement, quelle que soit la strategie.")
    print("  🔑 « AU CHOIX REEL » = swing a la lambda que la Phase A a retenue : c'est CE que")
    print("     `rate_by_swing` verra, et c'est le seul chiffre qui dit si le critere agira.")
    print("\n  ⚠️ Swing calcule sur le signal NOMINAL, sans convolution par la fente. Le critere")
    print("     est donc le meme a 2 nm et a 0,5 nm -- il capture une couche intrinsequement")
    print("     pauvre, pas un run degrade par le bruit de fente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
