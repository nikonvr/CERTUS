"""LIRE CE QUE COUTE LE PARALLELISME -- un run SEUL contre le meme run a DEUX.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_solo_vs_parallele.py <solo.log> <parallele.log>

## 🔑 LA SEULE QUESTION QU'IL REPOND, ET CE QU'ELLE DECIDE

Le 2026-08-23, monter la bande passante memoire de **+69 %** (2133 -> 3600 MHz, DOCP) n'a rien
rendu sur la duree d'un run. La conclusion *« le goulot est la bande passante memoire »* du
2026-08-22 est donc REFUTEE -- voir §0000 de `docs/REPRENDRE_ICI.md`.

Reste la question qu'elle laisse ouverte : **la machine passe-t-elle a l'echelle ?** Un run seul
le dit, et c'est ce qui decide si des COEURS se paient :

    debit a deux ~ 2,0x celui d'un seul   ->  la machine passe a l'echelle, plus de coeurs paient
    debit a deux ~ 1,0x                   ->  quelque chose de PARTAGE sature ; le cache L3 du
                                              5700G (16 Mo, la moitie d'un 5800X) est le suspect,
                                              et c'est un achat DIFFERENT

📏 Repere historique a battre ou a confirmer : **+29 % de debit a deux runs**, mesure le
2026-08-22 sur la configuration a 2133 MHz, soit un facteur **1,29** sur les 2,00 possibles.

## 🔴 CE QUE CET OUTIL REFUSE DE FAIRE

**Il ne compare aucune duree tant qu'il n'a pas prouve que le travail est le MEME.** A graine et
code identiques, les RMSE par bloc doivent etre identiques au bit ; s'ils divergent, les deux
runs n'ont pas fait la meme chose et l'ecart de duree ne mesure plus le parallelisme. Dans ce cas
il s'arrete au lieu de rendre un tableau qui aurait l'air juste.

⚠️ **Et il rappelle que n = 1.** Un run seul contre un run a deux, c'est UNE mesure dans chaque
condition. Il n'existe aucune estimation de la dispersion de run a run sur cette machine -- c'est
l'erreur exacte qui a ete corrigee le 2026-08-23 a propos du DOCP, ou deux graines lancees
ENSEMBLE avaient ete presentees a tort comme deux repetitions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 🔴 Le journal ne porte que `HH:MM:SS`, sans date. Un run qui traverse minuit rendrait des
# durees negatives, et une duree negative RESSEMBLE a un bug d'analyse plutot qu'a ce qu'elle
# est. On rattrape le passage de jour au lieu de le taire.
_TS = re.compile(r"^(\d{2}):(\d{2}):(\d{2})")
_DEBUT = re.compile(r"\[Block (\d+)\] Mining found (\d+) strategies")
_FIN = re.compile(r"\[Block (\d+)\] Best strategy ready: RMSE=([\d.]+)")


def _secondes(ligne: str) -> int | None:
    m = _TS.match(ligne)
    if not m:
        return None
    h, mi, s = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s


def lire(chemin: Path) -> dict[int, dict[str, object]]:
    """Rend {n_blocs: {"t0", "t1", "rmse", "mines"}} pour les blocs TERMINES."""
    blocs: dict[int, dict[str, object]] = {}
    precedent = -1
    jour = 0
    for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
        t = _secondes(ligne)
        if t is None:
            continue
        if t < precedent - 3600:      # recul franc : on a change de jour
            jour += 1
        precedent = t
        t += jour * 86400

        if (m := _DEBUT.search(ligne)):
            blocs.setdefault(int(m.group(1)), {})["t0"] = t
            blocs[int(m.group(1))]["mines"] = int(m.group(2))
        elif (m := _FIN.search(ligne)):
            b = blocs.setdefault(int(m.group(1)), {})
            b["t1"] = t
            b["rmse"] = m.group(2)
    return {n: b for n, b in blocs.items() if "t0" in b and "t1" in b}


def _mmss(s: float) -> str:
    return f"{int(s) // 60}:{int(s) % 60:02d}"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    p_solo, p_par = Path(sys.argv[1]), Path(sys.argv[2])
    lib_solo = sys.argv[3] if len(sys.argv) > 3 else "SEUL"
    lib_par = sys.argv[4] if len(sys.argv) > 4 else "a DEUX"
    for p in (p_solo, p_par):
        if not p.exists():
            print(f"🔴 introuvable : {p}")
            return 2

    solo, par = lire(p_solo), lire(p_par)
    communs = sorted(set(solo) & set(par), reverse=True)
    if not communs:
        print("🔴 aucun bloc TERMINE des deux cotes -- rien a comparer.")
        return 1

    print("=" * 78)
    print("A. EST-CE LE MEME TRAVAIL ? (sans quoi les durees ne mesurent rien)")
    print("=" * 78)
    ecarts = [n for n in communs
              if solo[n]["rmse"] != par[n]["rmse"] or solo[n]["mines"] != par[n]["mines"]]
    for n in communs:
        etat = "🔴 DIFFERENT" if n in ecarts else "identique"
        print(f"  bloc {n:>2}   RMSE {solo[n]['rmse']} / {par[n]['rmse']}   "
              f"mines {solo[n]['mines']} / {par[n]['mines']}   {etat}")
    if ecarts:
        print(f"\n🔴 {len(ecarts)} bloc(s) DIVERGENT. Les deux runs n'ont pas fait le meme")
        print("   travail : l'ecart de duree ne mesure plus le parallelisme. ARRET.")
        return 1
    print(f"\n🟢 {len(communs)} blocs, aucun ecart -- la comparaison porte sur le meme travail.")

    print()
    print("=" * 78)
    print("B. DUREES PAR NOMBRE DE BLOCS")
    print("=" * 78)
    # 🔴 LES EN-TETES ONT MENTI LE 2026-08-24. L'outil ecrivait « a DEUX » et « SEUL » en dur,
    # et il a servi ce jour-la a comparer 2133 MHz contre 3600 MHz -- deux runs A DEUX des deux
    # cotes. Le tableau etait juste, ses colonnes le contredisaient. Un lecteur qui n'aurait pas
    # lance la commande aurait lu l'inverse de ce qui etait mesure. Les libelles se donnent
    # donc en argument, et les CHEMINS sont imprimes : ils, eux, ne peuvent pas mentir.
    print(f"  gauche = {p_par}")
    print(f"  droite = {p_solo}")
    print()
    print(f"  {'bloc':>4}  {lib_par:>10}  {lib_solo:>10}  {'ecart':>8}")
    t_solo = t_par = 0
    for n in communs:
        d_s = solo[n]["t1"] - solo[n]["t0"]
        d_p = par[n]["t1"] - par[n]["t0"]
        t_solo += d_s
        t_par += d_p
        print(f"  {n:>4}  {_mmss(d_p):>10}  {_mmss(d_s):>10}  {(d_s - d_p) / d_p:>+7.1%}")
    print(f"  {'cumul':>4}  {_mmss(t_par):>10}  {_mmss(t_solo):>10}  "
          f"{(t_solo - t_par) / t_par:>+7.1%}")

    print()
    print("=" * 78)
    print("C. CE QUE CELA DECIDE")
    print("=" * 78)
    # 🔴 « SEUL » NE SE LIT PAS DANS UN JOURNAL. Un journal ne porte aucune trace de ce qui
    # tournait a cote de lui. Donne deux journaux PARALLELES a cet outil et il rendait
    # « 2,12x, la machine passe a l'echelle » sans broncher -- c'est arrive le 2026-08-23, en
    # test, et c'est ce qui a fait ecrire ce garde-fou. `mesure_solo_vs_parallele.sh`
    # echantillonne la concurrence PENDANT le run et la consigne ; sans ce releve, on ne
    # conclut pas.
    ctx = p_solo.parent / "CONTEXTE.txt"
    if not ctx.exists():
        print(f"  🔴 REFUS DE CONCLURE : {ctx} est absent.")
        print("     Rien ne prouve que le run de gauche etait SEUL, et cet outil rendrait un")
        print("     facteur d'echelle qui aurait l'air juste. Les sections A et B ci-dessus")
        print("     restent valides -- elles ne dependent pas de la concurrence.")
        print("     Relance la mesure par : bash scripts/mesure_solo_vs_parallele.sh")
        return 1
    releve = dict(
        l.split("#")[0].strip().split("=", 1)
        for l in ctx.read_text(encoding="utf-8", errors="replace").splitlines()
        if "=" in l.split("#")[0]
    )
    n_sondes = int(releve.get("max_processus_sonde", "0") or 0)
    n_autres = int(releve.get("max_autres_python", "0") or 0)
    if n_sondes > 2:
        print(f"  🔴 REFUS DE CONCLURE : {n_sondes} processus de sonde vus pendant le run.")
        print("     Une sonde en vaut DEUX -- un second run a donc chevauche celui-ci, qui")
        print("     n'etait pas seul. La mesure ne repond pas a la question posee.")
        return 1
    if n_autres:
        print(f"  ⚠️ {n_autres} processus python etranger(s) vus pendant la mesure : ils ont")
        print("     pris du CPU. Le facteur ci-dessous est donc un PLANCHER.")
        print()
    # 🔑 Le debit, et non la duree : a deux runs on produit DEUX resultats en t_par, seul on en
    # produit UN en t_solo. Le facteur vaut donc 2 x t_solo / t_par -- 2,00 si la machine passe
    # parfaitement a l'echelle, 1,00 si le second run ne rapporte rien du tout.
    facteur = 2.0 * t_solo / t_par
    occupation = (t_par / t_solo) / 2.0
    print(f"  debit a deux runs = {facteur:.2f}x celui d'un run seul   (2,00 = parfait, "
          f"1,00 = nul)")
    print("  repere du 2026-08-22 a 2133 MHz : 1,29x")
    print()
    # 🔴 CE BLOC A DIT LE CONTRAIRE LE 2026-08-23, ET C'ETAIT UNE ERREUR DE RAISONNEMENT.
    # Il concluait « facteur bas -> quelque chose de PARTAGE sature -> le cache L3 -> acheter un
    # CPU a gros cache ». Il sautait par-dessus l'explication la plus simple, qui suffit :
    #
    #   un run SEUL occupe deja une fraction f de la machine.  Deux runs en demandent 2f.
    #   Si 2f > 1 ils se partagent le peu qui reste et chacun ralentit d'un facteur 2f.
    #      -> T_a_deux / T_seul = 2f,  donc  f = (T_a_deux / T_seul) / 2
    #
    # Aucune contention de cache n'est requise pour rendre compte d'un facteur bas : une machine
    # simplement PLEINE le produit. Ne nommer un coupable exotique qu'apres avoir elimine
    # celui-la -- c'est la meme faute que « le goulot est la bande passante », affirmee sans
    # jamais avoir fait varier la memoire.
    print(f"  🔑 UN RUN SEUL OCCUPE DEJA {occupation:.0%} DE LA MACHINE.")
    print(f"     (deduit du seul rapport des durees : T_a_deux / T_seul = {t_par / t_solo:.2f})")
    print()
    if occupation >= 0.85:
        print("  🔴 LA MACHINE EST PLEINE AVEC UN SEUL RUN. Le second n'a presque plus rien a")
        print("     prendre : c'est cela, et non un goulot exotique, qui explique le facteur.")
        print("     👉 Le levier est le NOMBRE DE COEURS -- il n'y a pas de mystere a resoudre")
        print("        avant d'acheter, seulement des coeurs qui manquent.")
    elif occupation <= 0.60:
        print("  🟢 LA MACHINE A DE LA MARGE avec un run, et pourtant le second rend peu :")
        print("     LA, quelque chose de PARTAGE sature vraiment. Ce n'est pas la bande")
        print("     passante (refutee le 2026-08-23) -- le L3 de 16 Mo du 5700G devient le")
        print("     suspect, et c'est un achat DIFFERENT d'un simple ajout de coeurs.")
    else:
        print("  🟠 ZONE INTERMEDIAIRE : l'occupation explique une partie du facteur, pas tout.")
        print("     Ni les coeurs ni le cache ne sont designes seuls.")
    print()
    print("  ⚠️ CE QUE CE CHIFFRE NE SEPARE PAS. L'occupation ci-dessus est DEDUITE des durees,")
    print("     pas observee. Pour separer « machine pleine » de « ressource partagee qui")
    print("     sature », il faut le CPU % REELLEMENT consomme par un run seul : s'il est")
    print("     nettement plus BAS que l'occupation deduite, l'ecart est de la contention.")
    print("     📏 Repere existant, jamais refait depuis : 74 % le 2026-08-22, a 2133 MHz.")
    print()
    print("  ⚠️ n = 1 DANS CHAQUE CONDITION. La dispersion de run a run sur cette machine")
    print("     n'est toujours pas mesuree : rejouer un run a l'identique la donnerait, et")
    print("     c'est elle qui dit si les ecarts ci-dessus sont seulement lisibles.")
    print()
    print("  🔒 ET AUCUN ACHAT NE SE DECIDE SUR CE SEUL TABLEAU : les candidats a gros cache")
    print("     comme a beaucoup de coeurs n'ont PAS d'iGPU, et cette machine n'a pas de carte")
    print("     graphique. L'addition en comprend une.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
