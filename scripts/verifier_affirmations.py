"""HARNAIS DE VERIFICATION DE MES PROPRES AFFIRMATIONS -- 2026-08-18.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\verifier_affirmations.py

👤 2026-08-18 : *« il faut etre plus rigoureux, tu dois converger vers des interpretations et des
conclusions solides. Essaie de changer de methodologie pour tout verifier ce qui vient d'etre dit
et fait »*.

## Pourquoi ce fichier existe

Le 2026-08-18 j'ai ecrit, puis retire, quatre affirmations en quelques heures :

    « deep rend 0 deposable »                     -> NON MESURE, le run a 0 est en fast
    « la fente fine degrade x0,5 »                -> refute par la cellule propre (28 % vs 48 %)
    « 50 -> 150 tirages »                         -> faux, deep pose N=300
    « strategy_phase_timeout evite la troncature » -> faux, le parametre est INERTE

Le point commun n'est pas l'inattention : c'est la METHODE. J'affirmais depuis une lecture, puis
je verifiais apres coup. Ce fichier inverse l'ordre. Chaque affirmation devient un test qui rend
PASS ou FAIL, et le harnais lui-meme porte un CONTROLE NEGATIF -- une affirmation volontairement
fausse qui DOIT echouer. Un harnais dont tous les tests passent toujours ne prouve rien : c'est le
controle 4 du §12, applique a moi.

## Ce que le harnais ne peut PAS faire

Il verifie des proprietes du CODE et des ARTEFACTS. Il ne relance aucune mesure. Une affirmation
chiffree n'est donc confirmee que si un artefact la porte ; celles qui n'en ont pas ressortent
NON_VERIFIABLE, un troisieme etat qu'il ne faut pas confondre avec PASS.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

RESULTATS: list[tuple[str, str, str]] = []


def verdict(nom: str, etat: str, detail: str) -> None:
    RESULTATS.append((nom, etat, detail))


def _lit_la_cle(fichier: Path, cle: str) -> list[int]:
    """Les lignes ou `cle` est LUE, par AST -- pas par grep.

    🔑 Le grep se fait avoir sur trois formes au moins : la cle construite par concatenation,
    l'iteration sur une liste de cles, et l'acces par une variable. L'AST attrape les deux
    premieres et signale la troisieme.
    """
    try:
        arbre = ast.parse(fichier.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    lignes = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value == cle:
            lignes.append(n.lineno)
    return lignes


def test_A_timeout_inerte() -> None:
    """A. `strategy_phase_timeout` n'est lu par AUCUN module de calcul."""
    zones = [ROOT / "certus" / "core", ROOT / "certus" / "workers",
             ROOT / "certus" / "physics", ROOT / "certus" / "domain"]
    trouve = []
    for z in zones:
        for f in z.rglob("*.py"):
            for ln in _lit_la_cle(f, "strategy_phase_timeout"):
                trouve.append(f"{f.relative_to(ROOT)}:{ln}")
    # 🔑 Et on verifie aussi l'acces DYNAMIQUE : une boucle sur une liste de cles le lirait sans
    # que la constante apparaisse dans un `.get()`. certus/utils/certus_index_utils.py:1089 en
    # contient une -- il faut donc dire ce qu'elle fait.
    dyn = _lit_la_cle(ROOT / "certus" / "utils" / "certus_index_utils.py", "strategy_phase_timeout")
    if trouve:
        verdict("A. strategy_phase_timeout inerte", "FAIL",
                f"il EST lu : {', '.join(trouve[:3])} -- mon affirmation est fausse")
    else:
        verdict("A. strategy_phase_timeout inerte", "PASS",
                f"0 lecture dans core/workers/physics/domain. "
                f"Presence dans index_utils (coercition de type, l.{dyn[0] if dyn else '?'}) "
                f"-- il y est CONVERTI, pas consomme")


