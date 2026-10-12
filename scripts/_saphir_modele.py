"""MODELE DE L'INDICE DU SAPHIR : films en spline n / ln k (a la maniere d'INDEX SPLINE) + correction dn(lambda) du substrat.

Bibliotheque de `saphir_corridor.py`. Elle n'imprime rien et ne reconfigure pas la console.

POURQUOI. Quel est l'indice du saphir des echantillons ? Les references certifiees ont ete ajustees avec le Sellmeier du rayon ordinaire
(Malitson-Dodge) FIXE. On le libere : n_s(lambda) = Sellmeier(lambda) + dn(lambda), dn etant une spline a J noeuds (3 ou 4) commune
a tous les echantillons, et on laisse chaque film libre.

LES BRIQUES SONT CELLES DU DEPOT, RIEN N'EST REECRIT :
  * n et k d'un film = `nk_from_x_pwlnk` d'INDEX SPLINE : valeurs aux noeuds equidistants en sigma = 1/lambda, spline cubique not-a-knot ;
  * Sellmeier = `sellmeier_n_array` ; TLU = `epsilon1_TL_analytic`, `epsilon2_TLU_array`, `epsilon_to_nk` ;
  * spectres NORMALISES au substrat (T du film + substrat / T du substrat nu) : `calculate_RT_single_layer_backside_array` ;
  * spectres ABSOLUS a 8 degres : `calc_spectrum_oblique_backside_vectorized` (lame de 1 mm, face arriere incoherente, R et T TOTAUX),
    en s et en p ; le faisceau mesure T = T_s + f_T.(T_p - T_s) et R = R_s + f_R.(R_p - R_s), f etant la fraction p du faisceau.

CE QUE LA MESURE DONNE (voir reports/SAPHIR_corridor_indice_2026-10-12.md) : sur des spectres normalises, le niveau de dn est exactement
degenere avec l'epaisseur et l'indice des films ; sur des spectres absolus, il est fixe, a la polarisation du faisceau pres.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from certus.core.certus_core import HC_EV_NM  # noqa: E402
from certus.physics.certus_optical_models import sellmeier_n_array  # noqa: E402
from certus.physics.certus_tmm_oblique import calc_spectrum_oblique_backside_vectorized  # noqa: E402
from certus.spline.spline_objective import nk_from_x_pwlnk  # noqa: E402
from certus.utils.certus_index_utils import spectral_rmse_weights  # noqa: E402
from certus_physics import (  # noqa: E402
    calculate_bare_substrate_RT,
    calculate_RT_single_layer_backside_array,
    epsilon1_TL_analytic,
    epsilon2_TLU_array,
    epsilon_to_nk,
)

BASE = ROOT / "example" / "database_depots"
K_LO, K_HI = 1e-5, 5.0  # le crible de k d'INDEX SPLINE
N_BOUNDS = (1.15, 3.6)
PRIOR_CURV_N = 0.1  # ecart-type a priori de la courbure (difference seconde) des noeuds n : retire les directions singulieres, ne faconne pas l'ajustement
PRIOR_CURV_L = 3.0  # idem pour ln k
SIGMA_RATIO = 0.003  # echelle photometrique d'un spectre certifie (fraction de T) : systematique, pas le bruit d'un point
N_REF = 100.0  # points independants attribues a chaque spectre normalise
SIGMA_ABS = 0.001  # 0,1 % de T ou de R
THETA_DEG = 8.0
SUBSTRATE_NM = 1.0e6
D_REL_RATIO = 0.06
D_REL_ABS = 0.03

#: Les trois films absolus de la seance 24-03 et la reference certifiee dont les parametres TLU les demarrent (meme echantillon a l'epaisseur pres).
FICHIERS_24_03 = {"nu": ("tnusaphire-2f", "rnu-2f"), "Nb": ("tabsnb", "rabsnb"), "Ta": ("tabsta", "rabsta"), "Si": ("tabssi", "rabssi")}
DEPART_ABSOLU = {"Nb": "h400", "Ta": "pe-ta2", "Si": "h400-sio2"}


# ---------------------------------------------------------------------------------------------------------------- indices du saphir
def _coefficients_ordinaire():
    b1, c1, b2, c2, b3, c3 = json.loads((ROOT / "data" / "materials_v1.json").read_text(encoding="utf-8"))["sellmeier_coeffs_by_id"]["3"]
    return b1, c1, b2, c2, b3, c3


def indice_saphir(lam_nm):
    """L'indice du saphir de CERTUS : le Sellmeier d'id 3 (rayon ordinaire de Malitson et Dodge), le seul."""
    b1, c1, b2, c2, b3, c3 = _coefficients_ordinaire()
    return sellmeier_n_array(np.ascontiguousarray(lam_nm, dtype=np.float64), b1, c1, b2, c2, b3, c3, 0.0)


# ------------------------------------------------------------------------------------------------------------- noeuds et films
def noeuds_sigma(lam_lo, lam_hi, nombre):
    """`nombre` noeuds equidistants en sigma = 1/lambda entre les deux longueurs d'onde, par sigma croissant."""
    return np.linspace(1.0 / lam_hi, 1.0 / lam_lo, nombre)


