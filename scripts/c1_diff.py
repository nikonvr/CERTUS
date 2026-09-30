"""LA PREUVE DE C1 : LE CHEMIN INACTIF REND LES MEMES BITS QU'AVANT.

    python scripts\\c1_diff.py HEAD                  # l'arbre de travail contre le dernier commit
    python scripts\\c1_diff.py 78fda46 --tete HEAD   # deux commits
    python scripts\\c1_diff.py HEAD --corpus normal  # un seul corpus
    python scripts\\c1_diff.py DOSSIER_A --tete DOSSIER_B

🔴 POURQUOI UN HARNAIS. `CLAUDE.md` section 5, C1 : « tout nouveau parametre est inactif par defaut,
et le chemin inactif rend exactement les memes bits qu'avant ». Les tests ne le prouvent pas (« les
tests ne prouvent pas l'identite numerique : il faut le bit »), le banc non plus : **une
recompilation decale les derniers chiffres** (2,8e-11, reproductible). Ce harnais existait dans
`CLAUDE.md` comme « n'existe pas encore » ; il est ici.

🔑 COMMENT. `git archive` exporte la base dans un dossier temporaire (rien n'est touche dans le
depot, pas de worktree) ; un corpus FIXE, a graine fixe, appelle les points d'entree du calcul
dans un interprete NEUF par arbre, chacun avec son propre cache Numba VIERGE, les deux en
parallele ; les tableaux sont compares sur leurs BITS (`uint64`), pas sur une tolerance. Un signe de
zero, une valeur `NaN` differente, un dernier chiffre : tout compte. Le rapport dit, par point
d'entree, combien de tableaux different et de combien d'ulp.

📏 Pourquoi deux caches vierges : mesure le 2026-09-30, une compilation a froid et un rechargement
du cache different de 3,5e-18 sur 89 tableaux de gradient, sur l'ancien code comme sur le nouveau.
Comparer un arbre compile a froid a un arbre recharge ferait un ecart qui n'est pas celui du code.
Deux compilations a froid, dans deux processus, rendent les memes bits (verifie : `selftest`).

⚠️ Ce que le harnais ne dit PAS : il compare les points d'entree du corpus, sur ses cas. Un chemin
que le corpus n'appelle pas n'est pas prouve. Ajouter un point d'entree, c'est ajouter une fonction
de corpus (`CORPUS`) et monter `VERSION_CORPUS` (le cache de la base en depend).

Le code de sortie : 0 identiques, 1 des bits different (ou un cote ne sait pas faire ce que l'autre
fait), 2 le harnais lui-meme a echoue.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

#: A monter a chaque changement du corpus : il fait partie de la cle du cache de la base.
VERSION_CORPUS = 2

#: Ce qu'on exporte d'une revision : le paquet de calcul et ses voisins, pas `reports/` (592 Mo).
PAQUETS = ("certus", "certus_physics")


# =============================================================================
# Le corpus : appelé dans l'interprete de chaque arbre
# =============================================================================


class Enregistreur:
    """Ce qu'un arbre rend, par cle `entree#cas#k`, et ce qu'il ne sait pas faire."""

    def __init__(self) -> None:
        self.tableaux: dict[str, np.ndarray] = {}
        self.erreurs: dict[str, str] = {}

    def poser(self, cle: str, valeur: Any) -> None:
        self.tableaux[cle] = np.ascontiguousarray(np.asarray(valeur)).copy()

    def resoudre(self, entree: str, *chemins: str) -> Any:
        """La premiere fonction `module:nom` qui s'importe ; sinon l'entree est dite absente."""
        import importlib

        derniere = ""
        for chemin in chemins:
            module, nom = chemin.split(":")
            try:
                return getattr(importlib.import_module(module), nom)
            except (ImportError, AttributeError) as exc:
                derniere = f"{type(exc).__name__}: {str(exc)[:100]}"
        self.erreurs[entree] = f"absent ({derniere})"
        return None

    def appeler(self, entree: str, cas: int, fonction: Any, *args: Any) -> None:
        if fonction is None:
            return
        try:
            sortie = fonction(*args)
        except Exception as exc:  # noqa: BLE001 - ce qu'un arbre refuse est une mesure, pas un accident
            self.erreurs[f"{entree}#{cas:03d}"] = f"{type(exc).__name__}: {str(exc)[:100]}"
            return
        for k, tableau in enumerate(sortie if isinstance(sortie, tuple) else (sortie,)):
            self.poser(f"{entree}#{cas:03d}#{k}", tableau)


def _pile(rng: np.random.Generator, dissipative: bool):
    """Un empilement au hasard : (n couches, d, n arriere, d arriere, longueurs d'onde, substrat)."""
    n_couches = int(rng.integers(1, 9))
    n_arriere = int(rng.integers(0, 4))
    m = int(rng.integers(3, 9))
    wls = np.sort(rng.uniform(380, 1600, m))
    perte = rng.uniform(0, 0.02, (m, n_couches)) * (rng.random((m, n_couches)) < 0.3)
    nl = (rng.uniform(1.3, 3.2, (m, n_couches)) - 1j * perte).astype(np.complex128)
    nb = rng.uniform(1.3, 3.2, (m, n_arriere)).astype(np.complex128)
    d = rng.uniform(10, 260, n_couches)
    db = rng.uniform(10, 260, n_arriere)
    ns = rng.uniform(1.4, 3.6, m) + 0j
    if dissipative:  # n = n' - ik, k > 0 : le substrat absorbe
        ns = ns - 1j * 10.0 ** rng.uniform(-6, -1, m)
    return nl, d, nb, db, wls, ns.astype(np.complex128)


def corpus_normal(rec: Enregistreur) -> None:
    """Incidence normale : spectres, face arriere, cout de DESIGN, gradient ; substrat reel PUIS absorbant."""
    tm = "certus.physics.certus_tmm_matrix"
    f_fused = rec.resoudre("normal.fused", f"{tm}:calculate_RT_with_backside_fused")
    f_noback = rec.resoudre("normal.noback", f"{tm}:calculate_RT_no_backside")
    f_vecreal = rec.resoudre("normal.vecreal", f"{tm}:calculate_RT_vectorized_real")
    f_full = rec.resoudre("normal.fullexact", f"{tm}:calc_spectrum_full_exact")
    f_generic = rec.resoudre("normal.generic", "certus.physics.certus_tmm_backside:_apply_exact_backside_generic")
    f_comb = rec.resoudre("normal.combination", "certus.physics.certus_tmm_backside:apply_exact_backside_combination")
    f_rtrback = rec.resoudre(
        "normal.rtrback", "certus.physics.certus_opt_tmm:calculate_RTRback_incoherent_vectorized"
    )
    f_cost = rec.resoudre("normal.cost", "certus.physics.gradient_utils:cost_numba_fast")
    f_grad = rec.resoudre("normal.gradall", "certus.physics.gradient_oblique:compute_gradient_all_layers_analytic")

    rng = np.random.default_rng(20260930)
    for cas in range(60):
        for suffixe, dissipative in (("", False), ("_abs", True)):
            nl, d, nb, db, wls, ns = _pile(rng, dissipative)
            m, n_arriere = len(wls), len(db)
            cibles, poids = rng.uniform(0, 1, m), rng.uniform(0.2, 1, m)
            var = np.arange(len(d), dtype=np.int64)
            tirage = rng.uniform(0, 1, m)
            rec.appeler("normal.fused" + suffixe, cas, f_fused, d, nl, ns, wls)
            rec.appeler("normal.noback" + suffixe, cas, f_noback, d, nl, ns, wls)
            for avec in (True, False):
                rec.appeler(f"normal.vecreal{int(avec)}" + suffixe, cas, f_vecreal, d, nl, ns, wls, avec)
            try:
                rf, tf = f_noback(d, nl, ns, wls) if f_noback else (None, None)
            except Exception:  # noqa: BLE001 - deja dit par l'appel ci-dessus
                rf = tf = None
            if rf is not None:
                rec.appeler("normal.generic" + suffixe, cas, f_generic, rf, tf, d, nl, ns, wls)
                rec.appeler("normal.combination" + suffixe, cas, f_comb, rf, tf, tirage, ns)
            rec.appeler("normal.rtrback" + suffixe, cas, f_rtrback, d, nl, ns, wls)
            if n_arriere:
                rec.appeler("normal.fullexact" + suffixe, cas, f_full, wls, d, nl, db, nb, ns)
            for avec in (True, False):
                nbk = nb if (avec and n_arriere) else np.zeros((m, 0), dtype=np.complex128)
                dbk = db if (avec and n_arriere) else np.zeros(0)
                retour = bool(avec and n_arriere)
                rec.appeler(f"normal.cost{int(avec)}" + suffixe, cas, f_cost, d, nl, ns, wls, cibles, poids, 1.0, retour, nbk, dbk)
                rec.appeler(
                    f"normal.gradall{int(avec)}" + suffixe, cas, f_grad, d, nl, ns, wls, cibles, poids, 1.0, retour, nbk, dbk, var
                )


def corpus_oblique(rec: Enregistreur) -> None:
    """Incidence oblique, s et p : spectres, face arriere, gradients analytiques ; substrat reel PUIS absorbant."""
    to = "certus.physics.certus_tmm_oblique"
    go = "certus.physics.gradient_oblique"
    f_spec = rec.resoudre("oblique.spectrum", f"{to}:calc_spectrum_oblique_vectorized")
    f_back = rec.resoudre("oblique.backside", f"{to}:calc_spectrum_oblique_backside_vectorized")
    f_full = rec.resoudre("oblique.full", f"{to}:calc_spectrum_full_oblique_exact")
    f_contrib = rec.resoudre("oblique.contrib", f"{go}:compute_oblique_gradient_contrib_analytic")
    f_rtg = rec.resoudre("oblique.rtgrads", f"{go}:compute_oblique_rt_and_grads_analytic")
    f_bundle = rec.resoudre("oblique.bundle", f"{go}:compute_oblique_backside_bundle_analytic")

    rng = np.random.default_rng(20260929)
    for cas in range(60):
        for suffixe, dissipative in (("", False), ("_abs", True)):
            nl, d, nb, db, wls, ns = _pile(rng, dissipative)
            m, n_arriere = len(wls), len(db)
            angle = float(rng.choice([8, 20, 35, 50, 65, 78]))
            pol = str(rng.choice(["s", "p"]))
            est_s = pol == "s"
            cibles, poids = rng.uniform(0, 1, m), rng.uniform(0.2, 1, m)
            var = np.arange(len(d), dtype=np.int64)
            rec.appeler("oblique.spectrum" + suffixe, cas, f_spec, wls, nl, d, ns, angle, pol)
            rec.appeler("oblique.backside" + suffixe, cas, f_back, wls, nl, d, ns, angle, pol)
            rec.appeler("oblique.full" + suffixe, cas, f_full, wls, d, nl, db, nb, ns, angle, est_s)
            rec.appeler(
                "oblique.contrib" + suffixe, cas, f_contrib, d, nl, ns, wls, cibles, poids, angle, est_s, bool(cas % 2), var
            )
            for inverse in (False, True):
                rec.appeler(f"oblique.rtgrads{int(inverse)}" + suffixe, cas, f_rtg, d, nl, ns, wls, var, angle, est_s, inverse)
            rec.appeler(
                "oblique.bundle" + suffixe, cas, f_bundle, d, nl, ns, wls, var, angle, est_s,
                nb if n_arriere else None, db if n_arriere else None,
            )  # fmt: skip


def corpus_strat(rec: Enregistreur) -> None:
    """La simulation de croissance de STRAT : le noyau, ses aides, la propagation par tirage, la croissance detaillee.

    Les parametres de chaque appel sont tires au hasard (graine fixe) parmi les valeurs qui font emprunter au noyau
    ses branches : POEM ou repli absolu, mode non monotone, hysteresis, bruit de lecture, derive photometrique,
    lissage, palier de debit, profil de fente, temoin change en cours de route, balayage adaptatif, grille de la
    machine sans lissage, couches deja posees au debit. Un noyau de 1 190 lignes ne se caracterise pas cas par cas.
    """
    g = "certus.physics.certus_strat_growth"
    f_grow = rec.resoudre("strat.growth", f"{g}:simulate_growth_kernel")
    f_states = rec.resoudre("strat.states", f"{g}:update_run_states_kernel")
    f_tp = rec.resoudre("strat.turning", f"{g}:detect_turning_points")
    f_next = rec.resoudre("strat.next", f"{g}:next_turning_point_after")
    f_margin = rec.resoudre("strat.margins", f"{g}:turning_point_margins")
    f_scan = rec.resoudre("strat.scan", f"{g}:layer_scan_coeffs")
    f_profile = rec.resoudre("strat.tprofile", f"{g}:compute_T_front_profile")
    f_detail = rec.resoudre("strat.detailed", f"{g}:calculate_detailed_growth")
    nodes = 8  # SLIT_PROFILE_NODES : le nombre exact est celui du noyau, mais toute largeur >= 2 est une entree valide

    rng = np.random.default_rng(20260930)
    nominal = np.array([53.19, 85.62, 53.19, 85.62, 53.19, 85.62, 53.19, 85.62])
    n_h, n_l, n_sub = 2.35 + 0j, 1.46 + 0j, 1.52 + 0j

    for cas in range(400):
        i_layer = int(rng.integers(1, len(nominal)))
        prev = nominal[:i_layer] * (1.0 + rng.normal(0.0, 0.01, i_layer))
        wl = float(rng.choice([500.0, 540.0, 600.0, 650.0]))
        profiles = rng.normal(0.0, 1e-3, (len(nominal), nodes)) if rng.random() < 0.3 else None
        est_taux = bool(rng.random() < 0.25)
        # Les quatre derniers parametres du noyau : temoin change en cours de route, balayage adaptatif, grille de la
        # machine sans lissage, couches deja posees au debit. Sans eux, la moitie des branches ne serait jamais lue.
        base_layer = int(rng.integers(0, i_layer + 1)) if rng.random() < 0.3 else 0
        drapeaux = (rng.random(len(nominal)) < 0.4) if est_taux and rng.random() < 0.5 else None
        adaptatif = bool(rng.random() < 0.3)
        lissage = int(rng.choice([1, 3]))
        grille = float(rng.choice([0.0, 0.0, 0.125, 0.25]))
        if adaptatif:
            # 🔴 Le balayage adaptatif AVEC la grille fine lit hors du balayage grossier : le re-echantillonnage suppose 64
            # points sur trois fois l'epaisseur, le balayage adaptatif en a moins sur une autre fenetre. Le noyau rend alors
            # une `margin_missed` differente d'un lancement a l'autre (mesure le 2026-09-30, D54 : 6 cas sur 87 du corpus,
            # jusqu'a 20 % d'ecart). Un corpus dont l'arbre ne se retrouve pas lui-meme ne prouve rien : on l'evite.
            lissage, grille = 1, 0.0
        rec.appeler(
            "strat.growth", cas, f_grow, nominal, i_layer, prev, wl, n_h, n_l, n_sub,
            float(rng.choice([1.0, 0.98])), float(rng.choice([0.0, 0.3, -0.3])), float(rng.choice([1.0, 2.0])),
            int(rng.integers(0, 2)), int(rng.choice([-1, 1])), float(rng.choice([0.0, 1e-3])), int(rng.integers(0, 5)),
            int(rng.integers(0, 3)), float(rng.choice([0.0, 0.01])), float(rng.choice([1.0, 0.98])),
            float(rng.choice([0.0, 0.01])), float(rng.choice([0.0, 0.5])), bool(rng.random() < 0.7),
            lissage, 2.30 if est_taux else -1.0, 1.45 if est_taux else -1.0, est_taux, profiles,
            base_layer, adaptatif, grille, drapeaux,
        )  # fmt: skip

    for cas in range(20):
        i_layer = int(rng.integers(1, len(nominal)))
        n_runs = int(rng.integers(2, 6))
        history = np.tile(nominal[:i_layer], (n_runs, 1)) * (1.0 + rng.normal(0.0, 0.01, (n_runs, i_layer)))
        couloir = float(rng.choice([0.0, 0.005]))  # l'incertitude d'indice : la bande de longueurs d'onde ne compte qu'avec elle
        rec.appeler(
            "strat.states", cas, f_states, nominal, i_layer, history, float(rng.choice([500.0, 540.0, 600.0])),
            n_h, n_l, n_sub, 1.0, rng.uniform(-0.3, 0.3, n_runs), 2.0, int(rng.integers(0, 2)), int(rng.choice([-1, 1])),
            float(rng.choice([0.0, 1e-3])), int(rng.integers(0, 5)), float(rng.choice([0.0, 0.01])),
            float(rng.choice([0.0, 0.02])), float(rng.choice([0.0, 0.02])), float(rng.choice([0.0, 0.5])),
            int(rng.integers(0, 5)), bool(rng.random() < 0.7), int(rng.choice([1, 3])), couloir,
            int(rng.integers(0, 5)), 450.0 if couloir else 0.0, 650.0 if couloir else 0.0,
            rng.normal(0.0, 1e-3, (len(nominal), nodes)) if rng.random() < 0.3 else None,
        )  # fmt: skip

    for cas in range(60):  # signaux de controle : sommes de sinus, bruit ou pas, tous les seuils
        n = int(rng.integers(20, 200))
        ts = np.abs(np.sin(np.linspace(0.0, rng.uniform(2.0, 30.0), n))) + rng.normal(0.0, rng.choice([0.0, 1e-4, 1e-2]), n)
        hysteresis = float(rng.choice([0.0, 0.005, 0.05]))
        idx_stop = int(rng.integers(0, n))
        rec.appeler("strat.turning", cas, f_tp, ts, n, idx_stop, bool(rng.random() < 0.5), hysteresis)
        rec.appeler("strat.next", cas, f_next, ts, n, int(rng.integers(0, n)), hysteresis)
        rec.appeler("strat.margins", cas, f_margin, ts, n, hysteresis)

    for cas in range(30):  # coefficients de balayage et profils de T
        matrix = np.eye(2, dtype=np.complex128)
        n_layer = complex(rng.uniform(1.3, 2.4), 0.0)
        wl = float(rng.uniform(400.0, 900.0))
        for _ in range(int(rng.integers(1, 6))):
            n_i, d_i = rng.uniform(1.3, 2.4), rng.uniform(20.0, 150.0)
            phi = 2 * np.pi * n_i * d_i / wl
            layer = np.array([[np.cos(phi), 1j * np.sin(phi) / n_i], [1j * n_i * np.sin(phi), np.cos(phi)]])
            matrix = layer @ matrix
        rec.appeler("strat.scan", cas, f_scan, matrix[0, 0], matrix[0, 1], matrix[1, 0], matrix[1, 1], n_layer, n_sub)
        rec.appeler(
            "strat.tprofile", cas, f_profile, wl, n_layer, n_sub, matrix[0, 0], matrix[0, 1], matrix[1, 0], matrix[1, 1],
            np.linspace(0.0, 200.0, 41),
        )  # fmt: skip

    rec.appeler(
        "strat.detailed", 0, f_detail, len(nominal), nominal, np.full(len(nominal), 540.0),
        np.full(len(nominal), n_h), np.full(len(nominal), n_l), np.full(len(nominal), n_sub),
        np.full(len(nominal), 20, dtype=np.int64),
    )  # fmt: skip


def corpus_selftest(rec: Enregistreur) -> None:
    """Un seul noyau, `compute_RT_from_matrix` : de quoi prouver que le harnais voit un ulp, en quelques secondes."""
    f = rec.resoudre("selftest", "certus.physics.certus_opt_tmm:compute_RT_from_matrix")
    if f is None:
        return
    rng = np.random.default_rng(7)
    reflexions, transmissions = [], []
    for _ in range(300):
        m = rng.normal(size=4) + 1j * rng.normal(size=4)
        n_inc = complex(rng.uniform(1.0, 1.6), 0.0)
        n_sortie = complex(rng.uniform(1.3, 3.5), -rng.uniform(0, 0.5))
        r, t = f(m[0], m[1], m[2], m[3], n_inc, n_sortie)
        reflexions.append(r)
        transmissions.append(t)
    rec.poser("selftest#000#0", np.array(reflexions))
    rec.poser("selftest#000#1", np.array(transmissions))


CORPUS = {"normal": corpus_normal, "oblique": corpus_oblique, "strat": corpus_strat, "selftest": corpus_selftest}
CORPUS_PAR_DEFAUT = ("normal", "oblique", "strat")


def ouvrier(arbre: Path, sortie: Path, noms: list[str]) -> int:
    """Dans l'interprete d'un arbre : importe SON `certus`, joue le corpus, ecrit les tableaux et les erreurs."""
    import warnings

    warnings.simplefilter("ignore")
    sys.path.insert(0, str(arbre))
    import certus

    # `certus` est un paquet sans __init__ : il n'a pas de __file__, seulement des chemins.
    chemins = [Path(c).resolve() for c in getattr(certus, "__path__", [])]
    if not any(c.is_relative_to(arbre.resolve()) for c in chemins):
        print(f"OUVRIER_KO certus vient de {chemins}, pas de {arbre}", flush=True)
        return 2
    rec = Enregistreur()
    depart = time.perf_counter()
    for nom in noms:
        CORPUS[nom](rec)
    np.savez(sortie, **rec.tableaux)
    meta = {
        "erreurs": rec.erreurs,
        "tableaux": len(rec.tableaux),
        "secondes": round(time.perf_counter() - depart, 1),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
    }
    try:
        import numba

        meta["numba"] = numba.__version__
        meta["fils"] = numba.config.NUMBA_NUM_THREADS
    except ImportError:
        pass
    sortie.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"OUVRIER_OK {len(rec.tableaux)} tableaux, {len(rec.erreurs)} refus, {meta['secondes']} s", flush=True)
    return 0


