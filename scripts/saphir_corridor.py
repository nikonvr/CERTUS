"""CORRIDOR D'INDICE DU SAPHIR, depuis les mesures de la base de depots (2026-10-12).

    python scripts\\saphir_corridor.py <etape> [--sortie DOSSIER] [--sigma-f 0.15]

La question (2026-10-12) : « quel est le vrai indice du saphir ? [...] peut-etre converger vers un corridor d'indice du saphir ? »

Le modele est dans `_saphir_modele.py` : films en spline n / ln k (INDEX SPLINE) + correction dn(lambda) du Sellmeier du rayon ordinaire, commune a
tous les echantillons. Les calculs sont a UN thread par defaut (BLAS compris) : une campagne STRAT tournait pendant ces mesures et un premier
essai a pleins threads a consomme ~11 coeurs pendant une demi-heure (la SVD de `least_squares`). `--threads N` pour les lever.

etapes
  nu            le saphir nu de la seance 24-03 : indice depuis T seul et R seul, deficit de fermeture 1-T-R, fraction p qui reproduirait T et R
  absolu        T et R absolus (nu + 3 films, 1000-3300 nm) : dn libre ou non, polarisation libre ou non ; robustesse sur 17 variantes
  profil        chi2 en fonction du niveau de dn, faisceau non polarise puis polarisation libre sous N(0.5, sigma-f)
  information   ecart-type du niveau en fonction de la largeur a priori de la polarisation
  mwir          les memes ajustements jusqu'a 5200 nm avec l'absorption mesuree du saphir
  rapport       les references NORMALISEES de la base sur saphir : le niveau de dn y est-il determine ? (long)
  propagation   effet du niveau sur n_f et d des films, spectres absolus puis normalises
  synthese      donnees simulees a verite connue : le niveau plante est-il retrouve ?
  corridor      assemble le corridor (CSV, PNG, JSON) selon la regle documentee dans `regle_du_corridor`
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

_ARGS_PRE = argparse.ArgumentParser(add_help=False)
_ARGS_PRE.add_argument("--threads", type=int, default=1)
_THREADS = _ARGS_PRE.parse_known_args()[0].threads
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_var] = str(_THREADS)

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _saphir_modele as sm  # noqa: E402
from _artefact import ecrire_json  # noqa: E402

ROOT = sm.ROOT
FENETRE = (1000.0, 3300.0)  # la ou le saphir est transparent et ou les films de 3 um ne sont pas sous-echantillonnes par le pas de 50 nm


def sortie_par_defaut() -> Path:
    return ROOT / "reports" / "saphir_corridor_2026-10-12"


def references():
    return sm.references_saphir()


def probleme_absolu(lam_min=FENETRE[0], lam_max=FENETRE[1], J=3, poids_r_nu=1.0, utiliser_t=True, utiliser_r=True, noms=("nu", "Nb", "Ta", "Si"),
                    densite=2.5e-4, absorbant=False):
    sk = sm.noeuds_sigma(lam_min, lam_max, J)
    samples = sm.echantillons_absolus(references(), sk, lam_min, lam_max, noms=noms, densite=densite, absorbant=absorbant)
    return sm.ProblemeAbsolu(samples, sk, poids_r_nu=poids_r_nu, utiliser_t=utiliser_t, utiliser_r=utiliser_r), sk


def ajuste_non_polarise(prob, niveau=None, tours=2):
    """Le meilleur ajustement a faisceau non polarise (f = 0.5 exactement) ; `niveau` fixe dn partout, sinon dn est libre."""
    fixed = prob.fixe_polarisation(0.5)
    if niveau is not None:
        fixed.update(prob.fixe_niveau(niveau))
    x = prob.x_start
    for _ in range(tours):
        x, _res = prob.ajuster(x, fixed=fixed)
    return x


# ------------------------------------------------------------------------------------------------------------------------------ nu
def etape_nu():
    lam, t = sm.lire_mesure("24-03-accurate__tnusaphire-2f.csv")
    _l, r = sm.lire_mesure("24-03-accurate__rnu-2f.csv")
    ns = sm.indice_saphir(lam)
    manque = 1 - t - r
    r1_t, r1_r = (1 - t) / (1 + t), r / (2 - r)
    n_t, n_r = (1 + np.sqrt(r1_t)) / (1 - np.sqrt(r1_t)), (1 + np.sqrt(r1_r)) / (1 - np.sqrt(r1_r))
    lay = np.zeros((lam.size, 0), dtype=complex)
    rs, ts = sm.calc_spectrum_oblique_backside_vectorized(lam, lay, np.zeros(0), ns.astype(complex), 8.0, "s", sm.SUBSTRATE_NM)
    rp, tp = sm.calc_spectrum_oblique_backside_vectorized(lam, lay, np.zeros(0), ns.astype(complex), 8.0, "p", sm.SUBSTRATE_NM)
    print("Saphir nu de la seance 24-03 (T et R, 2 faces, 8 deg) ; n = Sellmeier ordinaire ; f = fraction p du faisceau qui reproduirait la mesure")
    print(f"{'lam':>6}{'T %':>8}{'R %':>8}{'1-T-R %':>9}{'n(T)-S':>9}{'n(R)-S':>9}{'f_T':>7}{'f_R':>7}")
    for i in range(0, lam.size, 3):
        if 500 <= lam[i] <= 3600:
            print(f"{lam[i]:6.0f}{100 * t[i]:8.3f}{100 * r[i]:8.3f}{100 * manque[i]:9.3f}{n_t[i] - ns[i]:+9.4f}{n_r[i] - ns[i]:+9.4f}"
                  f"{(t[i] - ts[i]) / (tp[i] - ts[i]):7.2f}{(r[i] - rs[i]) / (rp[i] - rs[i]):7.2f}")
    sortie = {}
    for lo, hi in ((500, 1000), (1000, 2000), (2000, 3000)):
        m = (lam >= lo) & (lam <= hi)
        sortie[f"{lo}-{hi}"] = {"n_T_moins_S": float(np.mean(n_t[m] - ns[m])), "n_R_moins_S": float(np.mean(n_r[m] - ns[m])), "deficit_pct": float(100 * np.mean(manque[m])),
                                "f_T": float(np.mean(((t - ts) / (tp - ts))[m])), "f_R": float(np.mean(((r - rs) / (rp - rs))[m]))}
        print(f"{lo}-{hi} nm : n(T)-S {sortie[f'{lo}-{hi}']['n_T_moins_S']:+.4f}   n(R)-S {sortie[f'{lo}-{hi}']['n_R_moins_S']:+.4f}   "
              f"deficit {sortie[f'{lo}-{hi}']['deficit_pct']:.3f} %   f_T {sortie[f'{lo}-{hi}']['f_T']:.2f}   f_R {sortie[f'{lo}-{hi}']['f_R']:.2f}")
    print("\nFermeture 1-T-R des trois films absolus de la meme seance (900-2400 nm) :")
    for nom, (tf, rf) in sm.FICHIERS_24_03.items():
        if nom == "nu":
            continue
        lt, tt = sm.lire_mesure(f"24-03-accurate__{tf}.csv")
        _lr, rr = sm.lire_mesure(f"24-03-accurate__{rf}.csv")
        m = (lt >= 900) & (lt <= 2400)
        sortie[f"fermeture_{nom}"] = float(100 * np.mean((1 - tt - rr)[m]))
        print(f"   {nom}: 1-T-R moyen {sortie[f'fermeture_{nom}']:.3f} %  (R de {100 * rr[m].min():.1f} a {100 * rr[m].max():.1f} %)")
    return sortie


# ------------------------------------------------------------------------------------------------------------------------- absolu
def niveau_de(prob, x):
    return float(np.mean(prob.dn_of(x)))


def etape_absolu():
    sortie = {}
    for etiquette, poids in (("R du saphir nu utilise", 1.0), ("R du saphir nu NON utilise", 0.0)):
        prob, _ = probleme_absolu(poids_r_nu=poids)
        print(f"=== {etiquette} ===")
        a = ajuste_non_polarise(prob, niveau=0.0)
        b, _ = prob.ajuster(a, fixed={prob.i_dn + j: 0.0 for j in range(prob.J)})
        c = ajuste_non_polarise(prob)
        d, _ = prob.ajuster(b, fixed={})
        for nom, x in (("A  dn = 0, f = 0.5", a), ("B  dn = 0, f_T f_R libres", b), ("C  dn libre, f = 0.5", c), ("D  dn libre, f libres", d)):
            print(f"{nom:<28} chi2 {prob.chi2(x):7.1f}  rms T/R " + " ".join(f"{n}:{100 * t:.2f}/{100 * r:.2f}" for n, t, r in prob.rms(x))
                  + "   dn " + " ".join(f"{v:+.4f}" for v in prob.dn_of(x)) + f"   f_T {x[prob.i_ft]:.2f} f_R {x[prob.i_fr]:.2f}")
        sortie[etiquette] = {"A": prob.chi2(a), "B": prob.chi2(b), "C": prob.chi2(c), "D": prob.chi2(d), "dn_C": [float(v) for v in prob.dn_of(c)], "dn_D": [float(v) for v in prob.dn_of(d)]}
    print("\nRobustesse : niveau (moyenne des noeuds dn) sous d'autres choix, faisceau non polarise, sigma de Fisher du niveau")
    niveaux = []
    for etiquette, kw in variantes():
        prob, _ = probleme_absolu(**kw["pb"])
        x = ajuste_non_polarise(prob)
        cibles = list(range(prob.i_dn, prob.i_dn + prob.J))
        info = prob.information(x, cibles, exclure=[prob.i_ft, prob.i_fr])
        sd, _noeuds = sm.sigma_niveau(info, prob.J)
        niveaux.append((etiquette, niveau_de(prob, x), sd, kw.get("valide", True)))
        print(f"   {etiquette:<46} niveau {niveaux[-1][1]:+.4f}  (Fisher +-{sd:.4f})" + ("" if niveaux[-1][3] else "   [ecarte : un film a un rms > 1 %]"))
    valides = np.array([v for _e, v, _s, ok in niveaux if ok])
    sortie["variantes"] = {"niveaux": {e: v for e, v, _s, _ok in niveaux}, "moyenne": float(valides.mean()), "ecart_type": float(valides.std(ddof=1)), "n": int(valides.size),
                           "sigma_fisher_aleatoire": float(np.median([s for _e, _v, s, _ok in niveaux]))}
    print(f"\n{valides.size} variantes retenues : niveau {valides.mean():+.4f}, ecart-type entre variantes {valides.std(ddof=1):.4f}")
    return sortie


def variantes():
    """Les choix d'analyse dont on mesure l'effet sur le niveau : (etiquette, parametres du probleme)."""
    base = {}
    out = [("reference : 4 echantillons, 1000-3300, J = 3", {"pb": base}),
           ("R du saphir nu non utilise", {"pb": {"poids_r_nu": 0.0}}),
           ("T seul (nu + films)", {"pb": {"utiliser_r": False}}),
           ("R seul (nu + films)", {"pb": {"utiliser_t": False}})]
    for retire in ("Nb", "Ta", "Si"):
        out.append((f"sans le film {retire}", {"pb": {"noms": tuple(n for n in ("nu", "Nb", "Ta", "Si") if n != retire)}}))
    out += [("saphir nu seul (T et R)", {"pb": {"noms": ("nu",)}}), ("saphir nu seul, T seul", {"pb": {"noms": ("nu",), "poids_r_nu": 0.0}})]
    for lo, hi in ((800, 3300), (1200, 3300), (1000, 2400), (1000, 3000), (1500, 3300)):
        out.append((f"fenetre {lo}-{hi}", {"pb": {"lam_min": float(lo), "lam_max": float(hi)}, "valide": lo >= 1000}))
    out += [("J = 4", {"pb": {"J": 4}}), ("plus de noeuds dans les films", {"pb": {"densite": 1.8e-4}}), ("moins de noeuds dans les films", {"pb": {"densite": 3.5e-4}})]
    return out


# ------------------------------------------------------------------------------------------------------------------------- profil
def etape_profil(sigma_f=0.15):
    sortie = {}
    niveaux = (-0.012, -0.0095, -0.0075, -0.005, -0.004, -0.0025, -0.001, 0.0, 0.001, 0.0025, 0.004, 0.005, 0.0075)
    for etiquette, poids in (("R du saphir nu utilise", 1.0), ("R du saphir nu NON utilise", 0.0)):
        prob, _ = probleme_absolu(poids_r_nu=poids)
        ref = int(np.argmin(np.abs(1.0 / prob.sk_dn - 1500.0)))
        x0 = ajuste_non_polarise(prob)
        n_pts = sum(2 * s.lam.size for s in prob.samples)
        echelle = max(prob.chi2(x0) / n_pts, 1.0)
        print(f"=== {etiquette}: noeud epingle a {1 / prob.sk_dn[ref]:.0f} nm ; echelle du chi2 = {echelle:.2f} (chi2 minimal / nombre de points) ===")
        sortie[etiquette] = {}
        for lib, f_libre in (("f = 0.5 exactement", False), (f"f libres, a priori N(0.5, {sigma_f})", True)):
            lignes = []
            for v in niveaux:
                fixed = {prob.i_dn + ref: v}
                if not f_libre:
                    fixed.update(prob.fixe_polarisation(0.5))
                x, _res = prob.ajuster(x0, fixed=fixed)
                pen = ((x[prob.i_ft] - 0.5) / sigma_f) ** 2 + ((x[prob.i_fr] - 0.5) / sigma_f) ** 2 if f_libre else 0.0
                lignes.append((v, prob.chi2(x) + pen, x))
            mini = min(c for _v, c, _x in lignes)
            print(f"  {lib}: noeud epingle -> chi2 - minimum")
            for v, c, x in lignes:
                print(f"     {v:+.4f}: {c - mini:9.1f}   autres noeuds " + " ".join(f"{u:+.4f}" for j, u in enumerate(prob.dn_of(x)) if j != ref)
                      + f";  f_T {x[prob.i_ft]:.2f} f_R {x[prob.i_fr]:.2f}")
            sortie[etiquette][lib] = {"pas": [v for v, _c, _x in lignes], "dchi2": [c - mini for _v, c, _x in lignes], "echelle": echelle, "intervalles": intervalles(lignes, mini, echelle)}
            iv = sortie[etiquette][lib]["intervalles"]
            print(f"     intervalle a 1 sigma [{iv['1sigma'][0]:+.4f}, {iv['1sigma'][1]:+.4f}]   a 2 sigma [{iv['2sigma'][0]:+.4f}, {iv['2sigma'][1]:+.4f}]")
    return sortie


def intervalles(lignes, mini, echelle):
    """Valeurs du noeud epingle ou chi2 - minimum franchit echelle*1 et echelle*4, par interpolation lineaire du profil."""
    v = np.array([a for a, _c, _x in lignes])
    c = np.array([b for _a, b, _x in lignes]) - mini
    o = np.argsort(v)
    v, c = v[o], c[o]
    i0 = int(np.argmin(c))
    out = {}
    for nom, seuil in (("1sigma", echelle * 1.0), ("2sigma", echelle * 4.0)):
        lo, hi = v[0], v[-1]
        for k in range(i0, 0, -1):
            if c[k - 1] >= seuil >= c[k] or c[k] < seuil <= c[k - 1]:
                lo = v[k - 1] + (v[k] - v[k - 1]) * (seuil - c[k - 1]) / (c[k] - c[k - 1])
                break
        for k in range(i0, v.size - 1):
            if c[k + 1] >= seuil >= c[k] or c[k] < seuil <= c[k + 1]:
                hi = v[k] + (v[k + 1] - v[k]) * (seuil - c[k]) / (c[k + 1] - c[k])
                break
        out[nom] = (float(lo), float(hi))
    return out


# ------------------------------------------------------------------------------------------------------------------- information
def etape_information():
    sortie = {}
    for etiquette, poids in (("R du saphir nu utilise", 1.0), ("R du saphir nu NON utilise", 0.0)):
        prob, _ = probleme_absolu(poids_r_nu=poids)
        x = ajuste_non_polarise(prob)
        cibles = list(range(prob.i_dn, prob.i_dn + prob.J))
        print(f"=== {etiquette} (sigma des donnees {sm.SIGMA_ABS}) ===")
        info = prob.information(x, cibles, exclure=[prob.i_ft, prob.i_fr])
        niveau, _ = sm.sigma_niveau(info, prob.J)
        sortie[etiquette] = {"f=0.5": niveau}
        print(f"   f = 0.5 exactement          : sigma(niveau) = {niveau:.5f}")
        for sd in (0.05, 0.1, 0.15, 0.25, 0.5, 5.0):
            info = prob.information(x, cibles, priors={prob.i_ft: sd, prob.i_fr: sd})
            niveau, _ = sm.sigma_niveau(info, prob.J)
            sortie[etiquette][f"sigma_f={sd}"] = niveau
            print(f"   f_T, f_R ~ N(0.5, {sd:4.2f})      : sigma(niveau) = {niveau:.5f}")
    print("Quelles donnees fixent le niveau ? sigma du niveau, f = 0.5 exactement")
    sortie["sous_ensembles"] = {}
    for etiquette, kw in (("saphir nu, T et R", dict(noms=("nu",))), ("saphir nu, T seul", dict(noms=("nu",), poids_r_nu=0.0)),
                          ("3 films, T et R", dict(noms=("Nb", "Ta", "Si"))), ("3 films, T seul", dict(noms=("Nb", "Ta", "Si"), utiliser_r=False)),
                          ("3 films, R seul", dict(noms=("Nb", "Ta", "Si"), utiliser_t=False)), ("tout", dict())):
        prob, _ = probleme_absolu(**kw)
        x = ajuste_non_polarise(prob)
        info = prob.information(x, list(range(prob.i_dn, prob.i_dn + prob.J)), exclure=[prob.i_ft, prob.i_fr])
        sortie["sous_ensembles"][etiquette] = sm.sigma_niveau(info, prob.J)[0]
        print(f"   {etiquette:<20}: {sortie['sous_ensembles'][etiquette]:.5f}")
    return sortie


# ---------------------------------------------------------------------------------------------------------------------------- mwir
def etape_mwir():
    sortie = {}
    print("Fenetres 1000 -> lam_max, J = 4, R du saphir nu NON utilise (sa fermeture echoue au-dela de 4 um), absorption mesuree du saphir")
    for absorbant, tag in ((True, "k_s mesure"), (False, "k_s = 0")):
        for hi in (3300, 4300, 5000, 5200):
            if not absorbant and hi not in (4300, 5000):
                continue
            prob, _ = probleme_absolu(1000.0, float(hi), J=4, poids_r_nu=0.0, absorbant=absorbant)
            x = ajuste_non_polarise(prob)
            info = prob.information(x, list(range(prob.i_dn, prob.i_dn + prob.J)), exclure=[prob.i_ft, prob.i_fr])
            sd = np.sqrt(np.diag(np.linalg.pinv(info, rcond=1e-14, hermitian=True)))
            print(f"   1000-{hi} {tag:<11} noeuds {' '.join(f'{1 / s:5.0f}' for s in prob.sk_dn)} nm : dn " + " ".join(f"{v:+.4f}" for v in prob.dn_of(x))
                  + "  sd " + " ".join(f"{s:.4f}" for s in sd) + "  rms T " + " ".join(f"{100 * t:.2f}" for _n, t, _r in prob.rms(x)))
            sortie[f"{hi}_{tag}"] = {"lam_noeuds": [float(1 / s) for s in prob.sk_dn], "dn": [float(v) for v in prob.dn_of(x)], "sd": [float(s) for s in sd]}
    return sortie


# ---------------------------------------------------------------------------------------------------------------------- rapport
def films_normalises(noms=None, J=3):
    refs = references()
    sk = sm.noeuds_sigma(450.0, 5200.0, J)
    films = [sm.film_normalise(n, refs[n], sk) for n in (noms or list(refs))]
    return sm.ProblemeNormalise(films, sk), sk


def etape_rapport():
    prob, _sk = films_normalises()
    sortie = {}
    t0 = time.time()
    pieces = []
    for f in prob.films:
        seul = sm.ProblemeNormalise([f], prob.sk_dn)
        xi, _res = seul.ajuster(seul.x_start, fixed={seul.i_dn + j: 0.0 for j in range(seul.J)}, max_nfev=600)
        pieces.append(xi[: seul.i_dn])
    xa = np.concatenate(pieces + [np.zeros(prob.J)])
    print(f"films ajustes un par un (saphir = Sellmeier) en {time.time() - t0:.0f} s ; rms (% de T) : "
          + " ".join(f"{n}:{100 * r:.2f}" for n, r in prob.rmse(xa)))
    x, res = prob.ajuster(xa, max_nfev=200)
    print(f"ajustement conjoint de {len(prob.films)} films, dn libre : {res.nfev} evaluations, {time.time() - t0:.0f} s")
    chi_a, chi_b = prob.chi2(xa), prob.chi2(x)
    dn = prob.dn_of(x)
    print(f"chi2 : dn = 0 -> {chi_a:.1f} ; dn libre -> {chi_b:.1f} (gain {chi_a - chi_b:.1f}) ; dn aux noeuds ({', '.join(f'{1 / s:.0f}' for s in prob.sk_dn)} nm) : "
          + " ".join(f"{v:+.4f}" for v in dn) + f"   (bornes +-0.05, epaisseurs +-{100 * sm.D_REL_RATIO:.0f} %)")
    ev, vec = np.linalg.eigh(prob.information_dn(x))
    for e, v in zip(ev, vec.T, strict=True):
        print(f"   valeur propre {e:10.3g}  sigma {1 / np.sqrt(max(e, 1e-30)):8.4f}  direction " + " ".join(f"{c:+.3f}" for c in v))
    print("   variation d'epaisseur par rapport au film certifie (%) : " + "  ".join(f"{f.name}:{100 * (prob.film_x(x, i)[0] / f.x0[0] - 1):+.2f}" for i, f in enumerate(prob.films)))
    sortie.update({"gain_chi2": float(chi_a - chi_b), "dn": [float(v) for v in dn], "valeurs_propres": [float(e) for e in ev], "sigma_niveau_equiv": float(1 / np.sqrt(max(ev[0], 1e-30)))})
    return sortie


# ---------------------------------------------------------------------------------------------------------------------- propagation
def etape_propagation():
    niveaux = (-0.0079, -0.0040, -0.0028, 0.0, +0.0030)
    grille = np.array([1000.0, 1500.0, 2000.0, 3000.0])
    sortie = {"absolu": {}, "normalise": {}}
    print("(1) Films ABSOLUS : variation de n_f et de d quand le saphir est epingle a Sellmeier + c (reference c = 0), faisceau non polarise")
    prob, _ = probleme_absolu(poids_r_nu=0.0)
    ref = ajuste_non_polarise(prob, niveau=0.0)
    sols = {0.0: ref}
    for c in niveaux:
        if c != 0.0:
            sols[c], _ = prob.ajuster(ref, fixed={**prob.fixe_polarisation(0.5), **prob.fixe_niveau(c)})
    print(f"{'film':<5}{'c':>9}{'dd %':>8}   dn_f a " + " ".join(f"{g:.0f}" for g in grille) + f" nm{'chi2':>12}")
    for i, s in enumerate(prob.samples):
        if not s.nodes:
            continue
        g = np.clip(grille, s.lam[0], s.lam[-1])
        n0 = sm.nk_from_x_pwlnk(prob.film_x(ref, i), g, s.sk, sm.K_LO, sm.K_HI)[0]
        for c in niveaux:
            x = sols[c]
            dn_f = sm.nk_from_x_pwlnk(prob.film_x(x, i), g, s.sk, sm.K_LO, sm.K_HI)[0] - n0
            dd = 100 * (prob.film_x(x, i)[0] / prob.film_x(ref, i)[0] - 1)
            print(f"{s.name:<5}{c:+9.4f}{dd:+8.2f}   " + " ".join(f"{v:+8.4f}" for v in dn_f) + f"{prob.chi2(x):12.1f}")
            sortie["absolu"].setdefault(s.name, {})[f"{c:+.4f}"] = {"dd_pct": float(dd), "dn_f": [float(v) for v in dn_f], "chi2": prob.chi2(x)}
    print("\n(2) Films NORMALISES (chacun seul) : variation de n_f a 1000 et 2000 nm et de d, saphir epingle a Sellmeier + c")
    refs = references()
    sk3 = sm.noeuds_sigma(450.0, 5200.0, 3)
    print(f"{'film':<20}{'c':>9}{'dd %':>8}{'dn_f 1000':>11}{'dn_f 2000':>11}{'rms %T':>9}")
    for nom in refs:
        film = sm.film_normalise(nom, refs[nom], sk3)
        un = sm.ProblemeNormalise([film], sk3)
        depart, ref_n, ref_d = None, None, None
        for c in sorted(niveaux, key=abs):
            x, _res = un.ajuster(un.x_start if depart is None else depart, fixed={un.i_dn + j: c for j in range(un.J)}, max_nfev=300)
            ns = [sm.nk_from_x_pwlnk(un.film_x(x, 0), np.array([g]), film.sk, sm.K_LO, sm.K_HI)[0][0] for g in (1000.0, 2000.0)]
            if depart is None:
                depart, ref_n, ref_d = x, ns, un.film_x(x, 0)[0]
            sortie["normalise"].setdefault(nom, {})[f"{c:+.4f}"] = {"dd_pct": float(100 * (un.film_x(x, 0)[0] / ref_d - 1)), "dn_f_1000": float(ns[0] - ref_n[0]),
                                                                    "dn_f_2000": float(ns[1] - ref_n[1]), "rms_pct": float(100 * un.rmse(x)[0][1])}
        for c in sorted(niveaux):
            r = sortie["normalise"][nom][f"{c:+.4f}"]
            print(f"{nom:<20}{c:+9.4f}{r['dd_pct']:+8.2f}{r['dn_f_1000']:+11.4f}{r['dn_f_2000']:+11.4f}{r['rms_pct']:9.3f}")
    return sortie


# ---------------------------------------------------------------------------------------------------------------------- synthese
def etape_synthese(tirages=6):
    """Donnees simulees : verite = films de l'ajustement reel (spline) puis films TLU certifies (autre famille) ; niveau et polarisation plantes."""
    sortie = {}
    rng = np.random.default_rng(20261012)
    refs = references()
    prob0, sk = probleme_absolu()
    vrai = ajuste_non_polarise(prob0, niveau=0.0)

    def simule(famille, niveau, f, bruit, deficit_r_nu=0.0):
        out = []
        for i, s in enumerate(prob0.samples):
            if famille == "spline":
                x = vrai.copy()
                x[prob0.i_dn:prob0.i_dn + prob0.J] = niveau
                x[prob0.i_ft], x[prob0.i_fr] = f
                t, r = prob0.TR(x, i)
            else:
                ns = (s.sell + niveau).astype(np.complex128)
                if s.nodes:
                    p = refs[sm.DEPART_ABSOLU[s.name]]["p"]
                    n, k = sm.nk_tlu(p, s.lam)
                    couches, d_couches = (n - 1j * k).astype(np.complex128).reshape(-1, 1), np.array([float(p[0])])
                else:
                    couches, d_couches = np.zeros((s.lam.size, 0), dtype=np.complex128), np.zeros(0)
                rs, ts = sm.calc_spectrum_oblique_backside_vectorized(s.lam, couches, d_couches, ns, 8.0, "s", sm.SUBSTRATE_NM)
                rp, tp = sm.calc_spectrum_oblique_backside_vectorized(s.lam, couches, d_couches, ns, 8.0, "p", sm.SUBSTRATE_NM)
                t, r = ts + f[0] * (tp - ts), rs + f[1] * (rp - rs)
            r = r - (deficit_r_nu if s.name == "nu" else 0.0)
            out.append(replace(s, T=t + rng.normal(0, bruit, t.size), R=r + rng.normal(0, bruit, r.size)))
        return out

    print(f"{tirages} tirages de bruit a 0.1 % ; niveau retrouve (moyenne des noeuds dn), faisceau suppose non polarise (f = 0.5)")
    cas = [("spline", 0.0, (0.5, 0.5), 0.0), ("spline", -0.004, (0.5, 0.5), 0.0), ("spline", -0.0075, (0.5, 0.5), 0.0),
           ("spline", 0.0, (0.35, 0.35), 0.0), ("spline", 0.0, (0.65, 0.65), 0.0), ("spline", 0.0, (0.5, 0.9), 0.002),
           ("TLU", 0.0, (0.5, 0.5), 0.0), ("TLU", -0.004, (0.5, 0.5), 0.0), ("TLU", -0.0075, (0.5, 0.5), 0.0), ("TLU", 0.0, (0.4, 0.4), 0.0), ("TLU", 0.0, (0.6, 0.6), 0.0)]
    for famille, niveau, f, deficit in cas:
        for etiquette, poids in (("R nu utilise", 1.0), ("R nu non utilise", 0.0)):
            vals = []
            for _ in range(tirages):
                p = sm.ProblemeAbsolu(simule(famille, niveau, f, 0.001, deficit), sk, poids_r_nu=poids)
                p.x_start = vrai.copy()
                p.x_start[p.i_dn:p.i_dn + p.J] = 0.0
                x = ajuste_non_polarise(p, tours=1)
                vals.append(float(np.mean(p.dn_of(x))))
            vals = np.array(vals)
            cle = f"{famille} niveau {niveau:+.4f} f {f} deficit R nu {deficit} {etiquette}"
            sortie[cle] = {"biais": float(vals.mean() - niveau), "ecart_type": float(vals.std())}
            print(f"  verite {famille:<6} niveau plante {niveau:+.4f}, faisceau {f}, deficit R nu {100 * deficit:.1f} %, {etiquette:<17}: biais {vals.mean() - niveau:+.4f}  ecart-type {vals.std():.4f}")
    return sortie


