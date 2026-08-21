"""FABRIQUER LES RAMPES DE LANCEMENT D'UN COMPOSANT, a partir de plusieurs graines.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\generer_rampes.py r75x2 42 77 101 202
    C:\\envs\\certus\\Scripts\\python.exe scripts\\generer_rampes.py r75x2 42 77 --relire-seulement

## 🔑 POURQUOI CE SCRIPT EXISTE

📏 Le 2026-08-21, `r75x2` a 2 nm est passe de **0 deposable sur 1617** a **197 sur 1810**, SEEL
**0,5676 nm**, sur le chemin de production et sans une seule surcharge. Ce qui a produit ce
resultat n'est PAS un algorithme : c'est une METHODE, executee a la main.

    1. lancer le composant sur K graines
    2. recolter les strategies deposables des graines qui en trouvent
    3. garder les meilleures, les ecrire en plans
    4. les declarer en `injected_strategies` dans la configuration du composant
    5. relancer -- la graine qui echouait trouve

Cette methode n'existait que dans l'historique d'une session. Ce script la fixe.

🔑 CE QUE CELA CHANGE, ET C'EST L'ESSENTIEL. L'objection « le resultat est specifique a r75x2 »
tombe en grande partie : un composant neuf obtient ses rampes en une commande. La circularite
devient une **etape assumee du procede** au lieu d'un accident methodologique.

## 🔴 CE QUE LES RAMPES SONT, ET CE QU'ELLES NE SONT PAS

📏 Mesure du 2026-08-21 : les rampes elles-memes sont **eliminees au criblage** -- elles
n'apparaissent pas dans la population finale. Ce sont leurs **descendants ELITE** qui survivent,
et la gagnante est a **deux mouvements** de sa rampe (un pas de λ, un pas de frontiere).

    Une rampe est un POINT DE DEPART, jamais une solution.

Et le mecanisme est compris : sans rampe, ELITE ne retient **0 candidate sur 2472**, parce que
**250 parents sur 250 plantent a 100 %** -- il n'y a aucun gradient a gravir. Avec rampes,
19,7 % des parents plantent a 0-4 %, et le rendement passe a 6,12 %. Les rampes n'apportent pas
de la diversite : elles apportent de la FAISABILITE.

🔴 CE QUE CE SCRIPT REFUSE, ET C'EST LE PLUS IMPORTANT. Un artefact d'avant le 2026-08-20 ne
porte PAS le detail des blocs -- `blocs: null`, `lambdas: [null, ...]`. La premiere version de
ce script en a tire UNE rampe au plan VIDE, qui avait l'air d'un resultat. Ces artefacts sont
desormais REFUSES, et leurs graines rangees dans un TROISIEME etat -- ni steriles, ni fecondes,
**a remesurer**. Confondre les deux ferait conclure « la graine ne trouve rien » la ou on n'a
tout simplement pas la donnee.

## 🔴 LA CIRCULARITE EST REELLE, ELLE EST ECRITE, ET ELLE NE DOIT PAS ETRE TUE

Un resultat obtenu avec des rampes **n'est PAS une decouverte autonome** : l'information vient
des graines qui ont reussi. Le fichier produit porte cette phrase, et tout document qui cite un
chiffre obtenu ainsi doit la porter aussi.

⚠️ Et il y a une seconde circularite, plus insidieuse : si les rampes sont **choisies** sur des
mesures a la graine G puis **remesurees** a la graine G, le chiffre est biaise vers le bas --
c'est la malediction du vainqueur, chiffree a **+12,9 %** le 2026-08-15. Ce script journalise la
graine d'origine de chaque rampe **precisement pour qu'on puisse verifier a une autre graine**.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PY = sys.executable

#: 👤 La porte : 95 % des depositions doivent se terminer.
TOLERANCE_PLANTAGE = 0.05

#: Combien de rampes garder. 🔑 CE N'EST PAS UN NOMBRE INVENTE : c'est `elite_parent_top_k`,
#: le nombre de parents qu'ELITE prend (`certus_strat_consensus.py`, defaut 10). Le metier
#: d'une rampe est d'etre parent -- en garder plus ne sert a rien, en garder moins prive ELITE
#: de directions. Si le defaut du noyau change, change celui-ci avec.
RAMPES_PAR_DEFAUT = 10

#: Le mode de la sonde. `deep` est celui de toutes les mesures de reference.
MODE = "deep"


def _plan(blocs: list[dict]) -> tuple:
    """Le plan comme suite de triplets `(debut, fin, λ)`. C'est l'espace ou ELITE se deplace."""
    return tuple(
        (int(b["start"]), int(b["end"]), float(b["wavelength"]))
        for b in (blocs or [])
        if b.get("wavelength") is not None
    )


def _distance(a: tuple, b: tuple) -> int:
    """Nombre de blocs qui different. Deux nombres de blocs differents = maximalement loin.

    🔑 POURQUOI UNE DISTANCE ET PAS UNE EGALITE. ELITE ne fait qu'UN mouvement par candidate
    -- un pas de λ, ou un pas de frontiere -- et elle les compose d'une ronde a l'autre.
    📏 Mesure du 2026-08-21 : la gagnante est a **3 blocs** de sa rampe, soit un pas de λ
    (615 -> 616) et un pas de frontiere (53 -> 52). Deux plans separes de 1 ou 2 blocs sont
    donc dans le meme voisinage : ELITE atteint l'un depuis l'autre, et en garder les deux
    achete une COPIE au lieu d'une DIRECTION.

    🔴 ET L'EGALITE NE SUFFIT PAS. 📏 Mesure du 2026-08-21 avec l'instrument `[ELITE-PARENTS]`,
    sur `r75x2` a 2 nm : les **cinq** parents qu'ELITE prend a dix blocs portaient **UN SEUL**
    jeu de λ distinct -- des quasi-doublons d'une lignee, un bloc retire ou duplique. Un quota
    sur l'egalite d'un jeu de λ ne les aurait pas separes, puisqu'ils sont EGAUX ; et un quota
    sur le plan complet les aurait tous gardes, puisqu'ils DIFFERENT. Seule une distance
    tranche. Meme lecon, meme methode que `_apply_wl_diversity` dans
    `certus_strat_context.py` -- apprise le matin, et reproduite ici avant correction.

    ⚠️ NE PAS RECOPIER UNE JUSTIFICATION QUE J'AI ECRITE PUIS RETIREE. Une premiere version de
    cette docstring disait que le quota par jeu de λ « ramenait les 547 deposables de la graine
    77 a UNE seule rampe ». Le FAIT est exact, la CAUSE etait fausse : l'artefact lu ne portait
    pas les plans (`blocs: null`), donc tous les jeux etaient vides, donc egaux. Une fois le bon
    artefact resolu, ces 547 deposables portent **217 jeux de λ distincts** -- la graine 77 a une
    population riche, pas une lignee unique.
    """
    if len(a) != len(b):
        return 10**6
    return sum(1 for x, y in zip(a, b) if x != y)


def _porte_les_plans(d: dict) -> bool:
    """Un artefact SANS le detail des blocs ne peut pas produire de rampe.

    🔴 DEFAUT REEL, TROUVE EN ESSAYANT CE SCRIPT. Le detail par bloc n'est enregistre que
    depuis le 2026-08-20 : les artefacts anterieurs portent `blocs: null` et
    `lambdas: [null, null, ...]`. 📏 Sur `blocs_vs_plantage_r75x2_deep_s077.json` -- 547
    strategies deposables -- la premiere version de ce script a produit UNE rampe au plan
    VIDE, qui avait l'air d'un resultat.

        Un artefact sans plans doit etre REFUSE, pas moyenne en silence.
    """
    st = d.get("strategies") or []
    return bool(st) and all(s.get("blocs") for s in st)


def _artefact(composant: str, graine: int) -> Path | None:
    """L'artefact le PLUS RECENT qui porte reellement les plans, pour ce couple.

    ⚠️ Le nom canonique ne suffit pas : la sonde suffixe d'un horodatage quand un homonyme
    existe -- c'est sa protection contre l'ecrasement (interdit 3). Le fichier sans suffixe
    est donc souvent le PLUS ANCIEN, et sur `r75x2` c'est precisement celui qui n'a pas de
    plans. On balaye, on filtre sur le contenu, on prend le plus recent.
    """
    motif = f"blocs_vs_plantage_{composant}_{MODE}_s{graine:03d}*.json"
    cands = sorted((ROOT / "reports").glob(motif), key=lambda q: q.stat().st_mtime, reverse=True)
    sans_plans = []
    for q in cands:
        try:
            d = json.loads(q.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _porte_les_plans(d):
            return q
        if d.get("strategies"):
            sans_plans.append(q.name)
    if sans_plans:
        print(f"    🔴 {len(sans_plans)} artefact(s) trouve(s) mais SANS le detail des blocs :")
        for n in sans_plans[:3]:
            print(f"       {n}")
        print("       Ils precedent l'instrument du 2026-08-20. Il faut REMESURER cette graine.")
    return None


def _lancer(composant: str, graine: int, resolution: float) -> int:
    """Lance la sonde pour une graine. SEQUENTIEL : une mesure, une machine."""
    print(f"  ▶ mesure de la graine {graine} -- cela prend des heures, une seule a la fois")
    env = dict(os.environ, CERTUS_BENCH_TIMEOUT_S="5400")
    jour = ROOT / "reports" / f"generer_rampes_{composant}_s{graine:03d}.log"
    with jour.open("w", encoding="utf-8") as fh:
        r = subprocess.run(
            [PY, "scripts/probe_blocs_vs_plantage.py", composant, MODE, "0", "0",
             str(resolution), "0", str(graine)],
            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, env=env, check=False,
        )
    print(f"    EXIT={r.returncode}, journal dans {jour.relative_to(ROOT)}")
    return r.returncode


def _recolter(chemin: Path) -> list[dict]:
    """Les strategies deposables d'un artefact. Le verdict est verifie, pas suppose."""
    d = json.loads(chemin.read_text(encoding="utf-8"))
    if d.get("verdict") != "OK":
        print(f"    🔴 verdict {d.get('verdict')!r} -- artefact ecarte")
        return []
    st = d.get("strategies") or []
    dep = [s for s in st if (s.get("crash_rate") or 1.0) <= TOLERANCE_PLANTAGE]
    print(f"    {len(st)} strategies, {len(dep)} deposables")
    return dep


