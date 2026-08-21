"""LIRE UNE CELLULE MULTISEED -- les trois lectures posees d'avance, et rien d'autre.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\lire_multiseed.py <journal.log> [artefact.json]

L'artefact est devine a partir de la ligne « consigne dans ... » du journal s'il n'est pas donne.

## 🔑 CE QUE CET OUTIL REFUSE DE FAIRE

Il ne cherche PAS a conclure. Il rend les trois grandeurs qui ont ete declarees AVANT le run
(`PLAN_PRODUCTION_2026-08-20.md` §20.4), et le fait qu'elles soient declarees d'avance est ce qui
leur donne de la valeur : on ne choisit pas, apres coup, la lecture qui arrange.

    1. LA COURBE DE SATURATION DE L'UNION -- combien chaque graine apporte de PLANS NEUFS, et a
       partir de quand elle n'apporte plus rien. C'est la seule facon de savoir si K = 5 etait
       justifie ou si K = 2 suffisait. Un multiseed dont la 5e graine n'apporte rien est un
       multiseed paye trop cher, et il faut pouvoir le dire.

    2. LES OCCURRENCES DE 685 nm dans les candidates ENGENDREES par ELITE. Controle du §18.4 :
       le levier atteint-il ce qu'il vise ? Il valait 2 sur 4226 a la reference. 🔴 Ce controle
       est INDEPENDANT du resultat en deposables -- un levier peut atteindre sa cible et ne rien
       debloquer, et c'est une information differente de « il ne l'atteint pas ».

    3. LES DEPOSABLES ET LE MEILLEUR SEEL, avec la cible de 0,5692 comme repere.
       ⚠️ `SEEL = 2*sqrt(score)` n'a de sens que sur une strategie DEPOSABLE. Sur une population
       qui plante, le score est un REPLI et `CLAUDE.md` §21 interdit de le citer comme une
       performance. L'outil rend donc « aucun » plutot qu'un chiffre flatteur.

## ⚠️ LA REGLE DE COMPTAGE DES HISTOGRAMMES, a ne pas perdre

Une candidate compte UNE FOIS par λ DISTINCTE de ses blocs. Les totaux somment donc a plus que
le nombre de candidates. Un compte dit « combien de candidates ont utilise cette λ », jamais
« combien de blocs ». Confondre les deux serait un rapport mal echelonne.
"""

from __future__ import annotations

import collections
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Le niveau que la graine 77 atteint sur ce composant, et la cible de 👤.
SEEL_CIBLE = 0.5692

#: Tolerance de 👤 : 95 % des depots doivent aboutir.
CRASH_TOL = 0.05

#: La λ des 544 deposables sur 547, et la cible du controle du §18.4.
LAMBDA_CIBLE = "685"

#: Ce que la reference engendrait pour cette λ, sur 4226 candidates.
REF_685 = 2

#: 🔴 LES NOMBRES DE BLOCS DEGENERES, A EXCLURE DE TOUTE MOYENNE.
#:
#: `_compute_blocks_range_contractual` FORCE 1, 2 et `num_layers` dans la plage, et ils ne
#: ressemblent a rien du reste : le bloc 75 (une couche par bloc) ne fait miner que 2
#: strategies, donc les 5 graines y voient forcement la meme chose et « la graine 5 n'apporte
#: rien » y est une tautologie, pas une mesure. Les 547 deposables de la graine 77 vivent
#: TOUTES a 7-13 blocs : c'est la seule zone ou la saturation de l'union veut dire quelque
#: chose.
BLOCS_DEGENERES = (1, 2, 75)

#: Nombre minimal de nombres de blocs INFORMATIFS avant d'oser un verdict.
MIN_BLOCS_POUR_VERDICT = 3


def lire_saturation(txt: str) -> dict[int, list[tuple[int, int, int]]]:
    """Par nombre de blocs, la liste (graine, survivantes, plans neufs) dans l'ordre du run."""
    rx = re.compile(
        r"\[Block (\d+)\] graine (\d+) : (\d+) notees, (\d+) survivantes, (\d+) PLANS NEUFS"
    )
    out: dict[int, list[tuple[int, int, int]]] = collections.defaultdict(list)
    for m in rx.finditer(txt):
        blk, graine, _notees, surv, neufs = (int(x) for x in m.groups())
        out[blk].append((graine, surv, neufs))
    return out