# =============================================================================
# La comparaison : les bits
# =============================================================================


def _bits(a: np.ndarray) -> np.ndarray:
    a = np.ascontiguousarray(a)
    if a.dtype in (np.float64, np.complex128):
        return a.view(np.uint64)
    if a.dtype in (np.float32, np.complex64):
        return a.view(np.uint32)
    return a


def _ordre(a: np.ndarray) -> np.ndarray:
    """Les flottants remis dans l'ordre des entiers (int64) : la distance entre deux d'entre eux est leur ecart en ulp.

    Les valeurs restent des ENTIERS : en float64 elles perdraient leurs 10 derniers bits, et un ecart d'un ulp
    deviendrait 0 ou 1 024 (mesure du 2026-09-30, premiere version du harnais : « 512 ulp » pour un ulp plante).
    """
    x = np.ascontiguousarray(a, dtype=np.float64).view(np.int64)
    return np.where(x >= 0, x, -(x & np.int64(0x7FFFFFFFFFFFFFFF)))


def _ecart_en_ulp(a: np.ndarray, b: np.ndarray) -> float:
    """Le plus grand ecart, en ulp, entre deux tableaux de flottants : exact tant qu'il tient dans un int64."""
    oa, ob = _ordre(a), _ordre(b)
    approche = np.abs(oa.astype(np.float64) - ob.astype(np.float64))
    exact = np.abs(oa - ob)  # deborde seulement la ou `approche` est enorme
    return float(np.where(approche >= 2.0**62, approche, exact.astype(np.float64)).max())