def matrice_dn(sk_dn, lam_nm):
    """(n_lam, J) : l'interpolation d'INDEX SPLINE de dn (cubique not-a-knot en sigma ; une parabole pour 3 noeuds)."""
    sig = np.clip(1.0 / np.asarray(lam_nm, dtype=np.float64), sk_dn[0], sk_dn[-1])
    return np.asarray(CubicSpline(sk_dn, np.eye(len(sk_dn)), bc_type="not-a-knot")(sig), dtype=np.float64)


def nk_tlu(p, lam_nm):
    """n, k du film de Tauc-Lorentz-Urbach de parametres p = (d, Eg, A, E0, C, Eu, eps_inf), comme INDEX les calcule."""
    _d, eg, a, e0, c, eu, eps_inf = p
    energie = HC_EV_NM / np.asarray(lam_nm, dtype=np.float64)
    e1 = epsilon1_TL_analytic(energie, eg, a, e0, c, eps_inf)
    e2 = epsilon2_TLU_array(energie, eg, a, e0, c, eu)
    n, k, _ = epsilon_to_nk(e1, e2, 0.5, 15.0, 15.0)
    return np.asarray(n, dtype=np.float64), np.asarray(k, dtype=np.float64)


def vecteur_film(p, sk, d_rel):
    """(x0, borne basse, borne haute) d'un film [d, n aux noeuds, ln k aux noeuds] demarre au film TLU certifie echantillonne aux noeuds."""
    n_nodes, k_nodes = nk_tlu(p, 1.0 / sk)
    d0 = float(p[0])
    count = sk.size
    x0 = np.concatenate([[d0], n_nodes, np.log(np.clip(k_nodes, K_LO * 1.0001, K_HI * 0.999))])
    lo = np.concatenate([[d0 * (1 - d_rel)], np.full(count, N_BOUNDS[0]), np.full(count, np.log(K_LO))])
    hi = np.concatenate([[d0 * (1 + d_rel)], np.full(count, N_BOUNDS[1]), np.full(count, np.log(K_HI))])
    return x0, lo, hi


def nombre_de_noeuds(lam_lo, lam_hi, densite=2.5e-4):
    return int(np.clip(round((1.0 / lam_lo - 1.0 / lam_hi) / densite) + 1, 4, 12))


def lire_mesure(fichier):
    """(lambda, valeur en fraction) d'un fichier de example/database_depots/mesures (valeurs en %)."""
    a = np.genfromtxt(BASE / "mesures" / fichier, delimiter=",", skip_header=1)
    return a[:, 0], a[:, 1] / 100.0