# ---------------------------------------------------------------------------------------------------------------------- corridor
def regle_du_corridor(niveau, sigma_variantes, sigma_fisher_polarisation):
    """La regle, ecrite pour qu'on puisse la contester :

    sigma_total^2 = sigma_variantes^2 + sigma_fisher_polarisation^2
        * sigma_variantes : ecart-type du niveau entre les variantes d'analyse (retrait d'un film, fenetre, noeuds, canaux) ;
        * sigma_fisher_polarisation : ecart-type du niveau donne par l'information de Fisher quand la fraction p du faisceau a l'a priori
          N(0.5, sigma_f) ; il contient deja le bruit aleatoire (0,0005) et ce que les donnees contraignent de f. sigma_f = 0.15 (degre de
          polarisation du faisceau de l'ordre de 30 %) est une HYPOTHESE, pas une mesure : `--sigma-f` la change.
    corridor = niveau +- 1,96 sigma_total, relatif a l'indice de reference (le Sellmeier d'id 3).
    """
    sigma_total = float(np.sqrt(sigma_variantes**2 + sigma_fisher_polarisation**2))
    return {"niveau": niveau, "sigma_total": sigma_total, "bas": niveau - 1.96 * sigma_total, "haut": niveau + 1.96 * sigma_total,
            "sigma_variantes": sigma_variantes, "sigma_fisher_polarisation": sigma_fisher_polarisation}