def comparer_tableaux(a: np.ndarray, b: np.ndarray) -> dict[str, Any] | None:
    """None si `a` et `b` ont les memes bits ; sinon ce qui differe : forme, ulp, ecart relatif."""
    if a.shape != b.shape or a.dtype != b.dtype:
        return {"forme": f"{a.shape}/{a.dtype} contre {b.shape}/{b.dtype}", "ulp": float("inf"), "rel": float("inf")}
    if np.array_equal(_bits(a), _bits(b)):
        return None
    if a.dtype.kind in "fc":
        reels_a = a.view(np.float64).ravel() if a.dtype.kind == "c" else a.astype(np.float64).ravel()
        reels_b = b.view(np.float64).ravel() if b.dtype.kind == "c" else b.astype(np.float64).ravel()
        autre = _bits(a).ravel() != _bits(b).ravel()
        if np.isnan(reels_a[autre]).any() or np.isnan(reels_b[autre]).any():
            return {"ulp": float("inf"), "rel": float("inf"), "nan": True}
        ulp = _ecart_en_ulp(reels_a[autre], reels_b[autre])
        ecart = np.abs(reels_a[autre] - reels_b[autre])
        echelle = np.maximum(np.maximum(np.abs(reels_a[autre]), np.abs(reels_b[autre])), np.finfo(np.float64).tiny)
        return {"ulp": ulp, "rel": float(np.max(ecart / echelle)), "positions": int(autre.sum())}
    return {"ulp": float("inf"), "rel": float("inf"), "positions": int((a != b).sum())}