def references_saphir():
    """{nom: reference} des references certifiees sur saphir (Al2O3) de la base, avec le premier depot de type T."""
    refs = json.loads((BASE / "references_index.json").read_text(encoding="utf-8"))["references"]
    cat = {d["id"]: d for d in json.loads((BASE / "catalogue.json").read_text(encoding="utf-8"))["depots"]}
    out = {}
    for r in refs:
        if r["substrat"] != "Al2O3":
            continue
        t_dep = next(d for d in r["depots"] if cat[d]["voies"][0]["mode"] == "T")
        out[r["nom"]] = {"p": tuple(r["parametres"][k] for k in ("d", "Eg", "A", "E0", "C", "Eu", "eps_inf")),
                         "fichier": Path(cat[t_dep]["fichier"]).name, "bande": r["bande_nm"]}
    return out


# ============================================================================================ PARTIE 1 : SPECTRES NORMALISES AU SUBSTRAT
@dataclass
class Film:
    name: str
    lam: np.ndarray
    y: np.ndarray
    v: np.ndarray
    sk: np.ndarray
    sig: np.ndarray
    sell: np.ndarray
    mdn: np.ndarray
    x0: np.ndarray
    lo: np.ndarray
    hi: np.ndarray

    @property
    def nodes(self) -> int:
        return (self.x0.size - 1) // 2


def film_normalise(nom, ref, sk_dn, lam_min=450.0, lam_max=5200.0, d_rel=D_REL_RATIO):
    """Un spectre T(film + substrat) / T(substrat nu) d'une reference de la base, sur sa bande certifiee dans [lam_min, lam_max]."""
    lam, t = lire_mesure(ref["fichier"])
    lo = max(ref["bande"][0] or 0.0, lam_min)
    hi = min(ref["bande"][1] or 1e9, lam_max)
    sel = (lam >= lo) & (lam <= hi) & np.isfinite(t)
    lam, y = lam[sel], t[sel]
    order = np.argsort(lam)
    lam, y = np.asarray(lam[order], dtype=np.float64), np.asarray(y[order], dtype=np.float64)
    w = np.asarray(spectral_rmse_weights(lam), dtype=np.float64)
    sk = noeuds_sigma(lam[0], lam[-1], nombre_de_noeuds(lam[0], lam[-1]))
    x0, lo_b, hi_b = vecteur_film(ref["p"], sk, d_rel)
    return Film(nom, lam, y, np.sqrt(N_REF * w / np.sum(w)), sk, 1.0 / lam, indice_saphir(lam), matrice_dn(sk_dn, lam), x0, lo_b, hi_b)


def rapport_modele(f: Film, xf, dn):
    n, k = nk_from_x_pwlnk(xf, f.lam, f.sk, K_LO, K_HI, f.sig)
    ns = f.sell + f.mdn @ dn
    _r, t = calculate_RT_single_layer_backside_array(f.lam, n, k, float(xf[0]), ns)
    return t / calculate_bare_substrate_RT(f.lam, ns)


def _moindres_carres(fun, jac, x_init, free, lo, hi, fixed, loss, f_scale, max_nfev):
    x_init = np.asarray(x_init, dtype=np.float64).copy()
    for idx, val in fixed.items():
        x_init[idx] = val

    def embed(z):
        x = x_init.copy()
        x[free] = z
        return x

    res = least_squares(
        lambda z: fun(embed(z)), np.clip(x_init[free], lo[free] + 1e-12, hi[free] - 1e-12),
        jac=lambda z: jac(embed(z))[:, free], bounds=(lo[free], hi[free]), method="trf", loss=loss, f_scale=f_scale,
        x_scale="jac", xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=max_nfev,
    )
    return embed(res.x), res