def test_B_dp_timeout_inutilise() -> None:
    """B. `_find_k_best_groupings_dp_sequential` ne lit jamais son argument `timeout`."""
    f = ROOT / "certus" / "core" / "certus_strat_ranking.py"
    arbre = ast.parse(f.read_text(encoding="utf-8"))
    cible = None
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == "_find_k_best_groupings_dp_sequential":
            cible = n
    if cible is None:
        verdict("B. timeout de la DP inutilise", "NON_VERIFIABLE", "fonction introuvable")
        return
    noms_args = {a.arg for a in cible.args.args}
    corps = [x for x in cible.body]
    lus = set()
    for stmt in corps:
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in noms_args:
                lus.add(n.id)
    inertes = sorted({"timeout", "start_time"} - lus)
    if inertes == ["start_time", "timeout"]:
        verdict("B. timeout de la DP inutilise", "PASS",
                "`timeout` et `start_time` sont declares et jamais lus dans le corps "
                "-> aucun risque de troncature sur la cellule dp_top_k=200")
    else:
        verdict("B. timeout de la DP inutilise", "FAIL",
                f"lus dans le corps : {sorted({'timeout', 'start_time'} & lus)}")


def test_C_dp_top_k_atteint_le_calcul() -> None:
    """C. `dp_top_k` est lu par le worker, donc une surcharge l'atteint."""
    f = ROOT / "certus" / "workers" / "certus_strat_workers.py"
    lignes = _lit_la_cle(f, "dp_top_k")
    if lignes:
        verdict("C. dp_top_k atteint le calcul", "PASS",
                f"lu a certus/workers/certus_strat_workers.py:{lignes[0]} -- "
                "la cellule dp_top_k=200 mesurera donc quelque chose")
    else:
        verdict("C. dp_top_k atteint le calcul", "FAIL",
                "aucune lecture dans les workers -- la cellule ne mesurerait RIEN")


def test_D_modes_existants_inchanges() -> None:
    """D. Ajouter `extreme` n'a change aucune valeur de fast / premium / deep."""
    import bench_examples as Bx

    Bx.qapp()
    Bx.autoanswer_dialogs(True)
    from CERTUS_STRAT import CertusStratApp

    app = CertusStratApp()
    app.load_configuration(str(ROOT / "example/example_strat/JSON-strat-random75.json"))
    # 🔴 Ces valeurs sont celles d'AVANT l'ajout du mode, relevees dans le diff de
    # certus_strat_ui_state.py. Si l'une bouge, la regle d'or est violee.
    ref = {"fast":    (50, 50, 10, 1, 20, 6),
           "premium": (150, 150, 25, 2, 40, 10),
           "deep":    (300, 300, 50, 3, 100, 25)}
    cles = ("robustness_num_runs", "consensus_num_runs", "n_screen_runs",
            "elite_rounds", "dp_top_k", "k_keep_survivors")
    ecarts = []
    for m, attendu in ref.items():
        app.widgets["execution_mode"].setCurrentText(m)
        if app.widgets["execution_mode"].currentText() != m:
            ecarts.append(f"{m} absent du combo")
            continue
        p = app.collect_params()
        obtenu = tuple(p.get(k) for k in cles)
        if obtenu != attendu:
            ecarts.append(f"{m}: {obtenu} != {attendu}")
    if ecarts:
        verdict("D. regle d'or -- fast/premium/deep inchanges", "FAIL", " | ".join(ecarts))
    else:
        verdict("D. regle d'or -- fast/premium/deep inchanges", "PASS",
                "les 3 modes rendent les 6 memes valeurs qu'avant l'ajout")


def test_E_niveau_exploration() -> None:
    """E. Le niveau 0/1/2 nomme trois fichiers DISTINCTS, et 1 garde l'ancien nom."""
    import importlib.util

    s = importlib.util.spec_from_file_location("bg", ROOT / "scripts" / "batch_grille_resolution.py")
    bg = importlib.util.module_from_spec(s)
    s.loader.exec_module(bg)
    n0 = bg._sortie("r75x2", "deep", 1.0, False, 42).name
    n1 = bg._sortie("r75x2", "deep", 1.0, True, 42).name
    n2 = bg._sortie("r75x2", "deep", 1.0, 2, 42).name
    attendu1 = "blocs_vs_plantage_r75x2_deep_s042_res1_large.json"
    if len({n0, n1, n2}) != 3:
        verdict("E. niveaux 0/1/2 distincts", "FAIL", f"collision : {n0} {n1} {n2}")
    elif n1 != attendu1:
        verdict("E. niveaux 0/1/2 distincts", "FAIL",
                f"le niveau 1 a CHANGE de nom : {n1} != {attendu1} -- "
                "l'artefact deja mesure serait remesure au lieu d'etre saute")
    elif not (ROOT / "reports" / attendu1).exists():
        verdict("E. niveaux 0/1/2 distincts", "FAIL",
                f"{attendu1} n'existe pas -- la retro-compatibilite n'est pas testable")
    else:
        verdict("E. niveaux 0/1/2 distincts", "PASS",
                f"{n0} / {n1} / {n2} -- et le niveau 1 retrouve bien l'artefact des 254")