def sigma_niveau_avec_prior(sigma_f):
    """sigma du niveau (Fisher, bruit de 0,1 %) quand f_T et f_R ont l'a priori N(0.5, sigma_f) ; R du saphir nu non utilise (sa fermeture est suspecte)."""
    prob, _ = probleme_absolu(poids_r_nu=0.0)
    x = ajuste_non_polarise(prob)
    info = prob.information(x, list(range(prob.i_dn, prob.i_dn + prob.J)), priors={prob.i_ft: sigma_f, prob.i_fr: sigma_f})
    return sm.sigma_niveau(info, prob.J)[0]


def etape_corridor(sortie, sigma_f=0.15, abs_res=None):
    sortie.mkdir(parents=True, exist_ok=True)
    abs_res = abs_res or etape_absolu()
    var = abs_res["variantes"]
    sigma_prior = sigma_niveau_avec_prior(sigma_f)
    regle = regle_du_corridor(var["moyenne"], var["ecart_type"], sigma_prior)
    print(f"\nIndice de reference = Sellmeier d'id 3 ; niveau mesure {regle['niveau']:+.4f} +- {regle['sigma_total']:.4f} (1 sigma : variantes "
          f"{var['ecart_type']:.4f}, Fisher avec a priori sur f {sigma_prior:.4f} pour sigma_f = {sigma_f})")
    print(f"corridor a 95 % : [{regle['bas']:+.4f}, {regle['haut']:+.4f}] autour de la reference")
    lam = np.arange(450.0, 5201.0, 50.0)
    no = sm.indice_saphir(lam)
    from _artefact import chemin_libre

    cible, ancien = chemin_libre(sortie / "saphir_corridor_indice.csv")
    lignes = ["lambda_nm;n_reference;n_corridor_bas;n_corridor_haut"]
    lignes += [f"{la:.0f};{no[i]:.5f};{no[i] + regle['bas']:.5f};{no[i] + regle['haut']:.5f}" for i, la in enumerate(lam)]
    cible.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"consigne dans {cible}" + (f" ({ancien.name} conserve)" if ancien else ""))
    tracer(sortie, regle, lam, no, float(np.sqrt(var["ecart_type"] ** 2 + var["sigma_fisher_aleatoire"] ** 2)))
    return {"regle": regle, "sigma_f": sigma_f, "absolu": abs_res}


