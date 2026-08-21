"""BATCH DE NUIT -- FAIRE TROUVER A LA GRAINE 42 CE QUE LA GRAINE 77 TROUVE.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\batch_nuit_2026-08-21_seed42.py [heures]

👤 2026-08-20, 23h : *« objectif : que seed 42 trouve d'aussi bonnes strategies que seed 77 en
terme de seel et l'implanter sur le code de production »*, avec autonomie totale sur les
arbitrages pendant une dizaine d'heures.

⚠️ CE BATCH EST ANTERIEUR A UNE DECISION DE 👤. Le 2026-08-21 il a LEVE la contrainte
mono-graine : *« meme si le code en production est ralenti, ce sera un gain enorme d'inclure
des strategies diverses venant de plusieurs seed »*. Les quatre cellules ci-dessous cherchent
donc toutes a debloquer la graine 42 SEULE -- ce qui reste une question valide (§18.4 : le
levier A decide si le multi-graines est necessaire), mais n'est plus la seule voie autorisee.

## Le composant est `r75x2` a 2 nm, en `deep`, graine 42. EXCLUSIVEMENT.

C'est l'etalon courant. Rien d'autre ne tourne cette nuit : une mesure, une machine.

## L'ETAT DE DEPART, mesure et non suppose

    r75x2 @ 2 nm deep    graine 42 : 1617 strategies, 0 deposable, crash_min 100,00 %
                         graine 77 : 2231 strategies, 547 deposables, meilleure SEEL 0,5692

    hors ELITE : 0 deposable AUX DEUX GRAINES (1617 et 1488), crash mediane 100 %
    ELITE gr.42 : 4226 candidates engendrees, 1327 evaluees en entier, 0 RETENUE
                  rejets : halving 1368 · RMSE 211 (16 %) · PLANTAGE 1116 (84 %)

Et le chainage est etabli (`PLAN_PRODUCTION_2026-08-20.md` §13) : les 1116 rejets « plantage »
SONT la porte de plantage --

    _crash_gate_rejects (robustness.py:2693) -> final_score = inf -> robustness_score = inf
    -> ELITE : not np.isfinite(full_score) (consensus.py:792)

## 🔒 L'ARBITRAGE QUE J'AI PRIS, ET POURQUOI

👤 proposait de **relacher bruit et derive** pour laisser passer plus de candidates dans ELITE.
C'est la bonne cible -- les 84 %. **Mais je ne lance PAS cette cellule sans surveillance**, et
c'est un choix, pas un oubli :

    relacher le bruit change LE MONDE ou vivent les candidates. Tout ce qu'on y trouve doit
    donc etre re-juge AU NOMINAL, sinon on rapporte un SEEL flatteur qui ne decrit aucune
    machine. Or le juge au nominal -- `probe_renoter.py` -- est EN PANNE, et sa panne n'est
    pas localisee : six causes candidates eliminees le 2026-08-20 au soir, aucune trouvee.

    Un resultat produit cette nuit par relachement serait donc inexploitable au matin.

🟢 **Ce que je lance a la place : quatre leviers qui ne relachent AUCUNE physique.** Chacun ne
change qu'une regle de DECISION ou l'etendue de la RECHERCHE, jamais le modele de la machine.
Ce qu'ils trouvent est donc deja juge au nominal, et directement publiable.

| levier | ce qu'il change | pourquoi il est honnete |
|---|---|---|
| `crash_gate_confidence` | la porte compare une BORNE DE CONFIANCE au lieu d'un taux estime | la tolerance de 5 % ne bouge pas ; c'est l'estimateur qui etait faux |
| `elite_stop_on_no_gain` | les rounds 2 et 3 de `deep` tournent enfin | a 0 retenue, le round 1 coupait TOUT |
| `elite_wl_neighbor_span` | ELITE explore lambda ± 2 nm au lieu de ± 1 | plus de portee, meme physique |
| `elite_max_candidates` | le plafond de 120, atteint dans 30 rounds sur 46 | plus d'offre, meme physique |

## 🔴 LA PORTE C1, ET LE BATCH S'ARRETE SI ELLE NE PASSE PAS

La cellule 1 tourne aux **reglages d'origine**. Elle doit rendre EXACTEMENT :

    1617 strategies · 0 deposable · crash_min 100,00 % · ELITE 0 strategie

L'instrument `[ELITE-WL]` pose au commit `5105fc8` est de la journalisation pure. **Tout ecart
signifie qu'il a fui dans le calcul, et alors TOUTE la nuit est a jeter avant d'etre lue.** Le
batch refuse de continuer dans ce cas -- il vaut mieux perdre neuf heures que rapporter neuf
heures de chiffres faux.

## Ce que la cellule 1 decide, et l'ordre des suivantes en depend

Les histogrammes `[ELITE-WL]` rendent deux lectures que rien ne portait avant :

    lambda gagnante ABSENTE des engendrees -> ELITE ne regarde jamais la -> les PARENTS
    lambda PRESENTE et dans un rejet       -> ELITE regarde et jette     -> la PORTE

    bandes de plantage sous 25 %  -> la porte a confiance a une chance -> `cgc95` d'abord
    bandes toutes a 100 %         -> aucune porte ne les sauve          -> `reach` d'abord

Le batch lit, decide, et **ecrit sa decision** dans le rapport. Il ne la devine pas.

## Ce que ce batch NE fait pas

- il ne committe rien ;
- il n'ecrase aucun artefact (`scripts/_artefact.py` et la garde de la sonde) ;
- il ne tronque aucun journal : la sortie COMPLETE de chaque cellule va au disque AVANT
  d'en imprimer la queue. 🔴 Le 2026-08-20, les pilotes jetaient 99 % du journal -- 30 lignes
  sur 15 887 -- et une conclusion en est morte ;
- il ne lance jamais deux cellules a la fois ;
- il ne cache aucun abandon : une cellule sautee faute de temps est DITE, avec son motif.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 🔴 La console Windows est en cp1252 et ce script imprime des pastilles. Sans ces deux
# lignes, UnicodeEncodeError leve A LA FIN -- apres la mesure, a l'ecriture de la synthese.
# 📏 Mesure du 2026-08-21 : trois plantages en une session, dont un qui a perdu
# l'artefact d'un run de cinquante minutes. `tests/unit/test_scripts_console_cp1252.py`
# refuse desormais tout nouveau script non protege.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PY = r"C:\envs\certus\Scripts\python.exe"
SONDE = "scripts/probe_blocs_vs_plantage.py"

#: `r75x2`, `deep`, fente 2 nm, graine 42, aucun profil elargi, aucune queue Rate.
#: Positionnels de la sonde : composant mode fente min_tp res_nm elargi graine par_swing
ARGS_BASE = ["r75x2", "deep", "0", "0", "2.0", "0", "42", "0"]

#: La reference que la cellule 1 doit reproduire au chiffre pres -- porte C1.
C1_ATTENDU = {"n_strats": 1617, "n_deposables": 0, "crash_min": 1.0, "n_elite": 0}

#: Tolerance de 👤 : 95 % des depots doivent aboutir.
CRASH_TOL = 0.05

#: Duree maximale accordee a une cellule. Au-dela, on la tue et on passe a la suivante :
#: une cellule qui derape ne doit pas manger les autres.
CELLULE_TIMEOUT_S = 4 * 3600

#: Marge gardee avant l'echeance globale pour ne pas lancer une cellule qui ne finira pas.
#: 📏 Les durees mesurees sur cette machine vont de 107 a 176 min ; on refuse de demarrer
#: sous 150 min de reste, et on le DIT.
RESERVE_MIN = 150


def _log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE DES SORTIES
# ─────────────────────────────────────────────────────────────────────────────

def resume_artefact(chemin: Path) -> dict:
    """Les quatre chiffres qui decident, plus le meilleur SEEL parmi les deposables.

    🔴 `SEEL = 2*sqrt(score)` n'a de sens QUE sur une strategie deposable. Sur une
    population qui plante a 100 %, le score est un REPLI (`_worst_finite_rmse`) et
    `CLAUDE.md` §21 interdit de le citer comme une performance. On rend donc `None`
    plutot qu'un chiffre flatteur.
    """
    import math

    d = json.loads(chemin.read_text(encoding="utf-8"))
    S = d.get("strategies") or []
    crs = [s.get("crash_rate") for s in S if s.get("crash_rate") is not None]
    dep = [s for s in S if (s.get("crash_rate") if s.get("crash_rate") is not None else 1.0) <= CRASH_TOL]
    elite = [s for s in S if str(s.get("origine", "")).startswith("ELITE")]
    seel = None
    if dep:
        best = min(dep, key=lambda s: s.get("score", float("inf")))
        sc = best.get("score")
        if sc is not None and sc >= 0:
            seel = 2.0 * math.sqrt(float(sc))
    return {
        "artefact": chemin.name,
        "n_strats": len(S),
        "n_deposables": len(dep),
        "crash_min": min(crs) if crs else None,
        "n_elite": len(elite),
        "n_elite_deposables": sum(
            1 for s in elite
            if (s.get("crash_rate") if s.get("crash_rate") is not None else 1.0) <= CRASH_TOL
        ),
        "meilleur_seel_deposable": seel,
        "config": d.get("config"),
        "profondeur": d.get("profondeur"),
    }


_RE_WL = re.compile(
    r"\[ELITE-WL\] Round (\d+) exit=(\w+) (generated|rejected_\w+|reject_crash_bands) (.*)"
)


def lire_elite_wl(journal: Path) -> dict:
    """Agrege les histogrammes `[ELITE-WL]` de tous les rounds d'une cellule.

    ⚠️ REGLE DE COMPTAGE, elle vient du code : une candidate compte UNE FOIS par lambda
    DISTINCTE de ses blocs. Les totaux somment donc a plus que le nombre de candidates.
    Un compte dit « combien de candidates ont utilise cette lambda », jamais « combien de
    blocs ». Confondre les deux serait un rapport mal echelonne.
    """
    agg: dict[str, dict[str, int]] = {}
    rounds = 0
    sorties: dict[str, int] = {}
    if not journal.is_file():
        return {"absent": True}
    for ligne in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _RE_WL.search(ligne)
        if not m:
            continue
        _rnd, exit_name, quoi, reste = m.groups()
        if quoi == "generated":
            rounds += 1
            sorties[exit_name] = sorties.get(exit_name, 0) + 1
        cible = agg.setdefault(quoi, {})
        if reste.strip() in ("(none)", ""):
            continue
        for jeton in reste.split():
            if jeton.startswith("[+"):
                break
            if ":" not in jeton:
                continue
            cle, _, n = jeton.rpartition(":")
            try:
                cible[cle] = cible.get(cle, 0) + int(n)
            except ValueError:
                continue
    return {"absent": False, "rounds": rounds, "sorties": sorties, "histogrammes": agg}


def lire_compteurs(journal: Path) -> dict:
    """Les trois compteurs de rejets ELITE, sommes sur tous les rounds."""
    tot = {"halving": 0, "full_rmse": 0, "score_non_fini": 0, "retenues": 0, "engendrees": 0}
    if not journal.is_file():
        return tot
    rx = re.compile(
        r"rejets -- halving=(\d+) full_rmse=(\d+) score_non_fini=(\d+) "
        r"\| retenues=(\d+) sur (\d+) engendrees"
    )
    for ligne in journal.read_text(encoding="utf-8", errors="replace").splitlines():
        m = rx.search(ligne)
        if m:
            h, f, s, r, e = (int(x) for x in m.groups())
            tot["halving"] += h
            tot["full_rmse"] += f
            tot["score_non_fini"] += s
            tot["retenues"] += r
            tot["engendrees"] += e
    return tot


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION D'UNE CELLULE
# ─────────────────────────────────────────────────────────────────────────────

def lancer(nom: str, overrides: str, tag: str, journal_dir: Path) -> dict:
    """Une cellule : un run de la sonde, journal COMPLET au disque, artefact localise.

    🔴 LE JOURNAL EST ECRIT EN ENTIER AVANT TOUT AFFICHAGE. Le 2026-08-20, les pilotes de
    batch capturaient tout et n'imprimaient que les 30 dernieres lignes sur 15 887 : une
    hypothese sur ELITE a ete formulee puis abattue parce qu'elle lisait une queue.
    """
    env = dict(os.environ)
    env["CERTUS_BENCH_TIMEOUT_S"] = "14400"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    if overrides:
        env["CERTUS_PROBE_OVERRIDES"] = overrides
        env["CERTUS_PROBE_TAG"] = tag
    else:
        env.pop("CERTUS_PROBE_OVERRIDES", None)
        env.pop("CERTUS_PROBE_TAG", None)

    journal = journal_dir / f"journal_{nom}.log"
    t0 = time.time()
    _log(f"CELLULE {nom} -- demarrage. overrides={overrides or '(aucune)'}")
    try:
        with journal.open("w", encoding="utf-8", errors="replace") as fh:
            proc = subprocess.run(
                [PY, "-u", SONDE, *ARGS_BASE],
                cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                timeout=CELLULE_TIMEOUT_S, check=False,
            )
        code = proc.returncode
        motif = None
    except subprocess.TimeoutExpired:
        code, motif = -9, f"TIMEOUT apres {CELLULE_TIMEOUT_S // 60} min"
    duree = (time.time() - t0) / 60.0

    txt = journal.read_text(encoding="utf-8", errors="replace") if journal.is_file() else ""
    art = None
    m = re.findall(r"consigne dans (reports[/\\][^\s]+\.json)", txt)
    if m:
        cand = ROOT / m[-1].replace("\\", "/")
        if cand.is_file():
            art = cand

    res = {
        "cellule": nom, "tag": tag, "overrides": overrides,
        "code": code, "duree_min": round(duree, 1), "motif": motif,
        "journal": str(journal.relative_to(ROOT)),
        "lignes_journal": len(txt.splitlines()),
        "elite_wl": lire_elite_wl(journal),
        "compteurs": lire_compteurs(journal),
    }
    if art is not None:
        try:
            res["resume"] = resume_artefact(art)
        except Exception as e:  # noqa: BLE001 -- un artefact illisible se DIT
            res["resume_erreur"] = f"{type(e).__name__}: {e}"
    else:
        res["resume_erreur"] = "aucun artefact trouve dans le journal"
    _log(f"CELLULE {nom} -- fini en {duree:.1f} min, code {code}. "
         f"{res.get('resume', res.get('resume_erreur'))}")
    return res


# ─────────────────────────────────────────────────────────────────────────────
# DECISION
# ─────────────────────────────────────────────────────────────────────────────

def porte_c1(resume: dict) -> tuple[bool, str]:
    """La cellule 1 reproduit-elle la reference ? Sinon l'instrument a fui dans le calcul."""
    ecarts = []
    for cle, attendu in C1_ATTENDU.items():
        vu = resume.get(cle)
        if cle == "crash_min":
            ok = vu is not None and abs(float(vu) - attendu) < 1e-9
        else:
            ok = vu == attendu
        if not ok:
            ecarts.append(f"{cle} : attendu {attendu}, vu {vu}")
    return (not ecarts), " | ".join(ecarts)