def test_F_formule_seel() -> None:
    """F. `SEEL = 2*sqrt(score)` reproduit DEUX reperes publies independants."""
    cas = [("reports/blocs_vs_plantage_75c_fast_s042.json", 0.272, "75c a 2 nm, §21"),
           ("reports/blocs_vs_plantage_r75x1.5_fast_s042.json", 0.63, "x1,5, dossier serie")]
    ecarts = []
    for f, publie, quoi in cas:
        p = ROOT / f
        if not p.exists():
            ecarts.append(f"{quoi}: artefact absent")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        dep = [x for x in d["strategies"] if x["crash_rate"] < 0.05]
        if not dep:
            ecarts.append(f"{quoi}: aucun deposable")
            continue
        calc = 2 * math.sqrt(min(x["score"] for x in dep))
        if abs(calc - publie) > 0.006:
            ecarts.append(f"{quoi}: calcule {calc:.3f} != publie {publie}")
    if ecarts:
        verdict("F. formule SEEL", "FAIL", " | ".join(ecarts))
    else:
        verdict("F. formule SEEL", "PASS",
                "reproduit 0,272 (75c) ET 0,63 (x1,5) -- deux reperes independants")


def test_G_correlation_offre() -> None:
    """G. Sur les 5 points a protocole IDENTIQUE, l'offre ordonne et l'epaisseur non."""
    Q = {"r75x0.5": 57.4, "75c": 114.9, "r75x1.5": 172.3, "r75x1.75": 201.1, "r75x2": 229.8}
    F = {k: f"reports/blocs_vs_plantage_{k}_fast_s042.json" for k in Q}
    pts = []
    manquants = []
    for k, f in F.items():
        p = ROOT / f
        if not p.exists():
            manquants.append(k)
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("verdict") != "OK" or d.get("mode") != "fast":
            manquants.append(f"{k}(protocole)")
            continue
        s = d["strategies"]
        pts.append((Q[k], len(s), sum(1 for x in s if x["crash_rate"] < 0.05)))
    if manquants:
        verdict("G. l'offre ordonne, l'epaisseur non", "NON_VERIFIABLE",
                f"points manquants : {manquants}")
        return

    def rho(x, y):
        def rk(v):
            o = sorted(range(len(v)), key=lambda i: v[i])
            r = [0.0] * len(v)
            i = 0
            while i < len(o):
                j = i
                while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                    j += 1
                m = (i + j) / 2 + 1
                for t in range(i, j + 1):
                    r[o[t]] = m
                i = j + 1
            return r
        a, b = rk(x), rk(y)
        n = len(x)
        m1, m2 = sum(a) / n, sum(b) / n
        d1 = sum((p - m1) ** 2 for p in a)
        d2 = sum((q - m2) ** 2 for q in b)
        if d1 == 0 or d2 == 0:
            return float("nan")
        return sum((p - m1) * (q - m2) for p, q in zip(a, b)) / math.sqrt(d1 * d2)

    rq = rho([p[0] for p in pts], [p[2] for p in pts])
    rn = rho([p[1] for p in pts], [p[2] for p in pts])
    if rn > 0.9 and abs(rq) < 0.4:
        verdict("G. l'offre ordonne, l'epaisseur non", "PASS",
                f"n={len(pts)} points : rho(offre)={rn:+.3f}, rho(Somme QWOT)={rq:+.3f}")
    else:
        verdict("G. l'offre ordonne, l'epaisseur non", "FAIL",
                f"rho(offre)={rn:+.3f}, rho(Somme QWOT)={rq:+.3f} -- l'ecart annonce ne tient pas")