def _seel(s: dict) -> float:
    sc = s.get("score")
    return 2.0 * math.sqrt(sc) if isinstance(sc, (int, float)) and sc >= 0 else float("inf")


def choisir_rampes(
    recolte: list[tuple[int, dict]], combien: int
) -> tuple[list[tuple[int, dict]], int, int]:
    """Choisir `combien` rampes MUTUELLEMENT ELOIGNEES, la meilleure d'abord.

    Rend `(gardees, ecartees, nombre de jeux de λ distincts dans la recolte)`.

    🔑 GLOUTON MAX-MIN, la meme methode que `_apply_wl_diversity` dans
    `certus_strat_context.py`. La mieux classee est prise d'abord et toujours gardee ; chaque
    suivante est la PLUS LOIN de ce qui est deja pris. Aucun seuil, donc aucun parametre
    invente (§19 de `CLAUDE.md`). Voir `_distance` pour la mesure qui l'impose.

    📏 Ce que cela donne en pratique, sur la graine 77 de `r75x2` : 547 deposables portant 217
    jeux de λ distincts -> **10 rampes sur 7 structures de blocs differentes** (7 a 13). Les 12
    rampes assemblees a la main le meme jour tenaient toutes en 9-10 blocs, avec des
    quasi-doublons a un nanometre pres.
    """
    if not recolte:
        return [], 0, 0
    recolte = sorted(recolte, key=lambda t: _seel(t[1]))
    plans = [_plan(s.get("blocs") or []) for _g, s in recolte]
    jeux = len({frozenset(w for _s, _e, w in pl) for pl in plans})

    gardees = [recolte[0]]
    pris = [0]
    while len(gardees) < min(max(1, combien), len(recolte)):
        meilleur, meilleure_d = None, -1
        for i in range(len(recolte)):
            if i in pris:
                continue
            d = min(_distance(plans[i], plans[j]) for j in pris)
            if d > meilleure_d:
                meilleur, meilleure_d = i, d
        if meilleur is None or meilleure_d <= 0:
            break          # tout le reste est un doublon EXACT du deja pris
        pris.append(meilleur)
        gardees.append(recolte[meilleur])
    return gardees, len(recolte) - len(gardees), jeux


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    relire = "--relire-seulement" in sys.argv[1:]
    if len(args) < 2:
        print(__doc__.split("## 🔑")[0])
        print("graines : au moins une. `--relire-seulement` n'exécute aucune mesure.")
        return 2

    composant, graines = args[0], [int(a) for a in args[1:]]

    # La resolution du composant vient de SON fichier, jamais d'un defaut de ce script :
    # une fente supposee est exactement le genre d'erreur qui rend un run incomparable.
    sys.path.insert(0, str(ROOT / "scripts"))
    from probe_blocs_vs_plantage import COMPOSANTS  # noqa: PLC0415
    if composant not in COMPOSANTS:
        print(f"🔴 composant {composant!r} inconnu. Connus : {sorted(COMPOSANTS)}")
        return 2
    cfg = json.loads((ROOT / COMPOSANTS[composant][0]).read_text(encoding="utf-8"))
    resolution = float(cfg.get("monochromator_resolution_nm", 2.0))
    print(f"composant {composant} · fente {resolution} nm · mode {MODE} · graines {graines}\n")

    # ── 1. une mesure par graine, SEQUENTIELLE ────────────────────────────
    recolte: list[tuple[int, dict]] = []
    steriles: list[int] = []
    sans_plans: list[int] = []
    for g in graines:
        print(f"graine {g} :")
        a = _artefact(composant, g)
        if a is not None:
            print(f"    artefact utilisable : {a.name}")
        elif relire:
            print("    aucun artefact utilisable, et --relire-seulement : ignoree")
            sans_plans.append(g)
            continue
        else:
            if _lancer(composant, g, resolution) != 0:
                print("    🔴 la mesure a echoue -- graine ignoree")
                steriles.append(g)
                continue
            a = _artefact(composant, g)
            if a is None:
                print("    🔴 la mesure n'a pas produit d'artefact avec plans -- graine ignoree")
                steriles.append(g)
                continue
        dep = _recolter(a)
        if dep:
            recolte += [(g, s) for s in dep]
        else:
            steriles.append(g)

    # ── 2. refuser de conclure sur du vide ────────────────────────────────
    if not recolte:
        print("\n" + "=" * 78)
        print("🔴 AUCUNE GRAINE N'A TROUVE DE STRATEGIE DEPOSABLE. Rien n'est ecrit.")
        print("=" * 78)
        print(f"  graines steriles : {steriles}")
        if sans_plans:
            print(f"  🟠 graines a REMESURER (artefact sans plans) : {sans_plans}")
            print("     Ne les compte PAS comme steriles : on ne sait pas ce qu'elles valent.")
        print("  Ce n'est PAS un echec du script : c'est un resultat, et il est important.")
        print("  Il dit que sur ce composant la recherche echoue a toutes les graines essayees")
        print("  -- donc que le probleme n'est pas la realisation du bruit. Essaie d'autres")
        print("  graines avant d'en conclure quoi que ce soit : le 2026-08-21, sur r75x2 a")
        print("  2 nm, la graine 77 trouvait 547 deposables la ou la 42 en trouvait ZERO.")
        return 1

    # ── 3. dedupliquer par JEU DE λ, pas par identifiant ──────────────────
    # 🔑 Deux rampes qui portent le meme jeu de λ sont UNE direction, pas deux. 📏 Les 12
    # rampes fabriquees a la main le 2026-08-21 comptaient des quasi-doublons -- elles ne
    # differaient que d'un nanometre sur une λ. `elite_parent_top_k` achete alors des COPIES
    # au lieu de DIRECTIONS, et c'est le defaut mesure du vivier de parents.
    gardees, doublons, jeux = choisir_rampes(recolte, RAMPES_PAR_DEFAUT)
    msg = f"  📏 {len(recolte)} deposables portent {jeux} jeu(x) de λ distinct(s)"
    if jeux <= 1:
        msg += "  🔴 UNE SEULE LIGNEE -- ELITE aura peu de directions."
    print(msg)

    # ── 4. ecrire, avec la PROVENANCE de chaque rampe ─────────────────────
    plans = [
        {
            "nom": f"s{g:03d}_SEEL{_seel(s):.4f}_crash{(s.get('crash_rate') or 0)*100:.2f}",
            "graine_origine": g,
            "seel_nm": round(_seel(s), 4),
            "crash_rate": s.get("crash_rate"),
            "n_blocs": s.get("n_blocs"),
            "origine_dans_le_run": s.get("origine"),
            "blocs": s.get("blocs"),
        }
        for g, s in gardees
    ]
    sortie = ROOT / "reports" / "plans" / f"rampes_{composant}_{'-'.join(map(str, graines))}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    if sortie.exists():
        # 🔴 On n'ecrase JAMAIS -- interdit 3 : `reports/` n'est presque pas protege.
        from datetime import datetime  # noqa: PLC0415
        garde = sortie.with_name(f"{sortie.stem}_{datetime.now():%Y%m%d_%H%M%S}{sortie.suffix}")
        print(f"\n🟠 {sortie.name} existe deja -- le precedent est CONSERVE, le nouveau va dans {garde.name}")
        sortie = garde
    sortie.write_text(json.dumps(plans, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── 5. dire ce qu'on a fait, et ce que cela vaut ──────────────────────
    print("\n" + "=" * 78)
    print(f"🟢 {len(plans)} RAMPES ECRITES dans {sortie.relative_to(ROOT)}")
    print("=" * 78)
    print(f"  recoltees : {len(recolte)} deposables sur {len(graines)} graines")
    print(f"  ecartees comme trop proches des retenues : {doublons}")
    if steriles:
        print(f"  🔴 graines STERILES (zero deposable) : {steriles}")
        print("     C'est une information, pas un incident : elle dit ou la recherche echoue.")
    if sans_plans:
        print(f"  🟠 graines A REMESURER (artefact sans plans) : {sans_plans}")
        print("     Leurs artefacts precedent l'instrument du 2026-08-20. Elles ne sont NI")
        print("     steriles NI fecondes -- on ne sait pas, et c'est un troisieme etat.")
    print(f"\n  {'rang':>4} {'graine':>7} {'blocs':>6} {'SEEL':>8} {'crash':>7}  origine dans le run")
    for i, (g, s) in enumerate(gardees, 1):
        print(f"  {i:>4} {g:>7} {s.get('n_blocs'):>6} {_seel(s):>8.4f} "
              f"{(s.get('crash_rate') or 0):>7.2%}  {str(s.get('origine'))[:34]}")

    print("\n" + "-" * 78)
    print("POUR S'EN SERVIR -- dans la configuration du composant, a la racine :")
    print(f'    "injected_strategies": "{sortie.relative_to(ROOT).as_posix()}"')
    print("\n🔴 ET IL FAUT LE DIRE AVEC LE CHIFFRE, PAS APRES :")
    print("  Un resultat obtenu avec ces rampes n'est PAS une decouverte autonome.")
    print(f"  L'information vient des graines {sorted({g for g, _ in gardees})}.")
    print("  ⚠️ Et si tu remesures a une graine qui a SERVI A CHOISIR ces rampes, le chiffre")
    print("     est biaise vers le bas -- malediction du vainqueur, +12,9 % mesures le 15/08.")
    print("     Verifie a une graine ABSENTE de la liste ci-dessus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