def comparer(base: dict[str, np.ndarray], tete: dict[str, np.ndarray], err_base: dict[str, str], err_tete: dict[str, str]):
    """Les lignes par point d'entree de la comparaison bit a bit de deux sorties de corpus."""
    par_entree: dict[str, dict[str, Any]] = {}

    def ligne(entree: str) -> dict[str, Any]:
        return par_entree.setdefault(entree, {"tableaux": 0, "differents": 0, "ulp": 0.0, "rel": 0.0, "exemples": [], "refus": 0})

    for cle in sorted(set(base) | set(tete)):
        entree = cle.split("#")[0]
        r = ligne(entree)
        r["tableaux"] += 1
        if cle not in base or cle not in tete:
            r["differents"] += 1
            r["exemples"].append(f"{cle}: seulement {'a la base' if cle in base else 'a la tete'}")
            r["ulp"] = float("inf")
            continue
        diff = comparer_tableaux(base[cle], tete[cle])
        if diff is not None:
            r["differents"] += 1
            r["ulp"] = max(r["ulp"], diff["ulp"])
            r["rel"] = max(r["rel"], diff["rel"])
            if len(r["exemples"]) < 3:
                r["exemples"].append(f"{cle}: {diff['ulp']:.0f} ulp, relatif {diff['rel']:.2e}")
    for cle in sorted(set(err_base) | set(err_tete)):
        if err_base.get(cle) == err_tete.get(cle):
            continue  # les deux refusent pareil : rien ne differe
        r = ligne(cle.split("#")[0])
        r["refus"] += 1
        r["differents"] += 1
        r["exemples"].append(f"{cle}: base {err_base.get(cle, 'repond')} ; tete {err_tete.get(cle, 'repond')}")
    return par_entree


