import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001
from .certus_strat_math import (
    check_extrema_proximity,
    calculate_extrema_distances,
    fit_parabola_vertex_3points,
    _solve_quadratic_target,
    _calc_T_from_matrix,
    _calc_T_added_layer,
)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def simulate_growth_kernel(
    p_thick_nominal: np.ndarray,
    i_layer: int,
    prev_thicknesses_sim: np.ndarray,
    wl: float,
    n_H,
    n_L,
    n_Sub,
    probe_offset: float,
    noise_val_precalc: float,
    non_monotonic_factor: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
    block_start_layer: int = -1,
) -> tuple[float, float]:
    """

    Fast TMM Simulation for robustness heuristics.

    CRITICAL PHYSICS NOTE:

    This kernel calculates T_front (Internal Transmission) ONLY.

    It intentionally IGNORES backside reflection for computational speed in heuristics.

    Do not use for absolute photometric accuracy. Use calculate_detailed_growth for that.

    This is a RELATIVE control kernel: target extraction and inversion both use the

    same front-only model, so there is no absolute backside mismatch in this loop.

    Args:

        non_monotonic_mode: How to handle non-monotonic T(d) curves:

            0 (ATTENUATE): Divide error by non_monotonic_factor (legacy)

            1 (REJECT): Return large penalty to reject candidate

    """
    if wl < 0.1:
        return (float(p_thick_nominal[i_layer]), 0.0)
    TWO_PI_VAL = TWO_PI
    M_before_00 = 1.0 + 0j
    M_before_01 = 0.0 + 0j
    M_before_10 = 0.0 + 0j
    M_before_11 = 1.0 + 0j
    for j in range(i_layer):
        n_prev = n_H if j % 2 == 0 else n_L
        th_prev = prev_thicknesses_sim[j]
        phi = TWO_PI_VAL / wl * n_prev * th_prev
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_prev if abs(n_prev) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_prev * sp
        t00 = cp * M_before_00 + m01 * M_before_10
        t01 = cp * M_before_01 + m01 * M_before_11
        t10 = m10 * M_before_00 + cp * M_before_10
        t11 = m10 * M_before_01 + cp * M_before_11
        M_before_00, M_before_01, M_before_10, M_before_11 = (t00, t01, t10, t11)
    # --- Empilement NOMINAL, accumule en parallele du reel ---------------------
    #
    # Le niveau de declenchement d'une couche est calcule AVANT le depot, sur la
    # conception nominale, et il ne bouge plus. Le viser sur un empilement devenu
    # errone est ce qui produit l'erreur de signe oppose : c'est le mecanisme de
    # compensation (Macleod, Bousquet).
    #
    # Avant ce correctif, la cible etait T_reel(d_nom) : la parabole d'inversion
    # interpolant exactement ce meme point, la resolution donnait Delta_d =
    # bruit / P', SANS aucun terme d'erreur accumulee. A bruit nul, l'epaisseur
    # etait nominale quelles que soient les erreurs precedentes, donc aucune
    # compensation ne pouvait apparaitre NI etre mesuree.
    M_nom_00 = 1.0 + 0j
    M_nom_01 = 0.0 + 0j
    M_nom_10 = 0.0 + 0j
    M_nom_11 = 1.0 + 0j
    for j in range(i_layer):
        n_prev = n_H if j % 2 == 0 else n_L
        th_prev_nom = p_thick_nominal[j]
        phi = TWO_PI_VAL / wl * n_prev * th_prev_nom
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_prev if abs(n_prev) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_prev * sp
        t00 = cp * M_nom_00 + m01 * M_nom_10
        t01 = cp * M_nom_01 + m01 * M_nom_11
        t10 = m10 * M_nom_00 + cp * M_nom_10
        t11 = m10 * M_nom_01 + cp * M_nom_11
        M_nom_00, M_nom_01, M_nom_10, M_nom_11 = (t00, t01, t10, t11)

    nominal_th = p_thick_nominal[i_layer]
    n_current = n_H if i_layer % 2 == 0 else n_L
    is_non_monotonic = False
    T_mono = np.zeros(5, dtype=np.float64)
    T_mono_nom = np.zeros(5, dtype=np.float64)  # meme balayage, empilement NOMINAL
    k_ext = -1  # indice du dernier extremum traverse (swing), -1 si aucun
    if nominal_th > 0.0001:
        for k in range(5):
            th_frac = k / 4.0 * nominal_th
            phi_c = TWO_PI_VAL / wl * n_current * th_frac
            cp_c, sp_c = (np.cos(phi_c), np.sin(phi_c))
            son_c = sp_c / n_current if abs(n_current) > 1e-09 else 0.0
            m01_c = +1j * son_c
            m10_c = +1j * n_current * sp_c
            a00 = cp_c * M_before_00 + m01_c * M_before_10
            a01 = cp_c * M_before_01 + m01_c * M_before_11
            a10 = m10_c * M_before_00 + cp_c * M_before_10
            a11 = m10_c * M_before_01 + cp_c * M_before_11
            denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
            if abs(denom) > 1e-09:
                T_mono[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)
            # meme point, mais sur la matrice NOMINALE : c'est la valeur que le
            # controleur ATTENDAIT de voir passer.
            b00 = cp_c * M_nom_00 + m01_c * M_nom_10
            b01 = cp_c * M_nom_01 + m01_c * M_nom_11
            b10 = m10_c * M_nom_00 + cp_c * M_nom_10
            b11 = m10_c * M_nom_01 + cp_c * M_nom_11
            den_n = b00 + n_Sub * b01 + b10 + n_Sub * b11
            if abs(den_n) > 1e-09:
                T_mono_nom[k] = 4.0 * n_Sub.real / (den_n.real**2 + den_n.imag**2)
        diffs = np.zeros(4, dtype=np.float64)
        for k in range(4):
            diffs[k] = T_mono[k + 1] - T_mono[k]
        flips = 0
        current_sign = 0.0
        if diffs[0] > 1e-09:
            current_sign = 1.0
        elif diffs[0] < -1e-09:
            current_sign = -1.0
        for k in range(1, 4):
            next_sign = 0.0
            if diffs[k] > 1e-09:
                next_sign = 1.0
            elif diffs[k] < -1e-09:
                next_sign = -1.0
            if next_sign != 0.0:
                if current_sign != 0.0 and next_sign != current_sign:
                    flips += 1
                current_sign = next_sign
        if flips > 0:
            is_non_monotonic = True
    # Niveau de declenchement FIGE, calcule sur le nominal et non sur le reel.
    target_nominal = 0.0
    if nominal_th > 0.0001:
        phi_t = TWO_PI_VAL / wl * n_current * nominal_th
        cp_t, sp_t = (np.cos(phi_t), np.sin(phi_t))
        son_t = sp_t / n_current if abs(n_current) > 1e-09 else 0.0
        mt01 = +1j * son_t
        mt10 = +1j * n_current * sp_t
        b00 = cp_t * M_nom_00 + mt01 * M_nom_10
        b01 = cp_t * M_nom_01 + mt01 * M_nom_11
        b10 = mt10 * M_nom_00 + cp_t * M_nom_10
        b11 = mt10 * M_nom_01 + cp_t * M_nom_11
        den_t = b00 + n_Sub * b01 + b10 + n_Sub * b11
        if abs(den_t) > 1e-09:
            target_nominal = 4.0 * n_Sub.real / (den_t.real**2 + den_t.imag**2)
    else:
        target_nominal = T_mono[4]

    # ------------------------------------------------------------------------
    # POEM — Percent of Optical Extrema Monitoring
    #
    #   T_POEM = (T_trigger - T_prev_TP) / (T_last_TP - T_prev_TP)      (Arsac
    #   these 2025, eq. 2.2 ; Zideluns et al., Opt. Express 29, 33398 (2021))
    #
    # Le point d'arret n'est PAS une valeur de transmission mais une FRACTION de
    # l'amplitude photometrique entre les deux derniers points tournants. La
    # fraction est pre-calculee sur le NOMINAL et figee avant le depot ; a
    # l'execution on la reporte sur les extrema REELLEMENT observes.
    #
    # Consequence, et c'est tout l'interet : si le signal reel subit une
    # distorsion affine T_reel = a*T_nom + b — derive de gain ou d'offset
    # photometrique, erreur d'indice, erreur d'epaisseur amont — alors
    # T_prev et T_last subissent la meme, et le niveau reporte vaut
    # a*T_trigger_nom + b. On s'arrete donc exactement a l'epaisseur voulue.
    # La compensation est obtenue par CHANGEMENT DE VARIABLE, pas par un
    # coefficient de reduction regle a la main.
    #
    # "If the current layer has less than two turning points, the virtual next
    #  turning points are used" : on prolonge le balayage au-dela de d_nom.
    #
    # Repli : si l'amplitude du swing est trop faible (< SWING_MIN, cf. les 4 %
    # d'amplitude de depart minimale de Zideluns et al.), POEM est mal
    # conditionne et on retombe sur la cible absolue figee.
    # 64 points et non 5 : localiser un point tournant a 5 points ne permet ni
    # de distinguer un extremum franc d'un epaulement, ni d'en compter plusieurs.
    # Cout : 64 evaluations de T par couche et par run, contre 8 auparavant.
    # BALAYAGE CONTINU SUR LA LONGUEUR DU BLOC, et non sur la seule couche
    # courante. Sans cela POEM ne capture que le swing intra-couche.
    #
    #   A longueur d'onde INCHANGEE le signal de monitoring est CONTINU d'une
    #   couche a l'autre : les points tournants deja traverses pendant les couches
    #   precedentes du bloc restent des mesures valides, exploitables pour recaler
    #   la couche courante. Au changement de lambda on repart sur un signal neuf
    #   et tout l'historique est perdu.
    #
    # C'est ce qui donne leur valeur aux blocs monochromatiques, ce que le P-PM
    # d'Arsac (chap. 4) exploite, et ce que Zideluns et al. (Opt. Express 29,
    # 33398, 2021) formulent ainsi : "self-compensation operates only at the
    # monitored wavelength and diminishes when layers are monitored at different
    # wavelengths".
    #
    # block_start_layer = indice de la premiere couche du bloc. Defaut -1 =
    # couche seule, ce qui preserve le comportement des appelants non modifies.
    NPTS = 64
    NPTS_PREV = 16
    MAX_LOOKBACK = 4
    D_SCAN = 3.0
    SWING_MIN = 0.04
    poem_ok = False
    T_prev_real = 0.0
    T_last_real = 0.0
    T_prev_nom = 0.0
    T_last_nom = 0.0
    if nominal_th > 0.0001:
        j0 = block_start_layer
        if j0 < 0 or j0 > i_layer:
            j0 = i_layer
        if i_layer - j0 > MAX_LOOKBACK:
            j0 = i_layer - MAX_LOOKBACK
        n_hist = (i_layer - j0) * NPTS_PREV
        n_tot = n_hist + NPTS
        Ts_r = np.zeros(n_tot, dtype=np.float64)
        Ts_n = np.zeros(n_tot, dtype=np.float64)
        R00, R01, R10, R11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
        Q00, Q01, Q10, Q11 = (1.0 + 0j, 0.0 + 0j, 0.0 + 0j, 1.0 + 0j)
        for j in range(j0):
            n_p = n_H if j % 2 == 0 else n_L
            ph1 = TWO_PI_VAL / wl * n_p * prev_thicknesses_sim[j]
            c1, s1 = (np.cos(ph1), np.sin(ph1))
            so1 = s1 / n_p if abs(n_p) > 1e-09 else 0.0
            a0 = c1 * R00 + 1j * so1 * R10
            a1 = c1 * R01 + 1j * so1 * R11
            a2 = 1j * n_p * s1 * R00 + c1 * R10
            a3 = 1j * n_p * s1 * R01 + c1 * R11
            R00, R01, R10, R11 = (a0, a1, a2, a3)
            ph2 = TWO_PI_VAL / wl * n_p * p_thick_nominal[j]
            c2, s2 = (np.cos(ph2), np.sin(ph2))
            so2 = s2 / n_p if abs(n_p) > 1e-09 else 0.0
            b0 = c2 * Q00 + 1j * so2 * Q10
            b1 = c2 * Q01 + 1j * so2 * Q11
            b2 = 1j * n_p * s2 * Q00 + c2 * Q10
            b3 = 1j * n_p * s2 * Q01 + c2 * Q11
            Q00, Q01, Q10, Q11 = (b0, b1, b2, b3)
        idx = 0
        for j in range(j0, i_layer):
            n_j = n_H if j % 2 == 0 else n_L
            d_rj = prev_thicknesses_sim[j]
            d_nj = p_thick_nominal[j]
            for k in range(1, NPTS_PREV + 1):
                f = k / NPTS_PREV
                p3 = TWO_PI_VAL / wl * n_j * (f * d_rj)
                c3, s3 = (np.cos(p3), np.sin(p3))
                o3 = s3 / n_j if abs(n_j) > 1e-09 else 0.0
                z1 = (c3 * R00 + 1j * o3 * R10) + n_Sub * (c3 * R01 + 1j * o3 * R11)
                z1 = z1 + (1j * n_j * s3 * R00 + c3 * R10) + n_Sub * (1j * n_j * s3 * R01 + c3 * R11)
                if abs(z1) > 1e-09:
                    Ts_r[idx] = 4.0 * n_Sub.real / (z1.real**2 + z1.imag**2)
                p4 = TWO_PI_VAL / wl * n_j * (f * d_nj)
                c4, s4 = (np.cos(p4), np.sin(p4))
                o4 = s4 / n_j if abs(n_j) > 1e-09 else 0.0
                z2 = (c4 * Q00 + 1j * o4 * Q10) + n_Sub * (c4 * Q01 + 1j * o4 * Q11)
                z2 = z2 + (1j * n_j * s4 * Q00 + c4 * Q10) + n_Sub * (1j * n_j * s4 * Q01 + c4 * Q11)
                if abs(z2) > 1e-09:
                    Ts_n[idx] = 4.0 * n_Sub.real / (z2.real**2 + z2.imag**2)
                idx += 1
            p3 = TWO_PI_VAL / wl * n_j * d_rj
            c3, s3 = (np.cos(p3), np.sin(p3))
            o3 = s3 / n_j if abs(n_j) > 1e-09 else 0.0
            g0 = c3 * R00 + 1j * o3 * R10
            g1 = c3 * R01 + 1j * o3 * R11
            g2 = 1j * n_j * s3 * R00 + c3 * R10
            g3 = 1j * n_j * s3 * R01 + c3 * R11
            R00, R01, R10, R11 = (g0, g1, g2, g3)
            p4 = TWO_PI_VAL / wl * n_j * d_nj
            c4, s4 = (np.cos(p4), np.sin(p4))
            o4 = s4 / n_j if abs(n_j) > 1e-09 else 0.0
            h0 = c4 * Q00 + 1j * o4 * Q10
            h1 = c4 * Q01 + 1j * o4 * Q11
            h2 = 1j * n_j * s4 * Q00 + c4 * Q10
            h3 = 1j * n_j * s4 * Q01 + c4 * Q11
            Q00, Q01, Q10, Q11 = (h0, h1, h2, h3)
        d_max = D_SCAN * nominal_th
        step_s = d_max / (NPTS - 1)
        for k in range(NPTS):
            d_k = k * step_s
            phi_k = TWO_PI_VAL / wl * n_current * d_k
            cpk, spk = (np.cos(phi_k), np.sin(phi_k))
            sonk = spk / n_current if abs(n_current) > 1e-09 else 0.0
            e01 = +1j * sonk
            e10 = +1j * n_current * spk
            r00 = cpk * R00 + e01 * R10
            r01 = cpk * R01 + e01 * R11
            r10 = e10 * R00 + cpk * R10
            r11 = e10 * R01 + cpk * R11
            dr = r00 + n_Sub * r01 + r10 + n_Sub * r11
            if abs(dr) > 1e-09:
                Ts_r[idx] = 4.0 * n_Sub.real / (dr.real**2 + dr.imag**2)
            q00 = cpk * Q00 + e01 * Q10
            q01 = cpk * Q01 + e01 * Q11
            q10 = e10 * Q00 + cpk * Q10
            q11 = e10 * Q01 + cpk * Q11
            dn = q00 + n_Sub * q01 + q10 + n_Sub * q11
            if abs(dn) > 1e-09:
                Ts_n[idx] = 4.0 * n_Sub.real / (dn.real**2 + dn.imag**2)
            idx += 1
        # Points tournants du signal NOMINAL : c'est lui qui definit la
        # strategie, le signal reel ne fait que fournir les valeurs mesurees.
        idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))
        tp_a = -1
        tp_b = -1
        for k in range(1, n_tot - 1):
            dl = Ts_n[k] - Ts_n[k - 1]
            dr2 = Ts_n[k + 1] - Ts_n[k]
            if (dl > 1e-12 and dr2 < -1e-12) or (dl < -1e-12 and dr2 > 1e-12):
                if k <= idx_nom_stop or tp_b < 0:
                    tp_a = tp_b
                    tp_b = k
        if tp_a >= 0 and tp_b >= 0:
            T_prev_nom = Ts_n[tp_a]
            T_last_nom = Ts_n[tp_b]
            T_prev_real = Ts_r[tp_a]
            T_last_real = Ts_r[tp_b]
            amp_nom = T_last_nom - T_prev_nom
            amp_real = T_last_real - T_prev_real
            if abs(amp_nom) > SWING_MIN and abs(amp_real) > SWING_MIN:
                poem_ok = True

    if poem_ok:
        # fraction figee, calculee sur le nominal (eq. 2.2)
        p_poem = (target_nominal - T_prev_nom) / (T_last_nom - T_prev_nom)
        # reportee sur les extrema reellement observes
        target_level = T_prev_real + p_poem * (T_last_real - T_prev_real)
    else:
        target_level = target_nominal

    target_T_noisy = target_level + noise_val_precalc
    th_points = np.array([max(0.1, nominal_th - probe_offset), nominal_th, nominal_th + probe_offset])
    T_points = np.zeros(3)
    for k in range(3):
        d = th_points[k]
        phi = TWO_PI_VAL / wl * n_current * d
        cp, sp = (np.cos(phi), np.sin(phi))
        son = sp / n_current if abs(n_current) > 1e-09 else 0.0
        m01 = +1j * son
        m10 = +1j * n_current * sp
        a00 = cp * M_before_00 + m01 * M_before_10
        a01 = cp * M_before_01 + m01 * M_before_11
        a10 = m10 * M_before_00 + cp * M_before_10
        a11 = m10 * M_before_01 + cp * M_before_11
        denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
        if abs(denom) > 1e-09:
            T_points[k] = 4.0 * n_Sub.real / (denom.real**2 + denom.imag**2)
    a_quad, b_quad, c_quad = fit_parabola_vertex_3points(th_points, T_points)
    calc_thick = _solve_quadratic_target(a_quad, b_quad, c_quad, target_T_noisy, nominal_th)
    error_raw = calc_thick - nominal_th
    dyn_encounter = 0.0
    if nominal_th > 0.0001:
        dyn_encounter = np.max(T_mono) - np.min(T_mono)
    if is_non_monotonic:
        if non_monotonic_mode == NON_MONOTONIC_MODE_REJECT:
            return (nominal_th + 1000000.0, dyn_encounter)
        # non_monotonic_factor N'EST PLUS APPLIQUE.
        #
        # Il divisait l'erreur par une constante (defaut 2.0) des qu'un extremum
        # etait traverse. C'etait la forme reduite du gain d'information apporte
        # par le swing — un pansement, rendu necessaire par le fait que le modele
        # ne pouvait PAS produire ce gain lui-meme : la cible etant recalculee sur
        # l'empilement reel, error_raw ne contenait que du bruit local et il n'y
        # avait rien a corriger.
        #
        # Avec la cible figee et POEM, le gain du swing est desormais STRUCTUREL :
        # il varie avec le contraste reellement observe et avec le nombre
        # d'extrema, au lieu d'etre le meme pour une couche qui frole un extremum
        # et une couche qui en traverse trois. Le diviser en plus reviendrait a
        # compter deux fois le meme effet.
        #
        # Le parametre est conserve dans la signature pour ne pas casser les six
        # sites d'appel ; il ne sert plus qu'au mode REJECT ci-dessus.
        return (max(0.0, nominal_th + error_raw), dyn_encounter)
    return (max(0.0, nominal_th + error_raw), dyn_encounter)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_at_layer(
    wl: float, n_layer, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11, d: float
) -> float:
    """

    Compute front-side T at end of a single layer (same convention as simulate_growth_kernel).

    Used to compute dT/dd for converting thickness noise (nm) to transmission noise.

    """
    if wl < 0.1:
        return 0.0
    TWO_PI_VAL = TWO_PI
    phi = TWO_PI_VAL / wl * n_layer * d
    cp, sp = (np.cos(phi), np.sin(phi))
    son = sp / n_layer if abs(n_layer) > 1e-09 else 0.0
    m01 = +1j * son
    m10 = +1j * n_layer * sp
    a00 = cp * M_before_00 + m01 * M_before_10
    a01 = cp * M_before_01 + m01 * M_before_11
    a10 = m10 * M_before_00 + cp * M_before_10
    a11 = m10 * M_before_01 + cp * M_before_11
    denom = a00 + n_Sub * a01 + a10 + n_Sub * a11
    if abs(denom) > 1e-09:
        return float(4.0 * np.real(n_Sub) / (denom.real**2 + denom.imag**2))
    return 0.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_T_front_profile(
    wl: float,
    n_layer,
    n_Sub,
    M_before_00,
    M_before_01,
    M_before_10,
    M_before_11,
    d_array: np.ndarray,
) -> np.ndarray:
    """T de face avant sur TOUTE une grille d'epaisseurs, en un seul appel.

    Meme calcul que ``compute_T_front_at_layer``, point par point : la boucle est
    simplement passee du cote compile. L'arithmetique est identique, donc les
    resultats le sont bit a bit.

    Motif : ``_compute_theoretical_layer_profile`` echantillonnait la courbe T(d)
    tous les nanometres depuis Python, soit ~200 franchissements de la frontiere
    Python->njit par couche, repetes pour chaque strategie et chaque tirage de
    Monte-Carlo. Le calcul lui-meme est negligeable devant ce cout de dispatch.
    """
    n = d_array.shape[0]
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = compute_T_front_at_layer(
            wl, n_layer, n_Sub, M_before_00, M_before_01, M_before_10, M_before_11, d_array[i]
        )
    return out


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def compute_dT_dd_kernel(
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    p_thick_arr: np.ndarray,
    M_before_all: np.ndarray,
    h_nm: float,
) -> np.ndarray:
    """dT/dd par difference centree, pour toutes les couches en un appel.

    Transposition directe de la boucle finale de ``_compute_dT_dd_per_layer`` :
    memes operations dans le meme ordre, donc memes resultats bit a bit. Elle
    faisait deux appels njit par couche depuis Python ; sur un empilement de
    quarante couches, evalue pour chaque strategie candidate, le cout de dispatch
    depassait celui du calcul.
    """
    num_layers = p_thick_arr.shape[0]
    dT_dd = np.zeros(num_layers, dtype=np.float64)

    for i in range(num_layers):
        wl_i = layer_wavelengths[i]

        if wl_i < 0.1:
            dT_dd[i] = 1e-6
            continue

        n_current = n_H_vals[i] if (i % 2) == 0 else n_L_vals[i]
        n_Sub = n_Sub_vals[i]
        d_nom = p_thick_arr[i]

        M00 = M_before_all[i, 0, 0]
        M01 = M_before_all[i, 0, 1]
        M10 = M_before_all[i, 1, 0]
        M11 = M_before_all[i, 1, 1]

        d_plus = d_nom + h_nm
        d_minus = max(0.1, d_nom - h_nm)

        T_plus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_plus)
        T_minus = compute_T_front_at_layer(wl_i, n_current, n_Sub, M00, M01, M10, M11, d_minus)

        denom = d_plus - d_minus
        dT_dd[i] = (T_plus - T_minus) / denom if denom > 1e-9 else 1e-6

    return dT_dd


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def prepare_dynamics_data_kernel(
    wls_array: np.ndarray,
    all_wls: np.ndarray,
    nominal_matrix_cache: np.ndarray,
    n_H_arr: np.ndarray,
    n_L_arr: np.ndarray,
    n_Sub_arr: np.ndarray,
    i_layer: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """

    Parallel preparation of data for dynamics calculation.

    """
    n = len(wls_array)
    n_layer_array = np.empty(n, dtype=np.complex128)
    n_sub_array = np.empty(n, dtype=np.complex128)
    M_before_stack = np.empty((n, 2, 2), dtype=np.complex128)
    for i in prange(n):
        wl = wls_array[i]
        if i_layer % 2 == 0:
            n_layer_array[i] = n_H_arr[i]
        else:
            n_layer_array[i] = n_L_arr[i]
        n_sub_array[i] = n_Sub_arr[i]
        M_before_stack[i, 0, 0] = 1.0
        M_before_stack[i, 0, 1] = 0.0
        M_before_stack[i, 1, 0] = 0.0
        M_before_stack[i, 1, 1] = 1.0
        if i_layer > 0:
            idx = np.searchsorted(all_wls, wl)
            if idx >= len(all_wls):
                idx = len(all_wls) - 1
            elif idx > 0:
                diff_curr = abs(wl - all_wls[idx])
                diff_prev = abs(wl - all_wls[idx - 1])
                if diff_prev < diff_curr:
                    idx = idx - 1
            M_before_stack[i, 0, 0] = nominal_matrix_cache[i_layer - 1, idx, 0, 0]
            M_before_stack[i, 0, 1] = nominal_matrix_cache[i_layer - 1, idx, 0, 1]
            M_before_stack[i, 1, 0] = nominal_matrix_cache[i_layer - 1, idx, 1, 0]
            M_before_stack[i, 1, 1] = nominal_matrix_cache[i_layer - 1, idx, 1, 1]
    return (n_layer_array, n_sub_array, M_before_stack)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores):
    """

    Compute TMM dynamics: peak-to-peak range of T(d) over layer growth.

    For each wavelength, T(d) is evaluated at thickness steps from 0 to

    nominal thickness. The dynamics metric is T_max - T_min (not endpoint

    delta). Returns dynamics, t_init, t_final, t_min (min T over growth).

    Precision adapts to input dtypes via Numba JIT.

    """
    n_wls = wls.shape[0]
    n_steps = thicknesses.shape[0]
    dynamics = np.empty(n_wls, dtype=np.float64)
    t_init = np.empty(n_wls, dtype=np.float64)
    t_final = np.empty(n_wls, dtype=np.float64)
    t_min = np.empty(n_wls, dtype=np.float64)
    I_VAL = +1j
    for wl_idx in prange(n_wls):
        wl = wls[wl_idx]
        n_layer = n_layers[wl_idx]
        n_sub = n_subs[wl_idx]
        M_before_00 = M_befores[wl_idx, 0, 0]
        M_before_01 = M_befores[wl_idx, 0, 1]
        M_before_10 = M_befores[wl_idx, 1, 0]
        M_before_11 = M_befores[wl_idx, 1, 1]
        T_min_val = 2.0
        T_max = -1.0
        T_start = 0.0
        T_end = 0.0
        for step_idx in range(n_steps):
            thickness = thicknesses[step_idx]
            if wl < 0.1:
                T_current = 0.0
            else:
                phi = TWO_PI / wl * n_layer * thickness
                cp, sp = (np.cos(phi), np.sin(phi))
                son = sp / n_layer if abs(n_layer) > 1e-09 else 0.0
                m01 = I_VAL * son
                m10 = I_VAL * n_layer * sp
                a00 = cp * M_before_00 + m01 * M_before_10
                a01 = cp * M_before_01 + m01 * M_before_11
                a10 = m10 * M_before_00 + cp * M_before_10
                a11 = m10 * M_before_01 + cp * M_before_11
                denom = a00 + n_sub * a01 + a10 + n_sub * a11
                if abs(denom) > 1e-09:
                    T_current = 4.0 * np.real(n_sub) / (denom.real**2 + denom.imag**2)
                else:
                    T_current = 0.0
            if step_idx == 0:
                T_start = T_current
            if step_idx == n_steps - 1:
                T_end = T_current
            if T_current < T_min_val:
                T_min_val = T_current
            if T_current > T_max:
                T_max = T_current
        dynamics[wl_idx] = T_max - T_min_val
        t_init[wl_idx] = T_start
        t_final[wl_idx] = T_end
        t_min[wl_idx] = T_min_val
    return (dynamics, t_init, t_final, t_min)