class ProblemeNormalise:
    """Tous les films ensemble : parametres = [film 1 (d, n aux noeuds, ln k aux noeuds), film 2, ..., noeuds dn]."""

    def __init__(self, films, sk_dn, borne_dn=0.05):
        self.films, self.sk_dn, self.J = films, np.asarray(sk_dn, dtype=np.float64), len(sk_dn)
        self.off = np.concatenate([[0], np.cumsum([f.x0.size for f in films])]).astype(int)
        self.i_dn = int(self.off[-1])
        self.n_par = self.i_dn + self.J
        self.lo = np.concatenate([f.lo for f in films] + [np.full(self.J, -borne_dn)])
        self.hi = np.concatenate([f.hi for f in films] + [np.full(self.J, borne_dn)])
        self.x_start = np.concatenate([f.x0 for f in films] + [np.zeros(self.J)])

    def film_x(self, x, i):
        return np.asarray(x[self.off[i]:self.off[i + 1]], dtype=np.float64)

    def dn_of(self, x):
        return np.asarray(x[self.i_dn:], dtype=np.float64)

    def modele(self, x, i):
        return rapport_modele(self.films[i], self.film_x(x, i), self.dn_of(x))

    def courbure(self, x):
        rows = []
        for i, f in enumerate(self.films):
            xf = self.film_x(x, i)
            for vec, prior in ((xf[1:1 + f.nodes], PRIOR_CURV_N), (xf[1 + f.nodes:], PRIOR_CURV_L)):
                rows.append((vec[:-2] - 2 * vec[1:-1] + vec[2:]) / prior)
        return np.concatenate(rows)

    def residus(self, x):
        parts = [f.v * (self.modele(x, i) - f.y) / SIGMA_RATIO for i, f in enumerate(self.films)]
        return np.concatenate(parts + [self.courbure(x)])

    def jacobien(self, x):
        x = np.asarray(x, dtype=np.float64)
        n_data = sum(f.lam.size for f in self.films)
        jac = np.zeros((n_data + self.courbure(x).size, self.n_par))
        r0 = 0
        dn = self.dn_of(x)
        for i, f in enumerate(self.films):
            xf = self.film_x(x, i)
            rows = slice(r0, r0 + f.lam.size)
            scale = f.v / SIGMA_RATIO
            steps = np.concatenate([[0.01], np.full(f.nodes, 1e-4), np.full(f.nodes, 1e-3)])
            for j in range(xf.size):
                up, dw = xf.copy(), xf.copy()
                up[j] += steps[j]
                dw[j] -= steps[j]
                jac[rows, self.off[i] + j] = scale * (rapport_modele(f, up, dn) - rapport_modele(f, dw, dn)) / (2 * steps[j])
            for j in range(self.J):
                up, dw = dn.copy(), dn.copy()
                up[j] += 1e-4
                dw[j] -= 1e-4
                jac[rows, self.i_dn + j] = scale * (rapport_modele(f, xf, up) - rapport_modele(f, xf, dw)) / 2e-4
            r0 += f.lam.size
        r = n_data
        for i, f in enumerate(self.films):
            for start, prior in ((1, PRIOR_CURV_N), (1 + f.nodes, PRIOR_CURV_L)):
                for m in range(f.nodes - 2):
                    c = self.off[i] + start + m
                    jac[r, c] += 1.0 / prior
                    jac[r, c + 1] -= 2.0 / prior
                    jac[r, c + 2] += 1.0 / prior
                    r += 1
        return jac

    def ajuster(self, x_init, fixed=None, loss="soft_l1", f_scale=3.0, max_nfev=200):
        fixed = dict(fixed or {})
        free = np.array([i for i in range(self.n_par) if i not in fixed], dtype=int)
        return _moindres_carres(self.residus, self.jacobien, x_init, free, self.lo, self.hi, fixed, loss, f_scale, max_nfev)

    def chi2(self, x):
        r = self.residus(x)
        return float(r @ r)

    def rmse(self, x):
        return [(f.name, float(np.sqrt(np.mean((self.modele(x, i) - f.y) ** 2)))) for i, f in enumerate(self.films)]

    def information_dn(self, x, rcond=1e-10):
        """Information de Fisher sur les noeuds dn une fois tous les parametres de film profiles (complement de Schur de J^T J)."""
        jac = self.jacobien(x)
        a_ff = jac[:, : self.i_dn].T @ jac[:, : self.i_dn]
        a_fs = jac[:, : self.i_dn].T @ jac[:, self.i_dn:]
        a_ss = jac[:, self.i_dn:].T @ jac[:, self.i_dn:]
        info = a_ss - a_fs.T @ np.linalg.pinv(a_ff, rcond=rcond, hermitian=True) @ a_fs
        return 0.5 * (info + info.T)