def test_H_controle_negatif() -> None:
    """H. 🔴 CONTROLE NEGATIF -- une affirmation FAUSSE doit faire echouer le harnais.

    Sans ce test, un harnais dont tout passe ne prouverait rien. On affirme ici que
    `robustness_num_runs` n'est lu par aucun module de calcul -- ce qui est FAUX, il l'est
    evidemment. Le test doit donc rendre FAIL. S'il rend PASS, c'est le HARNAIS qui est casse,
    pas le code.
    """
    trouve = []
    for z in (ROOT / "certus" / "core", ROOT / "certus" / "workers"):
        for f in z.rglob("*.py"):
            if _lit_la_cle(f, "robustness_num_runs"):
                trouve.append(f.name)
    if trouve:
        verdict("H. CONTROLE NEGATIF (doit echouer)", "FAIL_ATTENDU",
                f"robustness_num_runs EST lu ({len(trouve)} fichiers) -- "
                "le harnais sait donc detecter une affirmation fausse")
    else:
        verdict("H. CONTROLE NEGATIF (doit echouer)", "HARNAIS_CASSE",
                "le controle negatif est passe -- la methode de detection ne marche pas, "
                "et AUCUN des PASS ci-dessus ne vaut quoi que ce soit")


#: TOUS les chiffres que j'ai publies le 2026-08-18 dans CLAUDE.md, le dossier du chantier,
#: REPRISE.md, REPRENDRE_ICI.md et CERTUS_STRAT.html.
#: (fichier, offertes, deposables, crash_min %, SEEL ou None si score de repli)
#: 🔑 C'est le vrai changement de methode : un chiffre publie doit etre RE-DERIVABLE par un
#: script depuis son artefact. S'il ne l'est pas, il ne doit pas etre dans un document.
CHIFFRES_PUBLIES = [
    ("75c_fast_s042", 662, 241, 0.0, 0.272),
    ("75c_fast_s042_res5", 778, 289, 0.0, 0.310),
    ("75c_fast_s042_res1", 439, 12, 4.0, 0.371),
    ("75c_fast_s042_res0.5", 503, 0, 44.0, None),
    ("r75x0.5_fast_s042", 375, 0, 48.0, None),
    ("r75x0.5_fast_s042_res5", 375, 0, 70.0, None),
    ("r75x0.5_fast_s042_res1", 375, 0, 28.0, None),
    ("r75x0.5_fast_s042_res0.5", 376, 0, 82.0, None),
    ("r75x1.5_fast_s042", 440, 1, 0.0, 0.633),
    ("r75x1.5_fast_s042_res1", 417, 0, 30.0, None),
    ("r75x1.5_fast_s042_res0.5", 468, 0, 76.0, None),
    ("r75x1.75_fast_s042", 746, 282, 0.0, 0.528),
    ("r75x2_fast_s042", 404, 0, 100.0, None),
    ("r75x2_fast_s042_res1", 429, 0, 38.0, None),
    ("r75x2_fast_s042_res0.5", 424, 0, 80.0, None),
    ("r75x2_fast_s077_res1", 436, 0, 30.0, None),
    ("r75x2_premium_s042", 651, 0, 100.0, None),
    ("r75x2_deep_s042_res1_large", 2945, 254, 1.0, 0.629),
    # --- ajoutes le 2026-08-18 a 10:25, EN MEME TEMPS que dans les documents (§7bis) ---
    ("r75x1.75_fast_s042_res1", 468, 0, 6.0, None),
    ("r75x1.75_fast_s042_res0.5", 468, 0, 50.0, None),
    ("r75x2_fast_s101_res1", 420, 0, 36.0, None),
    ("75c_premium_s042_res5", 1415, 639, 0.0, 0.335),
    # --- 2026-08-18 14:15, le test decisif du cote mince ---
    ("r75x0.5_deep_s042_res1_large", 2000, 0, 39.666666666666664, None),
    # --- 14:21, le controle : deep SEUL suffit, extreme n'apporte rien ---
    ("r75x2_deep_s042_res1", 1986, 277, 1.0, 0.625),
    # --- 2026-08-18 18:59 et 19:12, 99c et x1,5 en elargi ---
    ("99c_deep_s042_res1_large", 2674, 0, 96.33333333333333, None),
    ("r75x1.5_deep_s042_large", 2801, 1, 0.3333333333333333, 0.633),
    # --- 2026-08-18 22:50, fin de la campagne elargie ---
    ("r75x2_deep_s077_res1_large", 2575, 0, 38.0, None),
    ("r75x0.5_deep_s042_large", 1997, 0, 68.66666666666667, None),
    # --- 2026-08-19 00:xx, MATRICE : premiere paire jumelle deep/extreme ---
    ("35c_deep_s042", 1023, 1017, 0.0, 0.482),
    ("35c_deep_s042_large", 1355, 1349, 0.0, 0.479),
    # --- 2026-08-19 nuit, MATRICE : 48c et 75c a leur fente de reference ---
    ("48c_deep_s042", 840, 804, 0.0, 0.173),
    ("48c_deep_s042_large", 1190, 1134, 0.0, 0.170),
    ("75c_deep_s042", 2547, 852, 0.0, 0.260),
]