def lire_wl(txt: str) -> dict[str, dict[str, int]]:
    """Les histogrammes [ELITE-WL], cumules sur tous les rounds."""
    rx = re.compile(r"\[ELITE-WL\] Round \d+ exit=\w+ (generated|rejected_\w+) (.*)")
    agg: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for m in rx.finditer(txt):
        quoi, reste = m.groups()
        if reste.strip() in ("(none)", ""):
            continue
        tronque = False
        for jeton in reste.split():
            if jeton.startswith("[+"):
                tronque = True
                break
            if ":" not in jeton:
                continue
            cle, _, n = jeton.rpartition(":")
            try:
                agg[quoi][cle] = agg[quoi].get(cle, 0) + int(n)
            except ValueError:
                continue
        if tronque:
            agg[quoi]["__TRONQUE__"] = agg[quoi].get("__TRONQUE__", 0) + 1
    return agg


def lire_bandes(txt: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in re.finditer(r"reject_crash_bands (.*)", txt):
        for jeton in m.group(1).split():
            if ":" not in jeton:
                continue
            cle, _, n = jeton.rpartition(":")
            try:
                out[cle] = out.get(cle, 0) + int(n)
            except ValueError:
                continue
    return out


def lire_gate(txt: str) -> int:
    """Combien de fois la borne de confiance a change le verdict. 0 = elle n'a rien attrape."""
    return len(re.findall(r"\[GATE\] strat", txt))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    journal = Path(sys.argv[1])
    if not journal.is_file():
        print(f"🔴 journal introuvable : {journal}")
        return 2
    txt = journal.read_text(encoding="utf-8", errors="replace")

    art = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    if art is None:
        m = re.findall(r"consigne dans (reports[/\\][^\s]+\.json)", txt)
        if m:
            cand = ROOT / m[-1].replace("\\", "/")
            art = cand if cand.is_file() else None

    fini = "consigne dans" in txt
    print("=" * 78)
    print(f"  {journal.name}   —   {'TERMINE' if fini else '🔴 EN COURS OU INTERROMPU'}")
    print("=" * 78)
    if not fini:
        print("\n⏳ CE RUN N'A PAS ABOUTI. Tous les comptes ci-dessous sont PARTIELS, et les")
        print("   verdicts sont volontairement SUPPRIMES. Un compte partiel compare a un compte")
        print("   complet n'est pas une mesure : c'est la facon la plus economique de se")
        print("   tromper, et ce depot en a paye cinq exemples dans la seule journee du 20/08.")

    # ── 1. saturation de l'union ────────────────────────────────────────────
    sat = lire_saturation(txt)
    print("\n1. COURBE DE SATURATION DE L'UNION — ce que chaque graine apporte VRAIMENT")
    if not sat:
        print("   🔴 aucune ligne de criblage multiseed : le levier n'a pas agi.")
    else:
        par_rang: dict[int, list[int]] = collections.defaultdict(list)
        exclus = []
        for blk in sorted(sat, reverse=True):
            lignes = sat[blk]
            det = "  ".join(f"g{g}:+{n}" for g, _s, n in lignes)
            marque = "  (DEGENERE, hors moyenne)" if blk in BLOCS_DEGENERES else ""
            print(f"   bloc {blk:>3} ({len(lignes)} graines) : {det}{marque}")
            if blk in BLOCS_DEGENERES:
                exclus.append(blk)
                continue
            for rang, (_g, _s, n) in enumerate(lignes):
                par_rang[rang].append(n)

        n_info = len(sat) - len(exclus)
        if exclus:
            print(f"\n   blocs exclus des moyennes : {exclus} — forces par le code et "
                  f"degeneres (le bloc 75 ne fait miner que 2 strategies, donc « la graine 5 "
                  f"n'apporte rien » y est une tautologie).")
        if n_info < MIN_BLOCS_POUR_VERDICT:
            print(f"   🔴 SEULEMENT {n_info} nombre(s) de blocs informatif(s) : "
                  f"AUCUNE MOYENNE, AUCUN VERDICT. Il en faut {MIN_BLOCS_POUR_VERDICT}.")
        else:
            print("\n   APPORT MOYEN PAR RANG DE GRAINE — la lecture qui dit si K etait "
                  f"justifie (sur {n_info} nombres de blocs informatifs) :")
            for rang in sorted(par_rang):
                v = par_rang[rang]
                print(f"     graine n°{rang + 1} : {sum(v) / len(v):6.2f} plans neufs en "
                      f"moyenne   (total {sum(v)})")
            derniers = par_rang.get(max(par_rang), [])
            if derniers and sum(derniers) == 0:
                print("   🔴 LA DERNIERE GRAINE N'APPORTE RIEN sur les blocs informatifs : "
                      "K est trop grand, elle est payee pour rien.")

    # ── 2. le levier atteint-il sa cible ? ──────────────────────────────────
    wl = lire_wl(txt)
    gen = wl.get("generated", {})
    print(f"\n2. CONTROLE DU §18.4 — ELITE engendre-t-il {LAMBDA_CIBLE} nm ?")
    if not gen:
        print("   🔴 aucun histogramme [ELITE-WL] : ELITE n'a pas tourne, ou pas journalise.")
    else:
        n685 = gen.get(LAMBDA_CIBLE, 0) + gen.get(LAMBDA_CIBLE + ".0", 0)
        n_tronq = gen.pop("__TRONQUE__", 0)
        top = sorted(gen.items(), key=lambda kv: -kv[1])[:10]
        print("   λ les plus engendrees : " + "  ".join(f"{k}:{v}" for k, v in top))
        print(f"   🔑 {LAMBDA_CIBLE} nm : {n685} candidates   "
              f"(reference : {REF_685} sur 4226)")
        # 🔴🔴 LE COMPTE D'UNE λ RARE N'EST PAS LISIBLE DANS CE FORMAT DE JOURNAL.
        #
        # `_format_wl_histogram` (`certus_strat_consensus.py`) n'affiche que les 14 λ LES PLUS
        # LOURDES et resume le reste en « [+N wl not shown] ». Or 685 nm porte 1 a 2
        # candidates par ronde : elle tombe donc presque toujours dans cette queue masquee, et
        # le compte ci-dessus est un PLANCHER, pas une mesure.
        #
        # 📏 La preuve est dans les chiffres eux-memes : 685 nm apparait 5 fois en GENERATION
        # et 11 fois dans les REJETS. Une candidate ne peut pas etre rejetee sans avoir ete
        # engendree -- donc la vue « generated » en manque au moins six.
        #
        # ⚠️ C'est exactement le defaut que la docstring de `_format_wl_histogram` pretend
        # eviter : « une liste tronquee en silence se lit comme une couverture complete ». Elle
        # DIT le nombre de λ omises, ce qui est mieux que rien, mais pas LESQUELLES -- et la λ
        # qu'on cherche est par construction dans la queue.
        #
        # 🔵 LE CORRECTIF, cote production : donner a `_format_wl_histogram` une liste de λ
        # a TOUJOURS afficher, quelle que soit leur place au classement. Trois lignes, et il
        # rend ce controle exploitable. Non fait ici : un run est en vol.
        if n_tronq:
            # 🔑 DEUX CAUSES POSSIBLES, ET ELLES N'ONT PAS LE MEME SENS.
            #
            # Avant le 2026-08-21, `_format_wl_histogram` n'affichait que les 14 λ les plus
            # lourdes -- donc TOUT journal anterieur porte des comptes qui sont des PLANCHERS
            # pour les λ rares, et le correctif ne les rattrape pas : il faut rejouer.
            # Depuis, la troncature ne peut plus venir que du plafond DUR (400 λ), qui ne mord
            # jamais sur la grille reelle de ~301 -- s'il mord, c'est un defaut a regarder.
            print(f"   🔴 {n_tronq} histogramme(s) TRONQUE(S) : le compte de {LAMBDA_CIBLE} nm "
                  f"est un PLANCHER, pas une mesure.")
            print(f"      Si ce journal precede le 2026-08-21, c'est l'ancienne troncature a "
                  f"14 λ -- corrigee depuis, mais elle ne se rattrape pas : REJOUER le run. "
                  f"Sinon le plafond dur a mordu, ce qui ne devrait pas arriver.")
        elif not fini:
            print("   ⏳ RUN INACHEVE : aucun verdict. Le compte ci-dessus est partiel et "
                  "n'est PAS comparable aux 2 sur 4226 de la reference, qui portent sur "
                  "l'integralite de ses rondes.")
        elif n685 > 5 * REF_685:
            print("   🟢 le levier ATTEINT sa cible — la troncature d'enumeration etait bien "
                  "ce qui l'en empechait.")
        elif n685 <= REF_685:
            print("   🔴 le levier N'ATTEINT PAS sa cible — ce n'est donc pas la troncature. "
                  "Il faut regarder les λ des PARENTS eux-memes (§18.4).")
        else:
            print("   🟠 progression faible : ni confirme ni refute, l'ecart est trop petit "
                  "pour trancher.")
        rej = wl.get("rejected_score_non_fini", {})
        r685 = rej.get(LAMBDA_CIBLE, 0) + rej.get(LAMBDA_CIBLE + ".0", 0)
        if r685:
            print(f"   ⚠️ dont {r685} rejetees par la porte de plantage : ELITE regarde "
                  "desormais la, et jette.")

    bandes = lire_bandes(txt)
    if bandes:
        print("\n   bandes de plantage des rejets : "
              + "  ".join(f"{k}:{v}" for k, v in sorted(bandes.items(), key=lambda kv: -kv[1])))
    ng = lire_gate(txt)
    print(f"   lignes [GATE] (desaccords de la borne de confiance) : {ng}"
          + ("   — attendu 0 : la porte n'est pas armee ici (controle negatif)" if ng == 0 else ""))

    # ── 3. le resultat ─────────────────────────────────────────────────────
    print("\n3. LE RESULTAT")
    if art is None:
        print("   🔴 pas d'artefact : le run n'a pas abouti. La sonde n'ecrit qu'a la fin, "
              "donc il n'y a RIEN a lire — ni partiel, ni degrade.")
        return 1
    d = json.loads(art.read_text(encoding="utf-8"))
    S = d.get("strategies") or []
    dep = [s for s in S
           if (s.get("crash_rate") if s.get("crash_rate") is not None else 1.0) <= CRASH_TOL]
    crs = [s.get("crash_rate") for s in S if s.get("crash_rate") is not None]
    print(f"   artefact : {art.name}")
    print(f"   config   : {json.dumps(d.get('config'), ensure_ascii=False)}")
    print(f"   {len(S)} strategies · {len(dep)} DEPOSABLES · "
          f"crash_min {100 * min(crs):.2f} %" if crs else "   (aucune strategie)")
    fam = collections.Counter(str(s.get("origine", "?")).split("(")[0].strip() for s in dep)
    if dep:
        best = min(dep, key=lambda s: s.get("score", float("inf")))
        seel = 2.0 * math.sqrt(float(best["score"])) if best.get("score", -1) >= 0 else None
        print(f"   familles des deposables : {dict(fam.most_common(8))}")
        if seel is not None:
            ecart = 100 * (seel - SEEL_CIBLE) / SEEL_CIBLE
            print(f"   🟢 MEILLEUR SEEL DEPOSABLE : {seel:.4f}   "
                  f"(cible {SEEL_CIBLE:.4f}, ecart {ecart:+.1f} %)")
            print(f"      blocs : {best.get('n_blocs')} · plantage "
                  f"{100 * best['crash_rate']:.2f} % · origine {best.get('origine')}")
    else:
        print("   🔴 AUCUN DEPOSABLE. Le meilleur score est un score de REPLI et "
              "`CLAUDE.md` §21 interdit de le citer comme une performance : aucun SEEL n'est "
              "rendu ici, et c'est deliberé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
