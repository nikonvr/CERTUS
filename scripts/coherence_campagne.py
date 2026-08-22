"""LA COHERENCE D'UNE CAMPAGNE -- ce qu'on verifie quand personne ne regarde.

    python scripts/coherence_campagne.py reports/nuit75_2026-08-22

👤, 2026-08-22 : *« toutes les 30mn verifie la coherence des resultats et si probleme,
corrige »*. Ce script est ce que « verifier la coherence » veut dire concretement.

## 🔑 IL NE VERIFIE PAS QUE LES CHIFFRES SONT BONS -- IL VERIFIE QU'ILS SONT COMPARABLES

Un resultat faux qui a l'air juste est le risque numero un de ce depot. Les six controles
ci-dessous cherchent donc les incoherences qui rendraient une comparaison MENSONGERE, pas les
valeurs qui deplaisent :

  1. UN SEUL CODE. Tous les artefacts d'une campagne doivent porter le meme `instrument`
     (le commit). 📏 Le 2026-08-22, changer `rate_by_swing` en cours de serie aurait melange
     deux versions sans que rien ne le dise -- c'est pour cela que les anciens ont ete archives.
  2. UNE SEULE PROFONDEUR. `n_screen_runs` et `robustness_num_runs` identiques partout : un
     `crash_min` ne se lit qu'avec son N, 4,00 % vaut 2/50 ou 6/150 selon la passe.
  3. UNE SEULE FENTE, UN SEUL MODE. Sinon les SEEL ne se comparent pas.
  4. AUCUN ARTEFACT VIDE. `verdict = OK` avec zero strategie est le symptome d'un plafond
     atteint -- quatre mesures de 91 min ont ete perdues ainsi, et leur artefact existait.
  5. LES SURCHARGES SONT ATTENDUES. Seules `union*` (notation finale) et `mt*` (multi-temoin)
     sont legitimes ; toute autre etiquette signale un run qui n'est pas ce qu'on croit.
  6. LES DUREES SONT PLAUSIBLES. Une mesure qui dure EXACTEMENT le plafond est le signe d'un
     `WAIT_TIMEOUT`, qui rend `None` -- ce qui RESSEMBLE a un resultat.

Rend 0 si tout est coherent, 1 s'il y a un point a instruire. ⚠️ Un signalement n'est pas une
erreur : c'est une phrase a LIRE.
"""

from __future__ import annotations

import glob
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RACINE = Path(__file__).resolve().parents[1]
TOLERANCE_PLANTAGE = 0.05
#: Etiquettes de surcharge legitimes dans une campagne orchestree.
TAGS_ATTENDUS = re.compile(r"^(union\d{8}_\d{6}|mt\d+)$")


def _seel(score: float) -> float:
    return 2.0 * (float(score) ** 0.5)


def _artefacts_de(journal_dir: Path) -> list[tuple[Path, dict]]:
    """Les artefacts ecrits DEPUIS le debut de la campagne, reperes par leur date."""
    debut = min((p.stat().st_mtime for p in journal_dir.glob("journal_*.log")), default=0.0)
    out = []
    for f in glob.glob(str(RACINE / "reports" / "blocs_vs_plantage_*.json")):
        p = Path(f)
        if p.stat().st_mtime < debut - 60:
            continue
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            out.append((p, {}))
    return sorted(out, key=lambda x: x[0].stat().st_mtime)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    jdir = RACINE / (args[0] if args else "reports/nuit75_2026-08-22")
    if not jdir.is_dir():
        print(f"🔴 dossier introuvable : {jdir}")
        return 1

    arts = _artefacts_de(jdir)
    print("=" * 78)
    print(f"COHERENCE DE CAMPAGNE -- {jdir.name} · {len(arts)} artefact(s)")
    print("=" * 78)
    if not arts:
        print("  (aucun artefact ecrit pour l'instant -- la campagne demarre)")
        return 0

    points: list[str] = []
    vus: dict[str, set] = defaultdict(set)

    for p, d in arts:
        if not d:
            points.append(f"{p.name} : ILLISIBLE")
            continue
        st = d.get("strategies") or []
        # 4. artefact vide
        if d.get("verdict") == "OK" and not st:
            points.append(f"{p.name} : verdict OK mais ZERO strategie -- plafond atteint ?")
        if d.get("verdict") not in ("OK", None):
            points.append(f"{p.name} : verdict = {d.get('verdict')!r}")
        vus["instrument"].add(d.get("instrument"))
        vus["mode"].add(d.get("mode"))
        prof = d.get("profondeur") or {}
        vus["n_screen"].add(prof.get("n_screen_runs"))
        vus["n_full"].add(prof.get("robustness_num_runs"))
        if st:
            vus["resolution"].add(st[0].get("resolution_nm"))
        # 5. surcharges attendues
        tag = (d.get("config") or {}).get("overrides_tag")
        if tag and not TAGS_ATTENDUS.match(str(tag)):
            points.append(f"{p.name} : etiquette INATTENDUE {tag!r}")

    # 1-3. l'unicite de ce qui doit etre unique
    for cle, libelle in (("instrument", "le COMMIT"), ("mode", "le mode"),
                         ("n_screen", "n_screen_runs"), ("n_full", "robustness_num_runs"),
                         ("resolution", "la fente")):
        valeurs = {v for v in vus[cle] if v is not None}
        if len(valeurs) > 1:
            points.append(f"{libelle} varie d'un artefact a l'autre : {sorted(map(str, valeurs))} "
                          f"-- les resultats ne sont PAS comparables")
        elif valeurs:
            print(f"  🟢 {libelle:22s} : {valeurs.pop()}")

    # 6. durees plausibles
    for jl in sorted(jdir.glob("journal_*.log")):
        txt = jl.read_text(encoding="utf-8", errors="replace")
        if "WAIT_TIMEOUT" in txt:
            points.append(f"{jl.name} : contient « WAIT_TIMEOUT » -- une mesure a ete COUPEE")

    # --- ce que la campagne a trouve ---------------------------------------------------
    print()
    print("  RESULTATS")
    for p, d in arts:
        st = d.get("strategies") or []
        if not st:
            continue
        dep = sorted([s for s in st if s.get("crash_rate", 1) <= TOLERANCE_PLANTAGE],
                     key=lambda s: s.get("score", math.inf))
        tag = (d.get("config") or {}).get("overrides_tag") or ""
        marque = " ← CITABLE" if str(tag).startswith("union") else (
            f" ← multi-temoin" if str(tag).startswith("mt") else "")
        rate = ""
        if dep:
            avec = sum(1 for s in dep if s.get("rate_layers"))
            rate = f" · {avec}/{len(dep)} avec Rate"
            if dep[0].get("rate_layers"):
                rate += f" (gagnante : couches {dep[0]['rate_layers']})"
        print("    %-14s s%-5s %5d strats %5d dep %s%s%s" % (
            d.get("composant"), d.get("seed"), len(st), len(dep),
            f"SEEL {_seel(dep[0]['score']):.4f}" if dep else "--", rate, marque))

    print()
    print("=" * 78)
    if points:
        for pt in points:
            print(f"  🔴 {pt}")
        print(f"\n  {len(points)} point(s) a instruire.")
        return 1
    print("  🟢 0 point a instruire -- tous les artefacts sont COMPARABLES entre eux.")
    print("  ⚠️ Cela ne dit PAS que les chiffres sont bons : cela dit qu'ils se comparent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
