"""Pourquoi un sous-empilement plante : la CAUSE par couche, pas seulement le taux.

    .venv\\Scripts\\python.exe scripts\\diag_substack.py example/example_strat/JSON-strat-99c-partB.json

Un taux de plantage dit qu'on echoue ; il ne dit pas de quoi. Le noyau distingue trois
causes, et elles appellent des remedes OPPOSES :

  * `level_unreachable` -- le niveau d'arret vise n'est pas atteignable : le signal est trop
    PLAT, ou l'arret tombe hors de la bande accessible. On corrige en changeant de longueur
    d'onde, pas en durcissant un seuil.
  * `tp_miscount` -- les extrema sont mal comptes : le signal est trop BRUITE devant le
    seuil, ou il ondule trop. On corrige en durcissant le seuil, pas en changeant de lambda.
  * `non_monotonic` -- la relation epaisseur/transmission n'est pas monotone sur la plage.

🔴 Confondre les deux premieres conduit a appliquer le remede de l'une au probleme de
l'autre, et a conclure que « rien ne marche ».

Rend aussi la DISTRIBUTION des taux de plantage sur toutes les strategies evaluees : un
« 98 % » sur la meilleure ne dit pas s'il y avait des candidates a 10 % ou si tout le monde
etait a 100 %. Les deux situations n'ouvrent pas les memes suites.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_examples as B  # noqa: E402
from CERTUS_STRAT import CertusStratApp  # noqa: E402


def main() -> int:
    cfg = sys.argv[1] if len(sys.argv) > 1 else "example/example_strat/JSON-strat-99c-partB.json"
    mode = sys.argv[2] if len(sys.argv) > 2 else "fast"

    B.qapp()
    B.autoanswer_dialogs(True)
    app = CertusStratApp()
    app.load_configuration(str(ROOT / cfg))
    if "execution_mode" in getattr(app, "widgets", {}):
        app.widgets["execution_mode"].setCurrentText(mode)

    overrides = {"show_plots": False, "robustness_seed": 42,
                 "monochromator_resolution_nm": 2.0, "search_resolution": False}
    _collect = app.collect_params
    seen = {"n": 0}

    def collect_with_overrides(*a, **kw):
        p = _collect(*a, **kw)
        p.update(overrides)
        seen["n"] += 1
        return p

    app.collect_params = collect_with_overrides
    n_layers = len(app.collect_params().get("stack_multipliers") or [])
    sys.stderr.write(f"\n{cfg} | mode {mode} | {n_layers} couches\n")

    app.run_workflow(23)
    res = B.wait_for(app.worker) if getattr(app, "worker", None) else None
    if seen["n"] == 0:
        raise SystemExit("collect_params jamais appele : les surcharges n'ont pas atteint le calcul")

    strats = ((res or {}).get("final_results", {}) or {}).get("all_strategies_results", [])
    if not strats:
        print("RESULT=None -- aucune strategie rendue. Ce n'est PAS 'tout plante'.")
        return 1

    print("\n" + "=" * 76)
    print(f"{cfg}  --  {n_layers} couches, sur verre NU")
    print("=" * 76)

    rates = sorted(float(s.get("crash_rate", 1.0)) for s in strats)
    print(f"\n{len(strats)} strategies evaluees. Distribution du taux de plantage :")
    for lo, hi in ((0, 0.001), (0.001, 0.05), (0.05, 0.5), (0.5, 0.99), (0.99, 1.01)):
        n = sum(1 for r in rates if lo <= r < hi)
        if n:
            print(f"   {lo:>5.0%} a {hi:>5.0%} : {n:4d} strategies  {'#' * min(46, n)}")
    print(f"   meilleure : {rates[0]:.1%}   mediane : {rates[len(rates) // 2]:.1%}")
    if rates[0] < 0.05:
        print("   🟢 au moins une strategie passe sous la tolerance de 5 %")
    else:
        print("   🔴 AUCUNE strategie ne passe sous 5 % : tout score rendu est un REPLI")

    # 🔴 LE CONTROLE QUI DEMELE LE PARADOXE. Une strategie a 0 % de plantage passe la porte,
    # recoit un score FINI, et devrait donc sortir AVANT une strategie a 98 % dont le score
    # vaut l'infini. Si ce n'est pas le cas, c'est que les deux ne sont pas comparables --
    # typiquement parce qu'elles n'ont pas ete evaluees a la meme profondeur. Un « 0 % sur
    # 10 tirages » veut dire « sous 10 % », pas zero.
    zero = [s for s in strats if float(s.get("crash_rate", 1.0)) < 1e-9]
    print(f"\nLes {len(zero)} strategies annoncees a 0 % de plantage :")
    for s in zero[:6]:
        sc = s.get("robustness_score")
        st = s.get("strategy") or {}
        finite = isinstance(sc, (int, float)) and sc == sc and sc != float("inf")
        print(f"   id={str(st.get('id', '?')):<12} score={str(sc)[:22]:<22} "
              f"fini={finite}  origine={str(st.get('origin', '?'))[:26]}")
    if zero:
        sc0 = strats[0].get("robustness_score")
        print(f"   -> score de la strategie RETENUE (rang 0) : {sc0}")
        print("   Si les scores ci-dessus sont finis et MEILLEURS, le classement est en cause.")
        print("   S'ils sont infinis ou absents, ces strategies n'ont PAS ete evaluees a fond :")
        print("   leur « 0 % » vient d'un criblage court et ne vaut pas comme mesure.")

    best = strats[0]
    causes = best.get("crash_causes") or {}
    if causes:
        print("\nCauses, sur la strategie retenue :")
        for k, v in sorted(causes.items(), key=lambda kv: -float(kv[1] or 0)):
            print(f"   {k:<26} {float(v):.1%}")

    prof = best.get("crash_by_layer") or {}
    if prof and prof.get("total"):
        tot = prof["total"]
        lvl = prof.get("level_unreachable") or [0] * len(tot)
        tpm = prof.get("tp_miscount") or [0] * len(tot)
        print("\nPlantages par couche (couches concernees seulement) :")
        print("   couche  total  niveau_inatteignable  comptage_faux")
        for i, t in enumerate(tot):
            if t:
                print(f"   {i:>6}  {t:>5}  {lvl[i]:>20}  {tpm[i]:>13}")
        worst = max(range(len(tot)), key=lambda i: tot[i])
        print(f"\n   couche la plus fautive : {worst} ({tot[worst]} tirages)")
    else:
        print("\n(aucun profil de plantage par couche dans le resultat)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