def tracer(sortie, regle, lam, no, sigma_exact):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from _artefact import chemin_libre

    lam_nu, t = sm.lire_mesure("24-03-accurate__tnusaphire-2f.csv")
    _l, r = sm.lire_mesure("24-03-accurate__rnu-2f.csv")
    ns = sm.indice_saphir(lam_nu)
    n_t = (1 + np.sqrt((1 - t) / (1 + t))) / (1 - np.sqrt((1 - t) / (1 + t)))
    n_r = (1 + np.sqrt(r / (2 - r))) / (1 - np.sqrt(r / (2 - r)))
    vu = (lam_nu >= 500) & (lam_nu <= 3600)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.5, 1]})
    a1.fill_between(lam, 1e3 * regle["bas"], 1e3 * regle["haut"], color="tab:green", alpha=0.35, label="corridor a 95 % (donnees absolues)")
    a1.axhline(0.0, color="tab:green", lw=1.5, label="reference : Sellmeier d'id 3")
    a1.plot(lam_nu[vu], 1e3 * (n_t - ns)[vu], ".", color="tab:blue", ms=4, label="saphir nu, inversion de T seul")
    a1.plot(lam_nu[vu], 1e3 * (n_r - ns)[vu], ".", color="tab:red", ms=4, label="saphir nu, inversion de R seul (deficit de fermeture)")
    a1.axvspan(1000, 3300, color="tab:blue", alpha=0.05)
    a1.set_xlim(450, 5200)
    a1.set_ylim(-12, 8)
    a1.set_xlabel("longueur d'onde (nm)")
    a1.set_ylabel("n - n_reference (x 1e-3)")
    a1.set_title("Indice du saphir relativement a la reference")
    a1.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2)
    barres = [("spectres normalises (9 references) : niveau indetermine", -12, 8),
              ("donnees absolues, f = 0.5 exact", 1e3 * (regle["niveau"] - 1.96 * sigma_exact), 1e3 * (regle["niveau"] + 1.96 * sigma_exact)),
              ("donnees absolues, f = 0.5 +- sigma_f (corridor)", 1e3 * regle["bas"], 1e3 * regle["haut"])]
    for i, (nom, lo, hi) in enumerate(barres):
        a2.barh(i, hi - lo, left=lo, height=0.62, color="tab:green" if i == 2 else "tab:blue", alpha=0.6)
        a2.text(-11.8, i + 0.34, nom, fontsize=7, va="bottom")
    a2.axvline(0.0, color="k", ls=":", lw=0.8)
    a2.set_xlim(-12, 8)
    a2.set_ylim(-0.5, len(barres) + 0.1)
    a2.set_yticks([])
    a2.set_xlabel("niveau de n - n_reference entre 1 et 3,3 um (x 1e-3)")
    a2.set_title("Ce que chaque information laisse du niveau")
    fig.tight_layout()
    cible, _ancien = chemin_libre(sortie / "saphir_corridor_indice.png")
    fig.savefig(cible, dpi=130)
    plt.close(fig)
    print(f"consigne dans {cible}")