def _format_ulp(ulp: float) -> str:
    """Un entier tant qu'il se lit (jusqu'a un million d'ulp), puis en puissance de dix."""
    if ulp == float("inf"):
        return "inf"
    return f"{ulp:.0f}" if ulp < 1e6 else f"{ulp:.1e}"


def rendre(par_entree: dict[str, dict[str, Any]], base: str, tete: str, secondes: float) -> str:
    lignes = [f"C1 - bits compares : base {base}  contre  tete {tete}  ({secondes:.0f} s)"]
    lignes.append(f"{'point d entree':<26}{'tableaux':>9}{'differents':>11}{'ulp max':>10}{'relatif max':>13}")
    lignes.append("-" * 69)
    for entree, r in sorted(par_entree.items()):
        ulp = "-" if not r["differents"] else _format_ulp(r["ulp"])
        rel = "-" if not r["differents"] else f"{r['rel']:.2e}"
        lignes.append(f"{entree:<26}{r['tableaux']:>9}{r['differents']:>11}{ulp:>10}{rel:>13}")
    total = sum(r["tableaux"] for r in par_entree.values())
    differents = sum(r["differents"] for r in par_entree.values())
    if differents:
        lignes.append("")
        for entree, r in sorted(par_entree.items()):
            for exemple in r["exemples"]:
                lignes.append(f"  {exemple}")
        lignes.append(f"\nC1 VIOLE : {differents} differences sur {total} tableaux, dans {sum(1 for r in par_entree.values() if r['differents'])} points d'entree")
    else:
        lignes.append(f"\nC1 TENU : {total} tableaux, tous identiques au bit")
    return "\n".join(lignes)


