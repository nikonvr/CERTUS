"""ORCHESTRATEUR MULTI-REALISATION -- chercher sur K graines dans un BUDGET DE TEMPS.

    python scripts/orchestre_multigraine.py r75x2 --budget 2h
    python scripts/orchestre_multigraine.py r75x2 --budget nuit --objectif meilleur

## POURQUOI CE FICHIER EXISTE

Sur `r75x2` a 2 nm, une graine trouve ou ne trouve pas, et c'est proche d'une loterie. Mesure
du 2026-08-22, sept graines NUES, plage complete, aucune surcharge :

    42 -> 0/1617     77 -> 547/2231 ✅     101 -> 0/1630     202 -> 0/1646
   303 -> 0/1680    404 -> 372/2016 ✅     505 -> 311/1995 ✅

🔑 Le mecanisme est mesure et n'a rien de vague (§3 de REPRENDRE_ICI) : hors ELITE il n'y a
rien ; la generation d'ELITE est DETERMINISTE ; le seul point de divergence des graines est le
criblage Monte-Carlo, dont les survivants deviennent les PARENTS d'ELITE. Et le paysage est une
FALAISE -- 100 % de plantage ou deposable, rien entre les deux. La graine decide donc quels
parents ELITE recoit, et si un descendant atterrit de l'autre cote.

**La reponse produit est donc de rejouer la meme recherche sur K realisations.** Ce fichier
est l'orchestration de cela, par-dessus des briques qui existent toutes deja.

## 🔴 POURQUOI UN BUDGET DE TEMPS, ET PAS UN `K` A COCHER

`K` utile depend de `p`, et **`p` est inconnu sur un composant neuf.** Nos 3/7 valent pour
`r75x2` a 2 nm -- un empilement, une fente. §8.2bis interdit d'en tirer une generalite. Une
case « multi-graines, K=4 » promettrait donc une couverture que le logiciel ne peut pas tenir.

Un budget, lui, est robuste a l'ignorance de `p` : on cherche tant qu'il reste du temps, et on
rapporte ce qu'on a trouve ET ce qu'on n'a pas eu le temps d'essayer.

## LES QUATRE REGLES DU DEPOT QUE CE FICHIER APPLIQUE

1. 🔒 **LA NOTATION FINALE EST SUR UNE GRAINE DISJOINTE** des graines de generation. Noter sur
   une graine qui a servi a trouver, c'est la MALEDICTION DU VAINQUEUR -- mesuree a **+12,9 %**
   le 2026-08-15. Le cout de la garde est mesure lui aussi : **+0,55 %**. Le programme REFUSE
   de tourner si les deux ensembles se croisent.
2. 🔒 **L'UNION NE TRANSPORTE QUE DES PLANS, JAMAIS DES SCORES.** Les scores viennent de
   realisations differentes et ne sont PAS comparables entre eux -- c'est ecrit dans la
   docstring de `_screen_with_seeds`. D'ou le prelevement en TOURNIQUET (le meilleur de chaque
   graine, puis le deuxieme de chaque, ...) : a l'interieur d'une graine le tri est licite,
   entre graines il ne l'est pas.
3. 🔴 **ON N'ATTEND JAMAIS UN ARTEFACT COMME SIGNAL DE FIN.** La sonde l'ecrit AVANT sa
   synthese ; une chaine qui le guettait a lance la mesure suivante 10 s trop tot le
   2026-08-21 (« RuntimeError: QThread has been deleted »). On attend la SORTIE DU PROCESSUS.
4. 🔴 **LE BUDGET GOUVERNE LES LANCEMENTS, PAS LES ARRETS.** Un run coupe est une mesure
   DETRUITE -- quatre de 91 min ont ete perdues ainsi le 2026-08-22, coupees a 98,9 %. On ne
   lance donc jamais un run qui ne rentre pas, mais on laisse finir ceux qui volent, et le
   depassement est RAPPORTE au lieu d'etre masque.

## CE QU'IL NE FAIT PAS

Il ne crible pas les graines a budget Monte-Carlo reduit. Mesure le 2026-08-22 : couper les
tirages d'un facteur 4 ne rend le run que **1,63x** plus rapide -- le minage DP et la
generation ELITE n'en dependent pas. Cribler 7 graines puis rejouer les gagnantes coute
**321 min** contre **308** pour tout jouer plein. Le criblage est fiable et non rentable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux lignes,
# UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# `tests/unit/test_scripts_console_cp1252.py` refuse tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

RACINE = Path(__file__).resolve().parents[1]

#: L'echelle de graines de GENERATION, deterministe et documentee. Aucun tirage aleatoire :
#: deux lancements du meme budget doivent essayer les memes realisations, sinon on ne peut ni
#: reprendre une campagne ni reproduire un resultat.
ECHELLE_GRAINES = (101, 202, 303, 404, 505, 606, 707, 808, 909, 1111, 1212, 1313)

#: La graine de NOTATION par defaut. 42 est la graine historique de notation du depot et
#: n'appartient pas a l'echelle ci-dessus -- la disjonction est donc vraie par construction,
#: et verifiee quand meme plus bas.
GRAINE_NOTATION_DEFAUT = 42

#: Tolerance de plantage de 👤. ⚠️ `crash_rate` EST DEJA le maximum sur les trois niveaux de
#: bruit (§3 point 7), dont un a 2x le bruit mesure : la lecture est donc conservatrice.
TOLERANCE_PLANTAGE = 0.05

#: Duree attendue d'un run tant qu'aucun n'a fini ICI. 🔴 Elle ne sert QU'A decider si un
#: lancement rentre dans le budget, jamais a annoncer un ETA : les durees ne valent que sur
#: leur machine (§0.2 piege 5). Des qu'un run finit, sa duree REELLE remplace celle-ci.
DUREE_ATTENDUE_DEFAUT_MIN = 60.0


def _duree_en_minutes(texte: str) -> float:
    """« 2h », « 90m », « 1h30 », « nuit » -> minutes.

    ⚠️ « nuit » vaut 10 h. C'est une convention, pas une mesure : elle ne dit rien de l'heure
    qu'il est, seulement de la duree qu'on accorde.
    """
    t = texte.strip().lower()
    if t == "nuit":
        return 600.0
    # ⚠️ Le `m` final est OPTIONNEL, et c'est un test qui l'a impose : le motif d'abord ecrit
    # exigeait `1h30m`, alors que le message d'erreur juste dessous annonce `1h30` comme
    # valide. Un outil qui contredit sa propre documentation est un piege, pas un outil.
    # Consequence voulue : un nombre NU se lit en minutes (« 45 » = 45 min).
    m = re.fullmatch(r"(?:(\d+(?:[.,]\d+)?)\s*h)?\s*(?:(\d+(?:[.,]\d+)?)\s*(?:m(?:in)?)?)?", t)
    if m and (m.group(1) or m.group(2)):
        h = float((m.group(1) or "0").replace(",", "."))
        mi = float((m.group(2) or "0").replace(",", "."))
        return h * 60.0 + mi
    raise argparse.ArgumentTypeError(
        f"budget {texte!r} illisible. Attendu : 2h · 90m · 1h30 · nuit · un nombre de minutes."
    )


#: Un suffixe de la forme `20260822_102742`. La sonde en ajoute un quand un homonyme existe
#: deja, pour ne pas ecraser une mesure.
_HORODATAGE = re.compile(r"\d{8}_\d{6}")


def _nom_artefact(composant: str, mode: str, graine: int, tag: str = "") -> str:
    suffixe = f"_{tag}" if tag else ""
    return f"blocs_vs_plantage_{composant}_{mode}_s{graine:03d}{suffixe}.json"


def _resoudre_artefact(composant: str, mode: str, graine: int, tag: str = "") -> Path | None:
    """Le chemin de l'artefact le plus RECENT qui corresponde EXACTEMENT a cette configuration.

    🔴 CE N'EST PAS UNE COMMODITE, C'EST LE DEFAUT N° 2 DE `generer_rampes.py`, REPRODUIT ICI
    PUIS CORRIGE. Resoudre par le nom canonique rate les homonymes : la sonde ajoute un
    horodatage quand un fichier du meme nom existe deja, pour ne pas ecraser une mesure. Sur ce
    depot, la mesure a plein budget de la graine 101 vit dans
    `..._s101_20260822_102742.json` -- un lecteur par nom canonique la declarerait ABSENTE et
    referait 45 minutes pour rien.

    🔴 ET LA FAUTE SYMETRIQUE EST PIRE : un `glob("...s101*.json")` naif ramasserait aussi
    `..._s101_mcreduit4x.json`, un run a BUDGET REDUIT, et le prendrait pour la mesure de
    reference. On n'accepte donc comme suffixe QUE le vide ou un horodatage -- jamais une
    etiquette de surcharge, qui designe une autre configuration.

    ⚠️ Le meme filtre protege d'une confusion de graines : `s101*` attrape `s1011`, dont le
    reste `1` n'est pas un horodatage et se trouve donc rejete.
    """
    attendu = _nom_artefact(composant, mode, graine, tag)[:-len(".json")]
    candidats = []
    for f in (RACINE / "reports").glob(f"{attendu}*.json"):
        reste = f.stem[len(attendu):].lstrip("_")
        if reste and not _HORODATAGE.fullmatch(reste):
            continue
        candidats.append(f)
    return max(candidats, key=lambda p: p.stat().st_mtime, default=None)


def _lire_artefact(chemin: Path | None) -> dict | None:
    """Rend le contenu si l'artefact est une MESURE, None sinon.

    🔴 `verdict != OK` ou une liste de strategies VIDE ne compte pas comme fait : les quatre
    mesures perdues du 2026-08-22 portaient toutes un artefact, et il ne portait rien.
    """
    if chemin is None or not chemin.is_file():
        return None
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if d.get("verdict") != "OK" or not (d.get("strategies") or []):
        return None
    return d


def _deposables(artefact: dict) -> list[dict]:
    """Les strategies sous la tolerance, triees par score CROISSANT.

    Le tri est licite ici : toutes ces strategies viennent de LA MEME realisation.
    """
    dep = [s for s in artefact["strategies"] if s.get("crash_rate", 1.0) <= TOLERANCE_PLANTAGE]
    return sorted(dep, key=lambda s: s.get("score", float("inf")))


def _seel(score: float) -> float:
    """SEEL = 2·√(score). Controle : 0,08053 rend 0,5676, la valeur publiee en §0ter."""
    return 2.0 * (float(score) ** 0.5)


#: Prefixe du flux d'EVENEMENTS, lisible par machine. Arme par `--evenements`.
#:
#: 🔑 POURQUOI UN FLUX, ET PAS DU REGEX SUR LES PHRASES. Le GUI pilote ce script au lieu de
#: reimplementer l'orchestration -- sinon deux chemins de code coexisteraient et divergeraient,
#: ce que ce depot a deja paye. Mais faire lire de la PROSE a une interface la rend solidaire
#: de la formulation : changer un mot d'affichage casserait le GUI en silence. Les phrases
#: restent donc pour l'humain, et cette ligne-ci pour la machine.
PREFIXE_EVT = "[ORCH] "

_evenements_armes = False


def _evt(type_: str, **champs) -> None:
    if _evenements_armes:
        print(PREFIXE_EVT + json.dumps({"evt": type_, **champs}, ensure_ascii=False), flush=True)


def lire_evenement(ligne: str) -> dict | None:
    """L'inverse de `_evt` -- rend le dictionnaire, ou None si la ligne n'est pas un evenement.

    Vit ici, a cote de l'emetteur, deliberement : un format dont l'ecriture et la lecture sont
    dans deux fichiers derive. Le GUI importe cette fonction.
    """
    if not ligne.startswith(PREFIXE_EVT):
        return None
    try:
        d = json.loads(ligne[len(PREFIXE_EVT):])
    except ValueError:
        return None
    return d if isinstance(d, dict) and "evt" in d else None


def mode_finalisation_demandee(drapeau: Path) -> str:
    """Le fichier d'arret porte SON MODE dans son contenu. Rend "", "attendre" ou "abandonner".

    🔑 POURQUOI DANS LE CONTENU, ET PAS DANS UN DRAPEAU DE LANCEMENT. 👤 : « si on clique sur
    arreter, on n'est pas oblige de terminer de suite, on peut passer a l'etape 3 ». La
    question ne se pose donc PAS au lancement mais au moment du clic -- a ce moment-la seul on
    sait si le run en vol vaut la peine d'etre attendu. Un seul fichier, un seul mecanisme :
    ce qu'on ecrit dedans decide.

        vide / n'importe quoi  ->  attendre    : les runs en vol finissent, RIEN n'est perdu
        « abandonner »         ->  abandonner  : on les tue et on passe a l'etape 3 tout de
                                                 suite. Leur travail est perdu, et c'est DIT.

    🔴 Dans les DEUX cas on passe a l'union puis a la notation finale. Arreter n'a jamais voulu
    dire tout jeter : ce qui est deja mesure porte un artefact et sera note.
    """
    if not drapeau.exists():
        return ""
    try:
        contenu = drapeau.read_text(encoding="utf-8", errors="replace").strip().lower()
    except OSError:
        contenu = ""
    return "abandonner" if contenu.startswith("abandonner") else "attendre"


def motif_finalisation(
    *,
    drapeau: Path,
    seel_cible: float | None,
    meilleur_seel: float | None,
    succes: bool,
    objectif: str,
) -> str:
    """Faut-il FINALISER -- cesser de lancer et produire le chiffre ? Rend le motif, ou "".

    Fonction PURE et au niveau du module, deliberement : c'est la decision qui interrompt une
    campagne de plusieurs heures, elle doit etre testable sans lancer un seul run.

    L'ordre des trois causes est un ordre de PRIORITE d'affichage, pas de logique -- elles ne
    s'excluent pas. La demande explicite de 👤 passe devant, parce que c'est la seule qui vient
    de l'exterieur et qu'il doit la voir reconnue.
    """
    if drapeau.exists():
        return "demande de l'utilisateur (fichier FINALISER)"
    if seel_cible is not None and meilleur_seel is not None and meilleur_seel <= seel_cible:
        return f"cible atteinte : SEEL {meilleur_seel:.4f} <= {seel_cible:.4f} nm"
    if succes and objectif == "premier":
        return "objectif « premier » : une realisation a trouve"
    return ""


def _signature(strategie: dict) -> tuple:
    """Signature de PLAN : (nombre de blocs, frontieres et lambdas).

    🔴 Jamais par `id` : mesure §24-51, 21 identifiants sur 79 portent deux ou trois plans
    DIFFERENTS. Dedupliquer par id fusionnerait des plans distincts et en perdrait en silence
    -- exactement l'echec que cette union existe pour eviter.
    """
    blocs = strategie.get("blocs") or strategie.get("blocks") or []
    return (
        int(strategie.get("n_blocs", len(blocs))),
        tuple(
            (int(b["start"]), int(b["end"]), round(float(b.get("wavelength", b.get("wl", 0.0))), 4))
            for b in blocs
            if isinstance(b, dict) and "start" in b and "end" in b
        ),
    )


def unir_en_tourniquet(par_graine: dict[int, list[dict]], plafond: int) -> tuple[list[dict], int]:
    """Union des plans, en TOURNIQUET, dedupliquee par signature.

    🔒 LE TOURNIQUET N'EST PAS UN DETAIL. Prendre « les N meilleurs de l'union » exigerait de
    comparer des scores venus de realisations DIFFERENTES -- ce que la regle d'or du multiseed
    interdit. On prend donc le meilleur de chaque graine, puis le deuxieme de chaque, etc. :
    chaque comparaison reste interne a une graine, et aucune graine n'est affamee.

    Rend (plans, nombre de plans ECARTES par le plafond). 🔴 L'appelant DOIT dire ce qui a ete
    ecarte : une troncature silencieuse se lit comme « on a tout couvert ».
    """
    graines = sorted(par_graine)
    plans: list[dict] = []
    vues: set[tuple] = set()
    ecartes = 0
    rang = 0
    while True:
        encore = False
        for g in graines:
            lst = par_graine[g]
            if rang >= len(lst):
                continue
            encore = True
            s = lst[rang]
            sig = _signature(s)
            if not sig[1] or sig in vues:
                continue
            vues.add(sig)
            if len(plans) >= plafond:
                ecartes += 1
                continue
            plans.append(
                {
                    "nom": f"s{g:03d}_{s.get('origine', '?')}_{s.get('n_blocs', '?')}b_rang{rang}",
                    "blocs": [
                        {
                            "start": int(b["start"]),
                            "end": int(b["end"]),
                            "wavelength": float(b.get("wavelength", b.get("wl", 0.0))),
                        }
                        for b in (s.get("blocs") or s.get("blocks") or [])
                    ],
                }
            )
        if not encore:
            break
        rang += 1
    return plans, ecartes


def _lancer(py: str, composant: str, mode: str, res_nm: float, graine: int,
            journal: Path, env_sup: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    # 🔴 LE PLAFOND SE CALCULE, IL NE SE COPIE PAS. `bench_examples.py:171` fait rendre None a
    # `wait_for` au-dela -- ce qui RESSEMBLE a un resultat. Regle du depot : max(5400, 4x duree
    # attendue). Un plafond trop grand ne coute rien ; un plafond trop petit detruit la mesure
    # a la derniere minute.
    env.setdefault("CERTUS_BENCH_TIMEOUT_S", "38400")
    if env_sup:
        env.update(env_sup)
    journal.parent.mkdir(parents=True, exist_ok=True)
    fh = journal.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [py, "scripts/probe_blocs_vs_plantage.py", composant, mode, "0", "0",
         f"{res_nm:g}", "0", str(graine)],
        cwd=RACINE, stdout=fh, stderr=subprocess.STDOUT, env=env,
    )
    proc._certus_journal = fh  # type: ignore[attr-defined]
    return proc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Cherche sur K realisations dans un budget de temps, unit, renote sur une graine disjointe.",
    )
    ap.add_argument("composant", help="nom du composant, ex. r75x2")
    ap.add_argument("--budget", type=_duree_en_minutes, default="2h",
                    help="duree maximale : 2h · 90m · 1h30 · nuit (10 h). Defaut 2h")
    ap.add_argument("--objectif", choices=("premier", "meilleur"), default="premier",
                    help="premier : on s'arrete des qu'une graine trouve. "
                         "meilleur : on epuise le budget et on unit tout. Defaut premier")
    ap.add_argument("--seel-cible", type=float, default=None, metavar="NM",
                    help="on arrete des qu'une realisation rend un SEEL <= cette valeur, en nm. "
                         "⚠️ Le SEEL annonce en cours de campagne est PROVISOIRE : il est mesure "
                         "sur la graine qui l'a trouve. Le chiffre citable vient de la notation "
                         "finale sur une graine disjointe.")
    ap.add_argument("--runs-en-vol", choices=("attendre", "abandonner"), default="attendre",
                    help="que faire des runs EN VOL quand on decide d'arreter. "
                         "attendre : on les laisse finir, rien n'est gaspille (defaut). "
                         "abandonner : on les tue, on s'arrete tout de suite, leur travail est perdu.")
    ap.add_argument("--slots", type=int, default=0,
                    help="processus concurrents. 0 = auto (cpu_count//8, au moins 1)")
    ap.add_argument("--mode", default="deep", choices=("fast", "premium", "deep"))
    ap.add_argument("--resolution", type=float, default=2.0, help="fente, en nm. Defaut 2.0")
    ap.add_argument("--graines", type=int, nargs="+", default=None,
                    help=f"graines de generation. Defaut : l'echelle {ECHELLE_GRAINES[:5]}...")
    ap.add_argument("--graine-notation", type=int, default=GRAINE_NOTATION_DEFAUT,
                    help=f"graine de NOTATION finale, DISJOINTE. Defaut {GRAINE_NOTATION_DEFAUT}")
    ap.add_argument("--max-plans", type=int, default=200,
                    help="plafond de plans injectes a la notation finale. Defaut 200")
    ap.add_argument("--duree-attendue", type=float, default=DUREE_ATTENDUE_DEFAUT_MIN,
                    help="minutes, pour decider si un lancement rentre. Remplacee par la duree "
                         f"REELLE des le premier run fini. Defaut {DUREE_ATTENDUE_DEFAUT_MIN:g}")
    ap.add_argument("--python", default=os.environ.get("CERTUS_PY", "C:/envs/certus/Scripts/python.exe"))
    ap.add_argument("--evenements", action="store_true",
                    help="emet en plus un flux JSONL prefixe « [ORCH] », pour un pilote "
                         "(le GUI STRAT). Les phrases humaines restent inchangees.")
    ap.add_argument("--dry-run", action="store_true", help="dit ce qui serait fait, ne lance rien")
    a = ap.parse_args(argv)
    global _evenements_armes
    _evenements_armes = bool(a.evenements)

    graines = list(a.graines) if a.graines else list(ECHELLE_GRAINES)
    slots = a.slots if a.slots > 0 else max(1, (os.cpu_count() or 8) // 8)

    # 🔒 LA GARDE ANTI-MALEDICTION, ET ELLE REFUSE DE TOURNER. Ce n'est pas un avertissement :
    # un score publie apres notation sur une graine qui a servi a trouver est FAUX de +12,9 %,
    # et rien dans le resultat ne le dirait.
    if a.graine_notation in graines:
        print(f"🔴 la graine de notation {a.graine_notation} est AUSSI une graine de generation.")
        print("   Noter sur une graine qui a servi a trouver, c'est la malediction du vainqueur")
        print("   -- mesuree a +12,9 % le 2026-08-15. Choisis une graine disjointe.")
        return 2

    stamp = time.strftime("%Y%m%d_%H%M%S")
    jdir = RACINE / "reports" / f"orchestre_{a.composant}_{stamp}"

    print("=" * 78)
    print("ORCHESTRATEUR MULTI-REALISATION -- CERTUS")
    print("=" * 78)
    print(f"  composant        : {a.composant} · mode {a.mode} · fente {a.resolution:g} nm")
    print(f"  budget           : {a.budget:.0f} min · objectif « {a.objectif} »")
    print(f"  slots            : {slots} concurrents")
    print(f"  graines          : {graines}")
    print(f"  graine notation  : {a.graine_notation}  (disjointe ✔)")
    print(f"  journaux         : {jdir.relative_to(RACINE)}")
    print()
    _evt("demarrage", composant=a.composant, mode=a.mode, resolution=a.resolution,
         budget_min=a.budget, objectif=a.objectif, seel_cible=a.seel_cible, slots=slots,
         graines=graines, graine_notation=a.graine_notation)

    # 🔴 LE POINT DE FINALISATION DOIT EXISTER DES LA PREMIERE SECONDE. Cette annonce vivait plus bas,
    # apres le balayage de reprise : un pilote qui proposait « Arreter » pendant ce laps ne
    # trouvait aucun chemin ou ecrire, et le clic ne faisait RIEN, en silence. Un bouton actif
    # qui n'agit pas est pire qu'un bouton grise. Trouve par le test d'integration du GUI.
    drapeau_finaliser = jdir / "FINALISER"
    jdir.mkdir(parents=True, exist_ok=True)
    print(f"  ⏹  pour FINALISER a tout moment :  touch {drapeau_finaliser.relative_to(RACINE)}")
    _evt("drapeau", chemin=str(drapeau_finaliser))

    # --- Reprise : ce qui porte deja une mesure ne se refait pas -------------------------
    # 🔴 `meilleur_seel` EST HISSE ICI, ET C'EST UNE REPARATION. Il vivait plus bas, dans la
    # boucle : une campagne dont TOUTES les graines etaient deja mesurees le laissait vide,
    # donc l'ecart provisoire -> definitif -- le canal de malediction du vainqueur qu'on publie
    # a chaque campagne -- etait SILENCIEUSEMENT saute. Or le cas de reprise est le plus
    # frequent : c'est celui de la validation du 2026-08-22.
    meilleur_seel: float | None = None
    fait: dict[int, dict] = {}
    for g in graines:
        art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, g))
        if art is not None:
            fait[g] = art
            dep = _deposables(art)
            print(f"  ⏭  graine {g} DEJA MESUREE -- {len(dep)} deposable(s)")
            if dep:
                seel_deja = _seel(dep[0]["score"])
                if meilleur_seel is None or seel_deja < meilleur_seel:
                    meilleur_seel = seel_deja
            _evt("deja", graine=g, deposables=len(dep),
                 seel=_seel(dep[0]["score"]) if dep else None)
    a_faire = [g for g in graines if g not in fait]
    if fait:
        print()

    if a.dry_run:
        print(f"  [dry-run] a lancer : {a_faire}")
        print(f"  [dry-run] duree attendue {a.duree_attendue:g} min -> "
              f"{int(a.budget // max(a.duree_attendue, 1e-9)) * slots} run(s) tiennent dans le budget")
        return 0

    # --- La boucle -----------------------------------------------------------------------
    t0 = time.monotonic()
    duree_reelle: float | None = None
    en_vol: dict[int, tuple[subprocess.Popen, float]] = {}
    jamais_lancees: list[int] = []
    succes = False
    raison_finalisation = ""

    # 🔑 L'ARRET A LA MAIN, ET IL DOIT MARCHER DEPUIS UNE AUTRE FENETRE. 👤 veut pouvoir
    # arreter « a tout moment si on lui annonce un SEEL qui lui convient ». Un Ctrl-C ne
    # suffit pas : la campagne peut tourner la nuit, detachee du terminal. Ce fichier-ci est
    # donc le vrai bouton -- il peut etre cree par l'utilisateur, par un script, ou plus tard
    # par un bouton d'interface, sans rien connaitre du processus.
    if a.seel_cible is not None:
        print(f"  🎯 finalisation automatique des qu'un SEEL <= {a.seel_cible:.4f} nm est atteint")
    print()

    def _minutes() -> float:
        return (time.monotonic() - t0) / 60.0

    def _rentre() -> bool:
        """🔴 Le budget gouverne les LANCEMENTS. On ne lance jamais ce qui ne rentre pas."""
        attendue = duree_reelle if duree_reelle is not None else a.duree_attendue
        return _minutes() + attendue <= a.budget

    def _doit_finaliser() -> str:
        return motif_finalisation(
            drapeau=drapeau_finaliser, seel_cible=a.seel_cible, meilleur_seel=meilleur_seel,
            succes=succes, objectif=a.objectif,
        )

    file_attente = list(a_faire)
    try:
        while file_attente or en_vol:
            raison_finalisation = raison_finalisation or _doit_finaliser()
            while file_attente and len(en_vol) < slots and not raison_finalisation:
                if not _rentre():
                    jamais_lancees.extend(file_attente)
                    print(f"  ⏹  budget : {len(file_attente)} graine(s) NON LANCEE(S) -- "
                          f"{_minutes():.0f} min ecoulees, un run en demande "
                          f"~{duree_reelle if duree_reelle is not None else a.duree_attendue:.0f}")
                    file_attente = []
                    break
                g = file_attente.pop(0)
                p = _lancer(a.python, a.composant, a.mode, a.resolution, g,
                            jdir / f"journal_s{g:03d}.log")
                en_vol[g] = (p, time.monotonic())
                print(f"  ▶  graine {g} lancee a {time.strftime('%H:%M:%S')} (pid {p.pid})")
                _evt("lancee", graine=g, pid=p.pid, ecoulees_min=round(_minutes(), 2))

            if raison_finalisation and file_attente:
                jamais_lancees.extend(file_attente)
                file_attente = []

            # 🔴 FINALISER N'EST PAS TUER, PAR DEFAUT. Un run coupe est une mesure DETRUITE :
            # quatre de 91 min ont ete perdues ainsi le 2026-08-22, a 98,9 % d'avancement. On
            # laisse donc finir ce qui vole -- sauf si 👤 a explicitement demande l'inverse,
            # auquel cas le travail perdu est DIT.
            # 🔑 LE MODE EST RELU A CHAQUE TOUR, parce que 👤 le decide au moment du CLIC et
            # non au lancement : le fichier FINALISER porte « abandonner » ou rien. Le drapeau
            # de ligne de commande reste la valeur par defaut pour un lancement sans pilote.
            mode = mode_finalisation_demandee(drapeau_finaliser) or a.runs_en_vol
            if raison_finalisation and en_vol and mode == "abandonner":
                print(f"  🛑 {raison_finalisation} -- abandon de {sorted(en_vol)} EN VOL, "
                      f"leur travail est PERDU. On passe a l'union et a la notation finale "
                      f"sur ce qui est deja mesure.")
                _evt("abandon", graines=sorted(en_vol))
                for g, (p, _tg) in list(en_vol.items()):
                    p.terminate()

            if not en_vol:
                break

            # 🔴 ON ATTEND LA SORTIE DU PROCESSUS, jamais l'apparition d'un artefact : la sonde
            # l'ecrit AVANT sa synthese.
            time.sleep(5)
            for g, (p, tg) in list(en_vol.items()):
                if p.poll() is None:
                    continue
                del en_vol[g]
                try:
                    p._certus_journal.close()  # type: ignore[attr-defined]
                except Exception:  # noqa: BLE001 -- fermer un journal ne doit rien casser
                    pass
                mins = (time.monotonic() - tg) / 60.0
                if duree_reelle is None and p.returncode == 0:
                    duree_reelle = mins
                    print(f"     📏 duree REELLE mesuree ici : {mins:.0f} min "
                          f"(elle remplace l'estimation de {a.duree_attendue:.0f})")
                art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, g))
                if p.returncode != 0 or art is None:
                    # 🔴 Un echec se DIT et n'arrete pas la campagne : les autres graines
                    # gardent leur valeur.
                    print(f"  🔴 graine {g} EXIT={p.returncode} en {mins:.0f} min, sans mesure "
                          f"exploitable -- cherche « WAIT_TIMEOUT= » dans son journal")
                    continue
                fait[g] = art
                dep = _deposables(art)
                if not dep:
                    print(f"  ❌ graine {g} : aucun deposable en {mins:.0f} min")
                    _evt("finie", graine=g, deposables=0, seel=None, minutes=round(mins, 1))
                    continue
                succes = True
                seel = _seel(dep[0]["score"])
                if meilleur_seel is None or seel < meilleur_seel:
                    meilleur_seel = seel
                # 🔑 L'ANNONCE VIVANTE, ET SA RESERVE DANS LA MEME LIGNE. C'est sur ce chiffre
                # que 👤 decide d'arreter, il doit donc porter ce qu'il vaut : il est mesure
                # sur la graine QUI L'A TROUVE. Le chiffre citable vient de la notation finale
                # sur une graine disjointe -- ecart mesure +0,55 %, canal mesure a +12,9 %.
                print(f"  ✅ graine {g} : {len(dep)} deposable(s) · SEEL {seel:.4f} nm "
                      f"({dep[0]['n_blocs']} blocs, plantage {100 * dep[0]['crash_rate']:.2f} %) "
                      f"en {mins:.0f} min   [PROVISOIRE -- note sur sa propre graine]")
                _evt("finie", graine=g, deposables=len(dep), seel=seel,
                     n_blocs=dep[0]["n_blocs"], crash=dep[0]["crash_rate"],
                     minutes=round(mins, 1), provisoire=True)

            raison_finalisation = raison_finalisation or _doit_finaliser()
    except KeyboardInterrupt:
        # 🔑 Ctrl-C N'EST PAS UNE PERTE. Ce qui est deja mesure porte un artefact sur disque ;
        # on enchaine donc sur la synthese et la notation finale au lieu de tout jeter.
        raison_finalisation = raison_finalisation or "Ctrl-C"
        jamais_lancees.extend(file_attente)
        print(f"\n  🛑 Ctrl-C -- {len(en_vol)} run(s) en vol abandonne(s), "
              f"{len(fait)} mesure(s) conservee(s)")
        for g, (p, _tg) in list(en_vol.items()):
            p.terminate()
        en_vol.clear()

    if raison_finalisation:
        print(f"\n  🛑 arret : {raison_finalisation}")

    # --- Synthese ------------------------------------------------------------------------
    print()
    print("=" * 78)
    par_graine = {g: _deposables(art) for g, art in sorted(fait.items())}
    qui_trouvent = {g: d for g, d in par_graine.items() if d}
    print(f"  {len(qui_trouvent)} graine(s) sur {len(par_graine)} mesuree(s) ont trouve · "
          f"{_minutes():.0f} min ecoulees sur un budget de {a.budget:.0f}")
    if jamais_lancees:
        # 🔴 Ce qui n'a pas ete essaye se DIT. Sans cette ligne, « 0 trouve » se lirait comme
        # « ca ne marche pas » alors que ce serait « on n'a pas eu le temps ».
        print(f"  ⚠️  NON ESSAYEES faute de budget : {sorted(set(jamais_lancees))}")
    if not qui_trouvent:
        print("  Aucune realisation n'a trouve. Ce n'est PAS « c'est impossible » : "
              "c'est « pas dans ce budget, sur ces graines ».")
        _evt("fin", trouve=False, non_essayees=sorted(set(jamais_lancees)))
        return 1

    plans, ecartes = unir_en_tourniquet(qui_trouvent, a.max_plans)
    if ecartes:
        print(f"  ⚠️  plafond --max-plans={a.max_plans} : {ecartes} plan(s) unique(s) ECARTE(S)")
    chemin = RACINE / "reports" / "plans" / f"plans_union_{a.composant}_{stamp}.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(plans, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  union en tourniquet : {len(plans)} plan(s) -> {chemin.relative_to(RACINE)}")
    _evt("union", plans=len(plans), ecartes=ecartes, graines=sorted(qui_trouvent))

    print()
    print(f"  ▶  NOTATION FINALE sur la graine {a.graine_notation}, DISJOINTE des graines de "
          f"generation")
    print("     (garde anti-malediction du vainqueur -- cout mesure +0,55 %)")
    _evt("notation", graine=a.graine_notation)
    tag = f"union{stamp}"
    p = _lancer(
        a.python, a.composant, a.mode, a.resolution, a.graine_notation,
        jdir / f"journal_notation_s{a.graine_notation:03d}.log",
        env_sup={
            "CERTUS_PROBE_OVERRIDES": f"injected_strategies={chemin.relative_to(RACINE).as_posix()}",
            # 🔴 L'etiquette est OBLIGATOIRE des qu'il y a une surcharge : sans elle, deux
            # configurations differentes rendraient deux artefacts indiscernables.
            "CERTUS_PROBE_TAG": tag,
        },
    )
    p.wait()
    try:
        p._certus_journal.close()  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    art = _lire_artefact(_resoudre_artefact(a.composant, a.mode, a.graine_notation, tag))
    if art is None:
        print(f"  🔴 la notation finale n'a pas rendu de mesure (EXIT={p.returncode}).")
        return 1
    dep = _deposables(art)
    print()
    print("=" * 78)
    if not dep:
        _evt("fin", trouve=False, raison="aucun plan de l'union ne tient a la notation")
        print("  🔴 AUCUN plan de l'union ne tient a la notation sur une graine disjointe.")
        print("     Les deposables trouves etaient donc propres a leur realisation.")
        return 1
    best = dep[0]
    seel = _seel(best["score"])
    print(f"  🟢 RESULTAT CITABLE : SEEL {seel:.4f} nm · {best['n_blocs']} blocs · "
          f"plantage {100 * best['crash_rate']:.2f} % · {len(dep)} deposable(s)")
    print(f"     trouve par {sorted(qui_trouvent)} · note sur {a.graine_notation}, disjointe")
    print(f"     artefact : reports/{_nom_artefact(a.composant, a.mode, a.graine_notation, tag)}")
    if meilleur_seel is not None:
        # 🔑 CE DELTA EST LE CANAL DE MALEDICTION DU VAINQUEUR, MESURE A CHAQUE CAMPAGNE. Il
        # valait +12,9 % le 2026-08-15 et +0,55 % le 2026-08-22 : ce n'est donc pas une
        # constante, et le publier a chaque fois evite de le supposer petit.
        ecart = 100.0 * (seel - meilleur_seel) / meilleur_seel
        print(f"     annonce en cours de campagne {meilleur_seel:.4f} nm -> "
              f"apres notation disjointe {seel:.4f} nm   ({ecart:+.2f} %)")
        if ecart > 2.59:
            print("     ⚠️  l'ecart depasse le bruit de 2,59 % sur une DIFFERENCE de SEEL : "
                  "le chiffre annonce en cours de route etait OPTIMISTE.")
    _evt("resultat", seel=seel, n_blocs=best["n_blocs"], crash=best["crash_rate"],
         deposables=len(dep), graine_notation=a.graine_notation,
         seel_provisoire=meilleur_seel, graines_trouvees=sorted(qui_trouvent),
         artefact=_nom_artefact(a.composant, a.mode, a.graine_notation, tag))
    _evt("fin", trouve=True, non_essayees=sorted(set(jamais_lancees)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