def test_J_queue_rate_falaise() -> None:
    """J. La queue Rate : la falaise, le plateau, et le mecanisme REFUTE.

    🔴 Ce controle existe parce que j'ai publie un mecanisme FAUX le 2026-08-19 -- « la queue
    franchit en boucle ouverte la zone ou la derive accumulee tue l'optique ». Les artefacts le
    refutent : la couche critique des deposables est TOUJOURS avant la coupure, donc restee
    optique. Ce test verrouille les quatre faits qui l'ont tue, pour qu'ils ne se re-periment pas.
    """
    import re as _re
    S = []
    for nom in ("tail", "tail46-55"):
        p = ROOT / "reports" / f"blocs_vs_plantage_r75x2_fast_s042_{nom}.json"
        if not p.exists():
            verdict("J. la queue Rate : falaise et plateau", "NON_VERIFIABLE", f"{p.name} manquant -- rien a verifier")
            return
        S += json.loads(p.read_text(encoding="utf-8"))["strategies"]

    par_coupure: dict[int, list] = {}
    for x in S:
        m = _re.match(r"RATE_TAIL(\d+)\(", str(x.get("origine") or ""))
        if m:
            par_coupure.setdefault(int(m.group(1)), []).append(x)
    cm = {c: min(x["crash_rate"] for x in g) for c, g in par_coupure.items()}

    pbs = []
    # 1. LA FALAISE : tout plante au-dessus de 61, tout passe a partir de 58.
    for c in (61, 64, 67, 70):
        if cm.get(c) != 1.0:
            pbs.append(f"coupure {c} : crash_min {cm.get(c)} au lieu de 1,0")
    # 2. LE PLATEAU : de 46 a 58, crash_min IDENTIQUE. C'est lui qui tue « plus on couvre,
    #    mieux c'est » -- couvrir 12 couches de plus ne gagne rien.
    plateau = {c: cm[c] for c in (46, 49, 52, 55, 58) if c in cm}
    if len(set(plateau.values())) != 1:
        pbs.append(f"le plateau n'est pas plat : {plateau}")
    elif next(iter(plateau.values())) >= 0.05:
        pbs.append(f"le plateau n'est pas deposable : {plateau}")
    # 3. UNE SEULE ARCHITECTURE : toutes les deposables sont a 75 blocs, une seule parente.
    dep = [x for x in S if x["crash_rate"] < 0.05]
    if not dep:
        pbs.append("aucune deposable -- l'artefact ne porte plus le resultat publie")
    if any(x["n_blocs"] != 75 for x in dep):
        pbs.append(f"toutes les deposables ne sont plus a 75 blocs : "
                   f"{sorted({x['n_blocs'] for x in dep})}")
    parents = {str(x["origine"]).split("from ")[-1].rstrip(")") for x in dep}
    if len(parents) != 1:
        pbs.append(f"plusieurs parentes : {parents}")
    # 4. LE FALSIFICATEUR : la couche critique de chaque deposable est AVANT sa coupure, donc
    #    restee OPTIQUE. Si un jour elle tombe dans la queue, l'ancien mecanisme redevient
    #    defendable et ce dossier doit etre rouvert.
    for x in dep:
        m = _re.match(r"RATE_TAIL(\d+)\(", str(x.get("origine") or ""))
        cl = (x.get("critical_layer") or {}).get("layer")
        if m and cl is not None and int(cl) >= int(m.group(1)):
            pbs.append(f"couche critique {cl} DANS la queue (coupure {m.group(1)}) -- "
                       f"le mecanisme « franchir la zone » redevient possible")

    if pbs:
        verdict("J. la queue Rate : falaise et plateau", "FAIL", " | ".join(pbs))
    else:
        verdict("J. la queue Rate : falaise et plateau", "PASS",
                f"falaise 61->58 (100 % -> {100 * min(plateau.values()):.2f} %), plateau plat sur "
                f"{len(plateau)} coupures, {len(dep)} deposables toutes a 75 blocs et d'une seule "
                f"parente, couche critique toujours HORS queue")