# ======================================================================================== PARTIE 2 : SPECTRES ABSOLUS (T ET R, 8 DEGRES)
def ks_saphir(lam_nm):
    """k du saphir nu de la seance, lu sur son T seul (transmittance interne d'une lame de 1 mm, n = Sellmeier ordinaire) : exponentielle d'un
    polynome du second degre en lambda ajuste sur 3900-5200 nm, et ZERO en dessous. Le T de la lame nue colle a Fresnel sans absorption entre
    1 et 2,4 um, et 0,2 % de T s'echangent contre 0,008 d'indice : un plancher d'absorption serait compense par dn. R n'est pas utilise."""
    lam = np.asarray(lam_nm, dtype=np.float64)
    lam_t, t = lire_mesure("24-03-accurate__tnusaphire-2f.csv")
    r1 = ((indice_saphir(lam_t) - 1) / (indice_saphir(lam_t) + 1)) ** 2
    a, b = r1**2 * t, (1 - r1) ** 2
    tau = (-b + np.sqrt(b**2 + 4 * a * t)) / (2 * a)
    ks = np.maximum(-np.log(np.clip(tau, 1e-6, 1)) * lam_t / (4 * np.pi * SUBSTRATE_NM), 1e-9)
    sel = lam_t >= 3900.0
    coef = np.polyfit((lam_t[sel] - 4500.0) / 1000.0, np.log(ks[sel]), 2)
    return np.where(lam >= 3900.0, np.exp(np.polyval(coef, (lam - 4500.0) / 1000.0)), 0.0)


@dataclass
class Echantillon:
    name: str
    lam: np.ndarray
    T: np.ndarray
    R: np.ndarray
    sk: np.ndarray | None
    sig: np.ndarray
    sell: np.ndarray
    mdn: np.ndarray
    ks: np.ndarray
    x0: np.ndarray
    lo: np.ndarray
    hi: np.ndarray

    @property
    def nodes(self) -> int:
        return (self.x0.size - 1) // 2 if self.x0.size else 0


def echantillons_absolus(refs, sk_dn, lam_min, lam_max, noms=("nu", "Nb", "Ta", "Si"), densite=2.5e-4, absorbant=False):
    """Le saphir nu et les films Nb2O5 / Ta2O5 / SiO2 de la seance 24-03 (T et R absolus), sur [lam_min, lam_max]."""
    out = []
    for nom in noms:
        t_file, r_file = FICHIERS_24_03[nom]
        lam, t = lire_mesure(f"24-03-accurate__{t_file}.csv")
        _lr, r = lire_mesure(f"24-03-accurate__{r_file}.csv")
        sel = (lam >= lam_min) & (lam <= lam_max)
        lam, t, r = lam[sel], t[sel], r[sel]
        ks = ks_saphir(lam) if absorbant else np.zeros(lam.size)
        mdn = matrice_dn(sk_dn, lam)
        if nom == "nu":
            out.append(Echantillon(nom, lam, t, r, None, 1 / lam, indice_saphir(lam), mdn, ks, np.zeros(0), np.zeros(0), np.zeros(0)))
            continue
        sk = noeuds_sigma(lam[0], lam[-1], nombre_de_noeuds(lam[0], lam[-1], densite))
        x0, lo, hi = vecteur_film(refs[DEPART_ABSOLU[nom]]["p"], sk, D_REL_ABS)
        out.append(Echantillon(nom, lam, t, r, sk, 1 / lam, indice_saphir(lam), mdn, ks, x0, lo, hi))
    return out