# =============================================================================
# Les arbres
# =============================================================================


def _git(racine: Path, *args: str) -> bytes:
    return subprocess.run(["git", "--no-optional-locks", *args], cwd=racine, capture_output=True, check=True, timeout=120).stdout


def preparer(racine: Path, spec: str, dest: Path) -> tuple[Path, str, str | None]:
    """(dossier de l'arbre, son nom, son SHA s'il vient de git). `.` est l'arbre de travail, modifications comprises."""
    if spec == ".":
        return racine, "arbre de travail", None
    dossier = Path(spec)
    if dossier.is_dir() and (dossier / "certus").is_dir():
        return dossier.resolve(), str(dossier), None
    sha = _git(racine, "rev-parse", "--verify", f"{spec}^{{commit}}").decode().strip()
    presents = set(_git(racine, "ls-tree", "--name-only", sha).decode().split("\n"))
    tar = _git(racine, "archive", sha, "--", *[p for p in PAQUETS if p in presents])
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        archive.extractall(dest, filter="data")
    return dest, f"{spec} ({sha[:7]})", sha


def _cle_du_cache(sha: str, noms: list[str], fils: int) -> str:
    import numpy

    try:
        import numba

        version_numba = numba.__version__
    except ImportError:
        version_numba = "?"
    empreinte = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    morceaux = [sha[:12], ",".join(noms), str(fils), sys.version.split()[0], numpy.__version__, version_numba, empreinte]
    return "_".join(morceaux).replace("/", "-")