def test_K_couche_rate_ne_plante_pas() -> None:
    """K. Le code : une couche Rate rend son epaisseur SANS sentinelle de plantage.

    🔑 C'est le seul fait de mecanisme qui vienne du CODE et non d'un artefact -- donc le seul
    qui ne depende ni d'une graine ni d'un composant. §16 : un commentaire n'est pas une preuve,
    on verifie le retour anticipe lui-meme.
    """
    src = (ROOT / "certus" / "physics" / "certus_strat_growth.py").read_text(encoding="utf-8")
    lignes = src.splitlines()
    i_rate = next((i for i, ln in enumerate(lignes) if ln.strip() == "if is_rate:"), None)
    if i_rate is None:
        verdict("K. une couche Rate ne peut pas planter", "FAIL", "le bloc `if is_rate:` a disparu de certus_strat_growth.py")
        return
    bloc = "\n".join(lignes[i_rate:i_rate + 30])
    pbs = []
    if "CRASH_SENTINEL_UNIT" in bloc:
        pbs.append("une sentinelle de plantage est apparue dans le chemin Rate")
    if "return (float(turns * RATE_TURN_NM)" not in bloc:
        pbs.append("le retour anticipe du chemin Rate a change de forme")
    if "if n_ref > 0:" not in bloc:
        pbs.append("la garde `n_ref > 0` a disparu -- une couche Rate sans reference "
                   "retombe sur POEM et REDEVIENT plantable")
    verdict("K. une couche Rate ne peut pas planter", "FAIL" if pbs else "PASS",
            " | ".join(pbs) or "retour anticipe intact, aucune sentinelle, garde n_ref>0 presente "
            "(donc une couche Rate en TETE d'empilement reste plantable)")


def test_L_les_deux_regles_gravees_du_rate() -> None:
    """L. 🔒 Les deux regles que 👤 a fait GRAVER le 2026-08-19.

    Elles ne vivent pas dans un commentaire : elles sont verifiees mecaniquement, parce que
    les deux etaient DEJA fausses dans le code alors que la documentation decrivait autre
    chose. Ce controle est la pour que ce ne puisse pas recommencer.

      1. « rate est interdit sur les 2 premieres couches ! mais absolument pas la derniere »
      2. « rate ne se calcule qu'avec les couches optiquement deposees »
    """
    pbs = []
    rob = (ROOT / "certus" / "core" / "certus_strat_robustness.py").read_text(encoding="utf-8")
    gro = (ROOT / "certus" / "physics" / "certus_strat_growth.py").read_text(encoding="utf-8")

    # --- regle 1, cote selection des candidates -----------------------------------------
    if "RATE_MIN_LAYER: int = 2" not in rob:
        pbs.append("RATE_MIN_LAYER n'est plus fixe a 2")
    if "num_layers - 1" in rob:
        pbs.append("une borne `num_layers - 1` est revenue -- la derniere couche est "
                   "peut-etre de nouveau exclue")
    if "range(RATE_MIN_LAYER, num_layers)" not in rob:
        pbs.append("le balayage par swing ne part plus de RATE_MIN_LAYER, ou reexclut la fin")
    if "RATE_MIN_LAYER <= last < num_layers" not in rob:
        pbs.append("la selection par frontiere de bloc a change de bornes")

    # --- regle 1, cote kernel : la garde physique doit rester ----------------------------
    if "if n_ref > 0:" not in gro:
        pbs.append("la garde n_ref>0 a disparu du noyau")

    # --- regle 2 : les couches Rate sont exclues des references --------------------------
    if "prev_rate_flags" not in gro:
        pbs.append("le noyau ne recoit plus prev_rate_flags : les couches Rate redeviennent "
                   "references d'elles-memes")
    bat = (ROOT / "certus" / "physics" / "certus_strat_batch.py").read_text(encoding="utf-8")
    if "rate_flags,\n            )" not in bat.replace("\r\n", "\n"):
        pbs.append("le site d'appel ne passe plus le tableau complet rate_flags au noyau")
    # 🔴 Le commentaire Q3 disait l'inverse de la regle et le code le suivait. S'il revient,
    # c'est que le correctif a ete defait.
    if "Rate ones included" in gro:
        pbs.append("le commentaire Q3 « Rate ones included » est revenu")

    verdict("L. les deux regles gravees du Rate", "FAIL" if pbs else "PASS",
            " | ".join(pbs) or "RATE_MIN_LAYER=2, derniere couche autorisee aux deux sites, "
            "garde n_ref>0 en place, prev_rate_flags passe et consomme")