def decider_ordre(cell1: dict) -> tuple[list[str], str]:
    """Ordonne les cellules suivantes d'apres ce que la cellule 1 a mesure.

    🔑 La decision est ECRITE, pas devinee. Deux lectures, deux ordres.
    """
    wl = cell1.get("elite_wl") or {}
    hist = (wl.get("histogrammes") or {}) if not wl.get("absent") else {}
    bandes = hist.get("reject_crash_bands") or {}
    engendrees = hist.get("generated") or {}

    # Part des rejets « plantage » qui ne sont PAS a 100 % : ceux qu'une borne de
    # confiance peut esperer recuperer.
    tot_snf = sum(n for k, n in bandes.items() if k.startswith("score_non_fini/"))
    a_100 = sum(n for k, n in bandes.items() if k == "score_non_fini/100%")
    recuperables = tot_snf - a_100
    part = (recuperables / tot_snf) if tot_snf else 0.0

    lam685 = engendrees.get("685") or engendrees.get("685.0") or 0

    motifs = [
        f"rejets plantage lus : {tot_snf} (dont {a_100} a 100 %, {recuperables} en dessous "
        f"= {100 * part:.1f} %)",
        f"685 nm dans les candidates ENGENDREES : {lam685}",
    ]
    if tot_snf == 0:
        motifs.append("AUCUNE bande lue -- l'instrument n'a rien emis, ou aucun round n'a "
                      "atteint l'evaluation complete. On garde l'ordre par defaut.")
        return ["cgc95", "nogain", "reach"], " · ".join(motifs)
    if part >= 0.02:
        motifs.append("des rejets sous 100 % existent : la porte a confiance a une cible "
                      "-> cgc95 EN PREMIER.")
        return ["cgc95", "reach", "nogain"], " · ".join(motifs)
    motifs.append("tous les rejets sont a 100 % : aucune porte ne les sauve, c'est la PORTEE "
                  "de la recherche qu'il faut ouvrir -> reach EN PREMIER.")
    return ["reach", "nogain", "cgc95"], " · ".join(motifs)