def _fichier_du_cache(entree: Path, suffixe: str) -> Path:
    """`entree` suivi de `suffixe`. `Path.with_suffix` ne convient pas : la cle contient les points des versions
    (`3.14.7_2.5.3_0.67_<empreinte>`), il remplacerait tout ce qui suit le dernier, empreinte du script comprise, et une base
    calculee par un ancien corpus etait rendue a un corpus plus recent (2026-09-30 : 160 cas « seulement a la tete »).
    """
    return entree.with_name(entree.name + suffixe)


def lancer(arbre: Path, sortie: Path, noms: list[str], fils: int, tmp: Path, nom: str) -> subprocess.Popen:
    env = {k: v for k, v in os.environ.items() if k not in ("NUMBA_DISABLE_JIT", "NUMBA_CPU_NAME", "NUMBA_OPT")}
    env.update(
        NUMBA_CACHE_DIR=str(tmp / f"cache_{nom}"), NUMBA_NUM_THREADS=str(fils), PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1"
    )
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--ouvrier", str(arbre), str(sortie), ",".join(noms)],
        cwd=arbre, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    )  # fmt: skip


def froid_contre_chaud(racine: Path, arbre: str, noms: list[str], fils: int = 4) -> tuple[dict, str, str, float]:
    """Le MEME arbre deux fois, dans un cache commun : a froid (il compile et ecrit), puis a chaud (il relit).

    La mesure du 2026-09-30 (3,5e-18 sur 89 tableaux de gradient) disait qu'un noyau relu du cache ne rend pas
    toujours les bits d'un noyau compile a l'instant. Ici on la refait sur tout le corpus, par point d'entree.
    """
    debut = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="c1_") as temp:
        tmp = Path(temp)
        dossier, nom, _sha = preparer(racine, arbre, tmp / "arbre")
        donnees = {}
        for cote in ("froid", "chaud"):
            sortie = tmp / f"{cote}.npz"
            p = lancer(dossier, sortie, noms, fils, tmp, "commun")  # meme NUMBA_CACHE_DIR les deux fois
            texte, _ = p.communicate(timeout=1800)
            if p.returncode != 0 or "OUVRIER_OK" not in texte:
                raise RuntimeError(f"l'ouvrier {cote} a echoue (code {p.returncode}) :\n{texte[-1500:]}")
            with np.load(sortie) as f:
                donnees[cote] = ({k: f[k] for k in f.files}, json.loads(sortie.with_suffix(".json").read_text(encoding="utf-8"))["erreurs"])
    par_entree = comparer(donnees["froid"][0], donnees["chaud"][0], donnees["froid"][1], donnees["chaud"][1])
    return par_entree, f"{nom}, a froid", f"{nom}, a chaud", time.perf_counter() - debut