@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")
def update_run_states_kernel(
    p_thick_nom_arr: np.ndarray,
    i_layer: int,
    prev_stacks: np.ndarray,
    best_wl: float,
    nH,
    nL,
    nSub,
    offset_val: float,
    noise_values: np.ndarray,
    factor_val: float,
    non_monotonic_mode: int = NON_MONOTONIC_MODE_ATTENUATE,
):
    """Parallel update of simulation states for next layer."""
    num_runs = prev_stacks.shape[0]
    updates = np.empty(num_runs, dtype=np.float64)
    for r in prange(num_runs):
        updates[r], _ = simulate_growth_kernel(
            p_thick_nom_arr,
            i_layer,
            prev_stacks[r],
            best_wl,
            nH,
            nL,
            nSub,
            offset_val,
            noise_values[r],
            factor_val,
            non_monotonic_mode,
        )
    return updates


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def calculate_detailed_growth(
    num_layers, p_thick_nominal, layer_wavelengths, n_H_arr, n_L_arr, n_Sub_arr, steps_per_layer_arr
):
    """

    Detailed growth simulation with exact physics.

    CRITICAL PHYSICS NOTE:

    This function computes T_total including INCOHERENT BACKSIDE reflection.

    T_val = (Tf * T_ext) / (1.0 - Rf * R_ext)

    Matches the "Real World" signal seen by the monitor.

    The expression is intentionally expanded inline (instead of routing through

    compute_RT_from_matrix) for step-wise growth performance. Keep formulas aligned.

    """
    if num_layers == 0:
        return (np.zeros(1), np.zeros(1), np.zeros(1))
    total_steps = np.sum(steps_per_layer_arr)
    total_points = total_steps + num_layers + 1
    x_points = np.empty(total_points)
    y_points = np.empty(total_points)
    layer_boundaries = np.empty(num_layers + 1)
    current_idx = 0
    cumulative_thick = 0.0
    layer_boundaries[0] = 0.0
    F00 = 1.0 + 0j
    F01 = 0.0 + 0j
    F10 = 0.0 + 0j
    F11 = 1.0 + 0j
    R00 = 1.0 + 0j
    R01 = 0.0 + 0j
    R10 = 0.0 + 0j
    R11 = 1.0 + 0j
    prev_wl = -1.0
    for i_layer in range(num_layers):
        target_th = p_thick_nominal[i_layer]
        current_wl = layer_wavelengths[i_layer]
        if current_wl < 0.1:
            current_wl = 1500.0
        n_l_target = n_H_arr[i_layer] if i_layer % 2 == 0 else n_L_arr[i_layer]
        n_s = n_Sub_arr[i_layer]
        nsr = n_s.real
        R_ext = ((nsr - 1.0) / (nsr + 1.0)) ** 2
        T_ext = 1.0 - R_ext
        if i_layer > 0 and abs(current_wl - prev_wl) > 0.001:
            F00 = 1.0 + 0j
            F01 = 0.0 + 0j
            F10 = 0.0 + 0j
            F11 = 1.0 + 0j
            R00 = 1.0 + 0j
            R01 = 0.0 + 0j
            R10 = 0.0 + 0j
            R11 = 1.0 + 0j
            k0 = TWO_PI / current_wl
            for j in range(i_layer):
                dj = p_thick_nominal[j]
                nj = n_H_arr[i_layer] if j % 2 == 0 else n_L_arr[i_layer]
                phi = k0 * nj * dj
                cp = np.cos(phi)
                isp = +1j * np.sin(phi)
                mj01 = isp / nj if abs(nj) > 1e-09 else 0j
                mj10 = isp * nj
                t00 = cp * F00 + mj01 * F10
                t01 = cp * F01 + mj01 * F11
                t10 = mj10 * F00 + cp * F10
                t11 = mj10 * F01 + cp * F11
                F00, F01, F10, F11 = (t00, t01, t10, t11)
                t00 = R00 * cp + R01 * mj10
                t01 = R00 * mj01 + R01 * cp
                t10 = R10 * cp + R11 * mj10
                t11 = R10 * mj01 + R11 * cp
                R00, R01, R10, R11 = (t00, t01, t10, t11)
        k0_curr = TWO_PI / current_wl
        denom_f = F00 + n_s * F01 + F10 + n_s * F11
        denom_r = n_s * R00 + n_s * R01 + R10 + R11
        if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
            Tf = 4.0 * nsr / (denom_f.real**2 + denom_f.imag**2)
            num_r = n_s * R00 + n_s * R01 - R10 - R11
            Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)
            T_val = Tf * T_ext / (1.0 - Rf * R_ext)
        else:
            T_val = 0.0
        x_points[current_idx] = cumulative_thick
        y_points[current_idx] = T_val
        current_idx += 1
        steps = steps_per_layer_arr[i_layer]
        step_sz = target_th / steps
        for s in range(1, steps + 1):
            d_partial = step_sz * s
            phi = k0_curr * n_l_target * d_partial
            cp = np.cos(phi)
            isp = +1j * np.sin(phi)
            mj01 = isp / n_l_target if abs(n_l_target) > 1e-09 else 0j
            mj10 = isp * n_l_target
            ft00 = cp * F00 + mj01 * F10
            ft01 = cp * F01 + mj01 * F11
            ft10 = mj10 * F00 + cp * F10
            ft11 = mj10 * F01 + cp * F11
            rt00 = R00 * cp + R01 * mj10
            rt01 = R00 * mj01 + R01 * cp
            rt10 = R10 * cp + R11 * mj10
            rt11 = R10 * mj01 + R11 * cp
            denom_f = ft00 + n_s * ft01 + ft10 + n_s * ft11
            denom_r = n_s * rt00 + n_s * rt01 + rt10 + rt11
            if abs(denom_f) > 1e-12 and abs(denom_r) > 1e-12:
                Tf = 4.0 * nsr / (denom_f.real**2 + denom_f.imag**2)
                num_r = n_s * rt00 + n_s * rt01 - rt10 - rt11
                Rf = (num_r.real**2 + num_r.imag**2) / (denom_r.real**2 + denom_r.imag**2)
                val = Tf * T_ext / (1.0 - Rf * R_ext)
            else:
                val = 0.0
            x_points[current_idx] = cumulative_thick + d_partial
            y_points[current_idx] = val
            current_idx += 1
        phi_full = k0_curr * n_l_target * target_th
        cp = np.cos(phi_full)
        isp = +1j * np.sin(phi_full)
        mf01 = isp / n_l_target if abs(n_l_target) > 1e-09 else 0j
        mf10 = isp * n_l_target
        t00 = cp * F00 + mf01 * F10
        t01 = cp * F01 + mf01 * F11
        t10 = mf10 * F00 + cp * F10
        t11 = mf10 * F01 + cp * F11
        F00, F01, F10, F11 = (t00, t01, t10, t11)
        t00 = R00 * cp + R01 * mf10
        t01 = R00 * mf01 + R01 * cp
        t10 = R10 * cp + R11 * mf10
        t11 = R10 * mf01 + R11 * cp
        R00, R01, R10, R11 = (t00, t01, t10, t11)
        cumulative_thick += target_th
        layer_boundaries[i_layer + 1] = cumulative_thick
        prev_wl = current_wl
    return (x_points[:current_idx], y_points[:current_idx], layer_boundaries)