#: Les trois leviers honnetes, et un seul change a la fois -- contrainte C3.
CELLULES = {
    "cgc95": ("crash_gate_confidence=0.95",
              "la porte compare une borne de confiance a 95 % au lieu d'un taux estime"),
    "nogain": ("elite_stop_on_no_gain=false",
               "les rounds 2 et 3 de deep tournent enfin : a 0 retenue, le round 1 coupait tout"),
    "reach": ("elite_wl_neighbor_span=2,elite_max_candidates=240",
              "ELITE explore lambda +/- 2 nm, plafond porte a 240 -- plus de PORTEE, "
              "meme physique. ⚠️ DEUX reglages a la fois : attribution impossible entre eux, "
              "assume car ils forment une seule idee (la portee) et le temps est compte"),
}


# ─────────────────────────────────────────────────────────────────────────────
# RAPPORT
# ─────────────────────────────────────────────────────────────────────────────

def ecrire_rapport(chemin: Path, etat: dict) -> None:
    """Rapport markdown reecrit apres CHAQUE cellule : lisible meme si la nuit est coupee."""
    L = []
    A = L.append
    A("# BATCH NUIT 2026-08-21 -- faire trouver a la graine 42 ce que la 77 trouve")
    A("")
    A(f"- composant : **r75x2**, 2 nm, `deep`, graine **42** — exclusivement")
    A(f"- lance : {etat['debut']} · echeance : {etat['echeance']}")
    A(f"- commit de l'instrument : `{etat.get('commit', '?')}`")
    A(f"- machine : {etat.get('machine', '?')}")
    A("")
    A("## Porte C1 — l'instrument est-il inerte ?")
    A("")
    if etat.get("c1") is None:
        A("_cellule 1 non terminee._")
    elif etat["c1"]["ok"]:
        A("🟢 **PASSE.** La cellule de reference reproduit "
          "`1617 strategies · 0 deposable · crash_min 100,00 % · ELITE 0`. "
          "L'instrumentation `[ELITE-WL]` est donc bien de la journalisation pure, "
          "et la nuit est interpretable.")
    else:
        A("🔴🔴 **ECHOUE — TOUTE LA NUIT EST A JETER.**")
        A("")
        A(f"```\n{etat['c1']['ecarts']}\n```")
        A("")
        A("L'instrument a fui dans le calcul. Aucun chiffre ci-dessous ne doit etre lu, "
          "et surtout pas publie. Le batch s'est arrete.")
    A("")
    if etat.get("decision"):
        A("## La decision prise apres la cellule 1")
        A("")
        A(f"Ordre retenu : **{' → '.join(etat['decision']['ordre'])}**")
        A("")
        A(f"Motif : {etat['decision']['motif']}")
        A("")
    A("## Les cellules")
    A("")
    A("| cellule | ce qu'elle change | durée | strat. | **déposables** | crash min | ELITE | "
      "**meilleur SEEL** |")
    A("|---|---|---|---|---|---|---|---|")
    for c in etat["cellules"]:
        r = c.get("resume") or {}
        quoi = CELLULES.get(c["cellule"], ("réglages d'origine", ""))[0] if c["cellule"] != "base" \
            else "réglages d'origine (référence)"
        seel = r.get("meilleur_seel_deposable")
        seel_s = f"**{seel:.4f}**" if seel is not None else "—"
        cm = r.get("crash_min")
        cm_s = f"{100 * cm:.2f} %" if cm is not None else "—"
        A(f"| `{c['cellule']}` | {quoi} | {c['duree_min']:.0f} min | {r.get('n_strats', '—')} | "
          f"**{r.get('n_deposables', '—')}** | {cm_s} | {r.get('n_elite', '—')} | {seel_s} |")
    A("")
    A("Cible : **SEEL 0,5692**, le meilleur que la graine 77 atteigne sur ce composant "
      "(547 deposables, crash 1,33 %).")
    A("")
    for c in etat["cellules"]:
        A(f"### `{c['cellule']}` — {c['duree_min']:.0f} min, code {c['code']}")
        A("")
        if c.get("motif"):
            A(f"🔴 {c['motif']}")
            A("")
        if c.get("resume_erreur"):
            A(f"🔴 {c['resume_erreur']}")
            A("")
        A(f"- journal : `{c['journal']}` ({c['lignes_journal']} lignes, **complet**)")
        r = c.get("resume") or {}
        if r:
            A(f"- artefact : `{r.get('artefact')}`")
            A(f"- profondeur consignee : `{r.get('profondeur')}`")
            ov = (r.get("config") or {}).get("overrides")
            A(f"- surcharges consignees : `{ov}`")
        cpt = c.get("compteurs") or {}
        if cpt.get("engendrees"):
            A(f"- compteurs ELITE cumules : engendrees **{cpt['engendrees']}**, "
              f"retenues **{cpt['retenues']}**, rejets halving {cpt['halving']}, "
              f"RMSE {cpt['full_rmse']}, plantage {cpt['score_non_fini']}")
        wl = c.get("elite_wl") or {}
        if not wl.get("absent") and wl.get("rounds"):
            A(f"- rounds ELITE instrumentes : {wl['rounds']} · sorties : {wl.get('sorties')}")
            for quoi, h in (wl.get("histogrammes") or {}).items():
                top = sorted(h.items(), key=lambda kv: -kv[1])[:12]
                if top:
                    A(f"  - `{quoi}` : " + " ".join(f"{k}:{v}" for k, v in top))
        A("")
    if etat.get("sautees"):
        A("## 🔴 Cellules SAUTEES — dit, jamais tu")
        A("")
        for nom, motif in etat["sautees"]:
            A(f"- `{nom}` : {motif}")
        A("")
    A("## ⚠️ Ce que ce batch ne pouvait pas faire")
    A("")
    A("- **Le levier de 👤 — relacher bruit et derive — n'a PAS tourne.** Il change le monde "
      "ou vivent les candidates, donc tout ce qu'il trouve doit etre re-juge AU NOMINAL ; "
      "et le juge au nominal (`probe_renoter.py`) est en panne, cause non localisee. "
      "Un resultat de cette forme aurait ete inexploitable au matin. C'est un arbitrage, "
      "pas un oubli.")
    A("- Aucune conclusion hors `r75x2` a 2 nm en `deep`, graine 42.")
    A("- Aucun commit. Aucun artefact ecrase.")
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    heures = float(sys.argv[1]) if len(sys.argv) > 1 else 9.5
    t_debut = datetime.now()
    echeance = t_debut + timedelta(hours=heures)

    stamp = f"{t_debut:%Y%m%d_%H%M%S}"
    jdir = ROOT / "reports" / f"batch_seed42_{stamp}"
    jdir.mkdir(parents=True, exist_ok=True)
    rapport = ROOT / "reports" / f"BATCH_seed42_{stamp}.md"

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT),
                                capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        commit = "?"

    etat = {
        "debut": f"{t_debut:%Y-%m-%d %H:%M}",
        "echeance": f"{echeance:%Y-%m-%d %H:%M}",
        "commit": commit,
        "machine": f"{os.cpu_count()} coeurs logiques",
        "cellules": [], "sautees": [], "c1": None, "decision": None,
    }
    _log(f"BATCH -- {heures:g} h, echeance {echeance:%H:%M}. Rapport : {rapport.name}")
    ecrire_rapport(rapport, etat)

    # ── Cellule 1 : la reference, et la porte C1 ────────────────────────────
    c1 = lancer("base", "", "", jdir)
    etat["cellules"].append(c1)
    if "resume" not in c1:
        etat["c1"] = {"ok": False, "ecarts": c1.get("resume_erreur", "pas de resume")}
        ecrire_rapport(rapport, etat)
        _log("🔴 la cellule de reference n'a pas produit d'artefact. Arret.")
        return 1
    ok, ecarts = porte_c1(c1["resume"])
    etat["c1"] = {"ok": ok, "ecarts": ecarts}
    ecrire_rapport(rapport, etat)
    if not ok:
        _log(f"🔴🔴 PORTE C1 ECHOUEE : {ecarts}. Arret -- mieux vaut perdre la nuit que "
             f"rapporter des chiffres faux.")
        return 1
    _log("🟢 porte C1 passee.")

    # ── Decision ────────────────────────────────────────────────────────────
    ordre, motif = decider_ordre(c1)
    etat["decision"] = {"ordre": ordre, "motif": motif}
    ecrire_rapport(rapport, etat)
    _log(f"decision : {' -> '.join(ordre)} | {motif}")

    # ── Les cellules suivantes, tant que le temps le permet ────────────────
    for nom in ordre:
        reste = (echeance - datetime.now()).total_seconds() / 60.0
        if reste < RESERVE_MIN:
            etat["sautees"].append(
                (nom, f"il restait {reste:.0f} min et une cellule en demande au moins "
                      f"{RESERVE_MIN} (durees mesurees : 107 a 176 min). Non lancee plutot "
                      f"que tronquee.")
            )
            ecrire_rapport(rapport, etat)
            _log(f"SAUTEE {nom} : {reste:.0f} min de reste.")
            continue
        ov, _quoi = CELLULES[nom]
        c = lancer(nom, ov, nom, jdir)
        etat["cellules"].append(c)
        ecrire_rapport(rapport, etat)

    _log(f"BATCH termine. Rapport : {rapport.relative_to(ROOT)}")
    print(f"\nRAPPORT={rapport.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