def executer(racine: Path, base: str, tete: str, noms: list[str], fils: int = 4, *, cache: bool = True) -> tuple[dict, str, str, float]:
    """Joue le corpus sur la base et sur la tete, en parallele ; rend (points d'entree, nom base, nom tete, secondes)."""
    debut = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="c1_") as temp:
        tmp = Path(temp)
        arbre_base, nom_base, sha_base = preparer(racine, base, tmp / "base")
        arbre_tete, nom_tete, sha_tete = preparer(racine, tete, tmp / "tete")
        dossier_cache = Path(tempfile.gettempdir()) / "certus_c1_cache"
        sorties = {"base": tmp / "base.npz", "tete": tmp / "tete.npz"}
        a_calculer = {"base": (arbre_base, sha_base), "tete": (arbre_tete, sha_tete)}
        depuis_cache = {}
        for cote, (_arbre, sha) in a_calculer.items():
            if cache and sha:
                entree = dossier_cache / _cle_du_cache(sha, noms, fils)
                if _fichier_du_cache(entree, ".npz").exists() and _fichier_du_cache(entree, ".json").exists():
                    depuis_cache[cote] = entree
        processus = {
            cote: lancer(arbre, sorties[cote], noms, fils, tmp, cote)
            for cote, (arbre, _sha) in a_calculer.items()
            if cote not in depuis_cache
        }
        for cote, p in processus.items():
            sortie, _ = p.communicate(timeout=1800)
            if p.returncode != 0 or "OUVRIER_OK" not in sortie:
                raise RuntimeError(f"l'ouvrier de {cote} a echoue (code {p.returncode}) :\n{sortie[-1500:]}")
        donnees = {}
        for cote in ("base", "tete"):
            if cote in depuis_cache:
                npz, meta = _fichier_du_cache(depuis_cache[cote], ".npz"), _fichier_du_cache(depuis_cache[cote], ".json")
            else:
                npz, meta = sorties[cote], sorties[cote].with_suffix(".json")
                sha = a_calculer[cote][1]
                if cache and sha:
                    dossier_cache.mkdir(exist_ok=True)
                    entree = dossier_cache / _cle_du_cache(sha, noms, fils)
                    _fichier_du_cache(entree, ".npz").write_bytes(npz.read_bytes())
                    _fichier_du_cache(entree, ".json").write_bytes(meta.read_bytes())
            with np.load(npz) as f:
                tableaux = {k: f[k] for k in f.files}
            donnees[cote] = (tableaux, json.loads(meta.read_text(encoding="utf-8"))["erreurs"])
    par_entree = comparer(donnees["base"][0], donnees["tete"][0], donnees["base"][1], donnees["tete"][1])
    return par_entree, nom_base, nom_tete, time.perf_counter() - debut


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="C1 : les bits de la tete contre ceux d'une base.")
    p.add_argument("base", nargs="?", help="un commit, une branche, une etiquette, ou un dossier qui contient certus/")
    p.add_argument("--tete", default=".", help="ce qu'on compare a la base (defaut : l'arbre de travail, modifications comprises)")
    p.add_argument("--corpus", default=",".join(CORPUS_PAR_DEFAUT), help=f"parmi {', '.join(CORPUS)}")
    p.add_argument("--fils", type=int, default=4, help="NUMBA_NUM_THREADS des deux cotes (defaut 4)")
    p.add_argument("--sans-cache", action="store_true", help="recalculer meme une base deja calculee")
    p.add_argument(
        "--froid-contre-chaud", action="store_true",
        help="compare la base a elle-meme : compilee a froid, puis relue du cache (ignore --tete)",
    )  # fmt: skip
    p.add_argument("--json", type=Path, help="ecrire le rapport, avec sa provenance (sans ecraser)")
    p.add_argument("--ouvrier", nargs=3, metavar=("ARBRE", "SORTIE", "CORPUS"), help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    if args.ouvrier:
        arbre, sortie, noms = args.ouvrier
        return ouvrier(Path(arbre), Path(sortie), noms.split(","))
    if not args.base:
        p.error("il faut une base : un commit, une branche, une etiquette ou un dossier")
    noms = args.corpus.split(",")
    inconnus = [n for n in noms if n not in CORPUS]
    if inconnus:
        p.error(f"corpus inconnu : {inconnus} (connus : {list(CORPUS)})")
    try:
        if args.froid_contre_chaud:
            par_entree, nom_base, nom_tete, secondes = froid_contre_chaud(ROOT, args.base, noms, args.fils)
        else:
            par_entree, nom_base, nom_tete, secondes = executer(ROOT, args.base, args.tete, noms, args.fils, cache=not args.sans_cache)
    except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
        print(f"C1 : le harnais a echoue : {exc}", file=sys.stderr)
        return 2
    print(rendre(par_entree, nom_base, nom_tete, secondes))
    if args.json:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from _artefact import ecrire_json

        ecrire_json(args.json, {"base": nom_base, "tete": nom_tete, "corpus": noms, "points_d_entree": par_entree})
    return 1 if any(r["differents"] for r in par_entree.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