def lame_TR(s: Echantillon, xf, dn, f_t, f_r):
    """(T, R) totaux de la lame pour un faisceau de fraction p f_t (voie transmission) et f_r (voie reflexion)."""
    ns = (s.sell + s.mdn @ dn - 1j * s.ks).astype(np.complex128)
    if s.nodes:
        n, k = nk_from_x_pwlnk(xf, s.lam, s.sk, K_LO, K_HI, s.sig)
        couches = (n - 1j * k).astype(np.complex128).reshape(-1, 1)
        d_couches = np.array([float(xf[0])])
    else:
        couches = np.zeros((s.lam.size, 0), dtype=np.complex128)
        d_couches = np.zeros(0)
    rs, ts = calc_spectrum_oblique_backside_vectorized(s.lam, couches, d_couches, ns, THETA_DEG, "s", SUBSTRATE_NM)
    rp, tp = calc_spectrum_oblique_backside_vectorized(s.lam, couches, d_couches, ns, THETA_DEG, "p", SUBSTRATE_NM)
    return ts + f_t * (tp - ts), rs + f_r * (rp - rs)


class ProblemeAbsolu:
    """Parametres = [film Nb, film Ta, film Si (d, n aux noeuds, ln k aux noeuds), noeuds dn (J), f_T, f_R]."""

    def __init__(self, echantillons, sk_dn, poids_r_nu=1.0, utiliser_t=True, utiliser_r=True):
        self.samples, self.sk_dn, self.J = echantillons, np.asarray(sk_dn, dtype=np.float64), len(sk_dn)
        self.poids_r_nu, self.utiliser_t, self.utiliser_r = poids_r_nu, utiliser_t, utiliser_r
        self.off = np.concatenate([[0], np.cumsum([s.x0.size for s in echantillons])]).astype(int)
        self.i_dn = int(self.off[-1])
        self.i_ft, self.i_fr = self.i_dn + self.J, self.i_dn + self.J + 1
        self.n_par = self.i_fr + 1
        self.lo = np.concatenate([s.lo for s in echantillons] + [np.full(self.J, -0.05), [0.0, 0.0]])
        self.hi = np.concatenate([s.hi for s in echantillons] + [np.full(self.J, 0.05), [1.0, 1.0]])
        self.x_start = np.concatenate([s.x0 for s in echantillons] + [np.zeros(self.J), [0.5, 0.5]])

    def film_x(self, x, i):
        return np.asarray(x[self.off[i]:self.off[i + 1]], dtype=np.float64)

    def dn_of(self, x):
        return np.asarray(x[self.i_dn:self.i_dn + self.J], dtype=np.float64)

    def TR(self, x, i):
        return lame_TR(self.samples[i], self.film_x(x, i), self.dn_of(x), x[self.i_ft], x[self.i_fr])

    def lignes(self, x, i):
        s = self.samples[i]
        t, r = self.TR(x, i)
        parts = []
        if self.utiliser_t:
            parts.append((t - s.T) / SIGMA_ABS)
        if self.utiliser_r:
            parts.append((self.poids_r_nu if s.name == "nu" else 1.0) * (r - s.R) / SIGMA_ABS)
        return np.concatenate(parts)

    def courbure(self, x):
        rows = []
        for i, s in enumerate(self.samples):
            if s.nodes:
                xf = self.film_x(x, i)
                for vec, prior in ((xf[1:1 + s.nodes], PRIOR_CURV_N), (xf[1 + s.nodes:], PRIOR_CURV_L)):
                    rows.append((vec[:-2] - 2 * vec[1:-1] + vec[2:]) / prior)
        return np.concatenate(rows) if rows else np.zeros(0)

    def residus(self, x):
        return np.concatenate([self.lignes(x, i) for i in range(len(self.samples))] + [self.courbure(x)])

    def jacobien(self, x):
        x = np.asarray(x, dtype=np.float64)
        base = [self.lignes(x, i) for i in range(len(self.samples))]
        n_data = sum(b.size for b in base)
        jac = np.zeros((n_data + self.courbure(x).size, self.n_par))
        r0 = 0
        shared = list(range(self.i_dn, self.n_par))
        for i, s in enumerate(self.samples):
            rows = slice(r0, r0 + base[i].size)
            for col in list(range(self.off[i], self.off[i + 1])) + shared:
                if col in (self.i_ft, self.i_fr):
                    step = 1e-3
                elif col >= self.i_dn:
                    step = 1e-4
                else:
                    j = col - self.off[i]
                    step = 0.01 if j == 0 else (1e-4 if j <= s.nodes else 1e-3)
                up, dw = x.copy(), x.copy()
                up[col] += step
                dw[col] -= step
                jac[rows, col] = (self.lignes(up, i) - self.lignes(dw, i)) / (2 * step)
            r0 += base[i].size
        r = n_data
        for i, s in enumerate(self.samples):
            if not s.nodes:
                continue
            for start, prior in ((1, PRIOR_CURV_N), (1 + s.nodes, PRIOR_CURV_L)):
                for m in range(s.nodes - 2):
                    c = self.off[i] + start + m
                    jac[r, c] += 1.0 / prior
                    jac[r, c + 1] -= 2.0 / prior
                    jac[r, c + 2] += 1.0 / prior
                    r += 1
        return jac

    def ajuster(self, x_init, fixed=None, loss="soft_l1", f_scale=3.0, max_nfev=300):
        fixed = dict(fixed or {})
        free = np.array([i for i in range(self.n_par) if i not in fixed], dtype=int)
        return _moindres_carres(self.residus, self.jacobien, x_init, free, self.lo, self.hi, fixed, loss, f_scale, max_nfev)

    def chi2(self, x):
        r = self.residus(x)
        return float(r @ r)

    def rms(self, x):
        out = []
        for i, s in enumerate(self.samples):
            t, r = self.TR(x, i)
            out.append((s.name, float(np.sqrt(np.mean((t - s.T) ** 2))), float(np.sqrt(np.mean((r - s.R) ** 2)))))
        return out

    def fixe_polarisation(self, f=0.5):
        return {self.i_ft: f, self.i_fr: f}

    def fixe_niveau(self, c):
        return {self.i_dn + j: c for j in range(self.J)}

    def information(self, x, cibles, exclure=(), priors=None, rcond=1e-10):
        """Information de Fisher sur les parametres `cibles`, tous les autres (sauf `exclure`, tenus fixes) etant profiles.
        `priors` = {indice: sigma} ajoute un a priori gaussien."""
        jac = self.jacobien(x)
        tgt = np.array(cibles, dtype=int)
        skip = set(cibles) | set(exclure)
        oth = np.array([i for i in range(self.n_par) if i not in skip], dtype=int)
        a_oo = jac[:, oth].T @ jac[:, oth]
        a_ot = jac[:, oth].T @ jac[:, tgt]
        a_tt = jac[:, tgt].T @ jac[:, tgt]
        for idx, sd in (priors or {}).items():
            if idx in set(cibles):
                a_tt[list(tgt).index(idx), list(tgt).index(idx)] += 1.0 / sd**2
            elif idx in set(oth):
                a_oo[list(oth).index(idx), list(oth).index(idx)] += 1.0 / sd**2
        info = a_tt - a_ot.T @ np.linalg.pinv(a_oo, rcond=rcond, hermitian=True) @ a_ot
        return 0.5 * (info + info.T)


def sigma_niveau(info, n_dn):
    """Ecart-type du niveau (moyenne des noeuds dn) et de chaque noeud, depuis la matrice d'information sur les noeuds dn en tete."""
    cov = np.linalg.pinv(info, rcond=1e-14, hermitian=True)
    u = np.zeros(info.shape[0])
    u[:n_dn] = 1.0 / n_dn
    return float(np.sqrt(u @ cov @ u)), np.sqrt(np.diag(cov))[:n_dn]