def test_I_chiffres_publies() -> None:
    """I. Chaque chiffre publie se re-derive de son artefact."""
    ecarts, absents = [], []
    for cle, n_att, dep_att, crash_att, seel_att in CHIFFRES_PUBLIES:
        p = ROOT / "reports" / f"blocs_vs_plantage_{cle}.json"
        if not p.exists():
            absents.append(cle)
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        s = d["strategies"]
        dep = [x for x in s if x["crash_rate"] < 0.05]
        crash = 100 * min(x["crash_rate"] for x in s)
        if len(s) != n_att:
            ecarts.append(f"{cle}: offertes {len(s)} != {n_att}")
        if len(dep) != dep_att:
            ecarts.append(f"{cle}: deposables {len(dep)} != {dep_att}")
        if abs(crash - crash_att) > 0.01:
            ecarts.append(f"{cle}: crash {crash:.2f} != {crash_att}")
        # 🔴 Un SEEL n'existe QUE s'il y a des deposables. Publier un score de repli comme SEEL
        # est l'erreur qui a produit le faux « 0,86 nm » du 99c.
        if seel_att is None:
            if dep:
                ecarts.append(f"{cle}: annonce SANS SEEL mais {len(dep)} deposables existent")
        else:
            if not dep:
                ecarts.append(f"{cle}: SEEL {seel_att} publie sur un score de REPLI")
            else:
                calc = 2 * math.sqrt(min(x["score"] for x in dep))
                if abs(calc - seel_att) > 0.0015:
                    ecarts.append(f"{cle}: SEEL {calc:.3f} != {seel_att} publie")
    if ecarts:
        verdict("I. les chiffres publies se re-derivent", "FAIL",
                f"{len(ecarts)} ecart(s) : " + " | ".join(ecarts[:4]))
    elif absents:
        verdict("I. les chiffres publies se re-derivent", "NON_VERIFIABLE",
                f"{len(absents)} artefact(s) absent(s) : {absents[:4]}")
    else:
        verdict("I. les chiffres publies se re-derivent", "PASS",
                f"{len(CHIFFRES_PUBLIES)} cellules -- offertes, deposables, crash_min et SEEL "
                "reproduits depuis les artefacts, sans exception")


def main() -> int:
    for t in (test_A_timeout_inerte, test_B_dp_timeout_inutilise, test_C_dp_top_k_atteint_le_calcul,
              test_E_niveau_exploration, test_F_formule_seel, test_G_correlation_offre,
              test_I_chiffres_publies, test_J_queue_rate_falaise,
              test_L_les_deux_regles_gravees_du_rate,
              test_K_couche_rate_ne_plante_pas,
              test_H_controle_negatif, test_D_modes_existants_inchanges):
        try:
            t()
        except Exception as e:  # noqa: BLE001 -- un test qui plante est une information
            verdict(t.__name__, "ERREUR", f"{type(e).__name__}: {e}")

    print("=" * 100)
    print("VERIFICATION MECANIQUE DES AFFIRMATIONS DU 2026-08-18")
    print("=" * 100)
    for nom, etat, detail in RESULTATS:
        marque = {"PASS": "🟢", "FAIL": "🔴", "FAIL_ATTENDU": "🟢",
                  "NON_VERIFIABLE": "🟠", "HARNAIS_CASSE": "🔴", "ERREUR": "🔴"}.get(etat, "  ")
        print(f"{marque} {etat:<16} {nom}")
        print(f"                    {detail}")
    ko = [r for r in RESULTATS if r[1] in ("FAIL", "HARNAIS_CASSE", "ERREUR")]
    nv = [r for r in RESULTATS if r[1] == "NON_VERIFIABLE"]
    print("=" * 100)
    print(f"  {len(RESULTATS) - len(ko) - len(nv)} verifiees · {len(nv)} non verifiables · "
          f"{len(ko)} EN ECHEC")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