ETAPES = {"nu": etape_nu, "absolu": etape_absolu, "profil": etape_profil, "information": etape_information,
          "mwir": etape_mwir, "rapport": etape_rapport, "propagation": etape_propagation, "synthese": etape_synthese}


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("etape", choices=sorted([*ETAPES, "corridor"]))
    ap.add_argument("--sortie", type=Path, default=sortie_par_defaut())
    ap.add_argument("--sigma-f", type=float, default=0.15, help="ecart-type a priori de la fraction p du faisceau (0.15 = degre de polarisation ~30 %%)")
    ap.add_argument("--threads", type=int, default=1, help="threads BLAS et Numba (1 par defaut : ne pas gener une campagne en cours)")
    args = ap.parse_args(argv)
    t0 = time.time()
    if args.etape == "corridor":
        res = etape_corridor(args.sortie, args.sigma_f)
    elif args.etape == "profil":
        res = etape_profil(args.sigma_f)
    else:
        res = ETAPES[args.etape]()
    args.sortie.mkdir(parents=True, exist_ok=True)
    racine = ROOT if ROOT in args.sortie.resolve().parents else None
    ecrit = ecrire_json(args.sortie / f"saphir_{args.etape}.json", {"etape": args.etape, "resultats": res, "duree_s": round(time.time() - t0, 1)}, racine=racine)
    print(f"{args.etape}: {time.time() - t0:.0f} s -> {ecrit.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
