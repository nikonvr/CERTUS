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

# ── NON-TERMINATING DEPOSITION SENTINELS, DECOMPOSED BY CAUSE ────────────────
#
# THE THREE CAUSES PREVIOUSLY RETURNED THE SAME VALUE, CREATING A DIAGNOSTIC BLINDSPOT.
#
# `simulate_growth_kernel` inflated thickness by 1e6 in three unrelated situations.
# As long as they were conflated, it was impossible to know WHY a deposition did not finish.
#
# Values are multiples of 1e6 and nominal thickness remains added, so:
#   - any consumer checking `val > 1e5` counts exact same crashes as before.
#   - cause is readable via `int(val // 1e6)` without knowing nominal thickness.
#
# The three diagnostic causes correspond to:
# CRASH_LEVEL_UNREACHABLE answers "is target level reachable?",
# CRASH_TP_MISCOUNT answers "do we count expected turning points?".
CRASH_SENTINEL_MIN: float = 100000.0
CRASH_SENTINEL_UNIT: float = 1000000.0
#: Target stopping level is not bracketed by signal before next extremum.
CRASH_LEVEL_UNREACHABLE: int = 1
#: Turning point count on real deposition differs from expected.
CRASH_TP_MISCOUNT: int = 2
#: Non-monotonic T(d) and REJECT mode requested: candidate is rejected.
CRASH_NON_MONOTONIC: int = 3
from .certus_strat_math import (
    check_extrema_proximity,
    calculate_extrema_distances,
    fit_parabola_vertex_3points,
    _seeded_noise_sample,
    _solve_quadratic_target,
    _calc_T_from_matrix,
    _calc_T_added_layer,
)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def detect_turning_points(
    Ts: np.ndarray,
    n_tot: int,
    idx_stop: int,
    start_is_tp: bool,
    hysteresis: float,
) -> tuple[int, int, int]:
    """Compte les points tournants d'un signal de monitoring et rend les deux derniers.

    Returns ``(n_tp, tp_a, tp_b)``: the number of extrema located at or before ``idx_stop``,
    then the indices of the last two retained (``-1`` if absent). Same selection convention
    as legacy code: beyond ``idx_stop`` an extremum is only retained if none has been retained yet.

    SINGLE FUNCTION FOR BOTH REAL AND NOMINAL SIGNALS - THIS IS ESSENTIAL.
    Divergent counting between real and nominal signals is one of the primary crash modes.
    Detecting extrema with two separately written loops risks algorithmic divergence rather than
    physical divergence.

    ``hysteresis`` — DETECTION RULE, in units of T:

        0.0  Legacy rule: an extremum is declared as soon as the difference between
             two consecutive samples changes sign beyond a NUMERICAL guard of 1e-12.
             This is not a physical rule, and produces a crash rate that DOES NOT DEPEND ON NOISE:
             1.47% per layer at sigma = 5e-8 vs 1.30% at real instrument noise. Where the monitoring
             signal lacks dynamic range (e.g. rejection band where T_front is 1e-5 to 1e-7),
             noisy counting diverges from clean counting regardless of noise magnitude.

        > 0  HYSTERESIS detector (modeling real hardware controllers): tracks the current extremum,
             and only DECLARES it when the signal has deviated from it by more than ``hysteresis``.
             A ripple smaller than this threshold produces no turning point.

             The returned index is that of the extremum ITSELF, not the threshold crossing time:
             the physical machine records the extreme value it observed, not the time it realized
             it had passed it.

             THIS THRESHOLD DERIVES FROM NOISE, NOT AN AMPLITUDE CRITERION.
             The 4% starting amplitude rule from Zideluns p. 112 is a wavelength PRE-SELECTION
             heuristic — a way to guess in advance what Monte-Carlo measures directly.
             This detection threshold should not borrow its value from that heuristic.

             The governing quantity is reading noise, which is MEASURED:
             On the OMS 5100, the signal fluctuates from 45.5 to 45.55% T (peak-to-peak amplitude
             `trigger_tolerance` = 0.05 points). The draw is bounded to +/- this amplitude
             (truncated N(0, A/3) law), so the maximum apparent deviation from noise alone is 2A:

                 hysteresis >= 2 x trigger_tolerance / 100
                 -> noise alone can NEVER fabricate a false turning point reversal.

    The threshold applies to the NOMINAL signal as well. It represents what the strategy
    EXPECTS to count; evaluating it with a different rule than the physical machine
    would induce artificial per-layer counting divergence.
    """
    tp_a = -1
    tp_b = -1
    n_tp = 0
    if start_is_tp:
        n_tp += 1
        tp_b = 0

    if hysteresis <= 0.0:
        for k in range(1, n_tot - 1):
            dl = Ts[k] - Ts[k - 1]
            dr = Ts[k + 1] - Ts[k]
            if (dl > 1e-15 and dr < -1e-15) or (dl < -1e-15 and dr > 1e-15):
                if k <= idx_stop:
                    n_tp += 1
                if k <= idx_stop or tp_b < 0:
                    tp_a = tp_b
                    tp_b = k
        return (n_tp, tp_a, tp_b)

    # Hysteresis detector. Simultaneously tracks current maximum and minimum;
    # `dirn` is 0 until direction is established by first threshold crossing.
    maxv = Ts[0]
    minv = Ts[0]
    maxi = 0
    mini = 0
    dirn = 0
    for k in range(1, n_tot):
        v = Ts[k]
        if v > maxv:
            maxv = v
            maxi = k
        if v < minv:
            minv = v
            mini = k
        emit = -1
        if dirn >= 0 and maxv - v > hysteresis:
            emit = maxi
            dirn = -1
            minv = v
            mini = k
        elif dirn <= 0 and v - minv > hysteresis:
            emit = mini
            dirn = 1
            maxv = v
            maxi = k
        # Index 0 is already declared by `start_is_tp`: do not double count.
        if emit < 0 or (start_is_tp and emit == 0):
            continue
        if emit <= idx_stop:
            n_tp += 1
        if emit <= idx_stop or tp_b < 0:
            tp_a = tp_b
            tp_b = emit
    return (n_tp, tp_a, tp_b)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def next_turning_point_after(Ts: np.ndarray, n_tot: int, i_start: int, hysteresis: float) -> int:
    """Indice du premier point tournant situe apres ``i_start``, ou ``n_tot - 1`` si aucun.

    Sert a borner la fenetre du test d'atteignabilite du niveau : au-dela du prochain
    extremum, le signal repart et le niveau vise ne sera jamais atteint.

    **Meme regle de detection que ``detect_turning_points``**, et il le faut : sans cela
    un micro-extremum fabrique par le bruit juste apres l'arret tronquerait la fenetre
    et provoquerait un plantage que la machine ne subirait pas — exactement l'artefact
    que l'hysteresis existe pour supprimer.
    """
    if hysteresis <= 0.0:
        for k in range(i_start + 1, n_tot - 1):
            dl = Ts[k] - Ts[k - 1]
            dr = Ts[k + 1] - Ts[k]
            if (dl > 1e-12 and dr < -1e-12) or (dl < -1e-12 and dr > 1e-12):
                return k
        return n_tot - 1

    if i_start + 1 >= n_tot:
        return n_tot - 1
    maxv = Ts[i_start]
    minv = Ts[i_start]
    maxi = i_start
    mini = i_start
    dirn = 0
    for k in range(i_start + 1, n_tot):
        v = Ts[k]
        if v > maxv:
            maxv = v
            maxi = k
        if v < minv:
            minv = v
            mini = k
        if dirn >= 0 and maxv - v > hysteresis:
            if maxi > i_start:
                return maxi
            dirn = -1
            minv = v
            mini = k
        elif dirn <= 0 and v - minv > hysteresis:
            if mini > i_start:
                return mini
            dirn = 1
            maxv = v
            maxi = k
    return n_tot - 1


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
    signal_noise_scale: float = 0.0,
    signal_noise_seed: int = 0,
    signal_noise_run: int = 0,
    tp_hysteresis: float = 0.0,
    affine_scale: float = 1.0,
    affine_offset: float = 0.0,
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

        signal_noise_scale: AXE 1.1 — echelle du bruit de LECTURE applique au
            signal de monitoring REEL ``Ts_r``, en unites de T (0..1), AVANT la
            detection des points tournants, la lecture des ancres POEM et le test
            d'atteignabilite du niveau. 0.0 = desactive, et le chemin de calcul est
            alors mot pour mot celui d'avant ce parametre. Voir le bloc
            « BRUIT DE LECTURE » plus bas.

        signal_noise_seed: graine du flux de bruit de lecture. Doit etre une
            fonction de la seule configuration de tirage (graine, niveau de bruit)
            et JAMAIS de la strategie evaluee : c'est ce qui preserve les nombres
            aleatoires communs.

        signal_noise_run: indice du tirage Monte-Carlo. Meme exigence.

        tp_hysteresis: AXE 1.2 — LA REGLE DE DETECTION DE POINT TOURNANT, en unites de
            T. 0.0 = regle historique (changement de signe au-dela d'un garde numerique
            de 1e-12), qui n'est pas une regle physique. > 0 = detecteur a hysteresis.
            Voir ``detect_turning_points``, qui contient la derivation du seuil a partir
            du bruit mesure — et pourquoi ce n'est PAS le critere des 4 % de Zideluns.

            🔴 SANS CE PARAMETRE, `signal_noise_scale` N'EST PAS MESURABLE : le taux de
            plantage qu'il produit ne depend pas de sigma (1,47 % par couche a
            sigma = 5e-8 contre 1,30 % au sigma reel), donc il ne mesure pas le bruit.

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
    # ---- BRUIT DE LECTURE SUR LE SIGNAL DE MONITORING (axe 1.1) --------------
    #
    # `noise_val_precalc` n'a longtemps bruite qu'UN SEUL point de toute la
    # chaine : la comparaison d'arret (`target_T_noisy`, plus bas). Or `Ts_r`, le
    # signal « reel », sert a trois choses de plus, et aucune n'etait bruitee :
    #
    #   - la DETECTION des points tournants           -> « voit-on les TP ? »
    #   - la lecture des ANCRES POEM (T_prev, T_last) -> « POEM est-il gratuit ? »
    #   - le test d'ATTEIGNABILITE du niveau          -> « atteint-on le niveau ? »
    #
    # Les trois questions du juge de paix recevaient donc la reponse « toujours, et
    # exactement », qui n'a aucun contenu : les extrema etaient localises sur une
    # courbe TMM parfaite. En particulier POEM reporte sa fraction figee sur les
    # extrema REELLEMENT OBSERVES — T_prev_real et T_last_real sont censes etre des
    # MESURES. On lui donnait le benefice du recalage sans lui en faire payer le
    # cout : le niveau vise valant T_prev + p.(T_last - T_prev), deux ancres
    # portant chacune une erreur d'ecart-type sigma donnent
    #
    #     Var[cible] = sigma^2 . [ (1-p)^2 + p^2 ]   + sigma^2 sur la lecture d'arret
    #
    # soit un bruit effectif de sigma.sqrt(1 + (1-p)^2 + p^2) : x1,22 a p = 0,5, et
    # jusqu'a x1,41 quand le trigger tombe sur une ancre. POEM echange un BIAIS
    # (l'erreur non compensee) contre une VARIANCE (deux mesures de plus), et le
    # modele ne comptait que le benefice — il favorisait donc structurellement les
    # strategies qui s'appuient sur beaucoup d'ancres, ou sur des ancres anciennes
    # heritees du bloc, puisqu'il les supposait parfaites.
    #
    # 🔴 NOMBRES ALEATOIRES COMMUNS — la contrainte a ne pas perdre.
    #
    # Le tirage est une FONCTION PURE de (graine, couche balayee, tirage, indice de
    # point). Aucune entree ne depend de la strategie : ni la longueur d'onde, ni le
    # decoupage en blocs, ni `block_start_layer`. Deux strategies comparees sur le
    # meme (graine, tirage) voient donc EXACTEMENT le meme bruit de lecture, et leur
    # difference de score reste imputable a la strategie seule.
    #
    # C'est pourquoi le tirage n'est pas materialise en tableau : un tableau indexe
    # a plat sur le balayage se DESALIGNERAIT d'une strategie a l'autre, puisque la
    # longueur de l'historique `n_hist` depend du decoupage en blocs. Le generateur
    # `_seeded_noise_sample` — deja en production pour la nucleation, meme loi
    # N(0, 1/3) tronquee a +/-1 que le tirage Sobol de la Phase B — est appele avec
    # des indices ALIGNES SUR LA PHYSIQUE :
    #
    #   historique de la couche j, point k    ->  (group=j,       elem=k)
    #   balayage de la couche courante, k     ->  (group=i_layer, elem=NPTS_PREV+k)
    #
    # Le premier indexage est invariant en `i_layer` : toutes les couches d'un meme
    # bloc relisent le passe de la couche j AVEC LE MEME BRUIT. C'est l'invariant
    # physique — la machine a enregistre une mesure, elle ne la remesure pas.
    #
    # ⚠ CE QUI RESTE NON FIDELE, et qu'il faut avoir en tete pour lire les taux de
    # plantage produits. Le nombre d'extrema PARASITES qu'un bruit de lecture
    # fabrique depend de la DENSITE d'echantillonnage du balayage, qui est ici un
    # choix numerique (NPTS = 64 sur 3x l'epaisseur, NPTS_PREV = 16 sur 1x) et non
    # la cadence de la machine. L'historique est donc echantillonne quatre fois plus
    # grossierement que la couche courante, et un meme point physique n'a pas le
    # meme bruit selon qu'il est lu comme « couche courante » ou comme « historique ».
    # Modeliser la cadence et le temps d'integration est l'axe 1.2, pas celui-ci.
    #
    # NE SONT PAS BRUITES, et c'est voulu :
    #   - `Ts_n` : le signal NOMINAL est la strategie, calculee hors ligne avant le
    #     depot. Il n'y a personne pour la mesurer.
    #   - `T_mono` : grandeur de conception (dynamique, monotonie), pas une lecture.
    #   - les trois points `T_points` de l'inversion parabolique : ils ne sont pas
    #     une mesure mais la resolution de T_reel(d) = target_T_noisy. Le bruit de
    #     la lecture d'arret est deja porte, et seulement porte, par
    #     `noise_val_precalc`.
    NPTS = 64
    NPTS_PREV = 16
    MAX_LOOKBACK = 4
    D_SCAN = 3.0
    SWING_MIN = 0.04
    apply_signal_noise = signal_noise_scale > 0.0
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
                if apply_signal_noise:
                    # group = j : le passe de la couche j porte le MEME bruit pour
                    # toutes les couches du bloc qui le relisent.
                    Ts_r[idx] += signal_noise_scale * _seeded_noise_sample(
                        signal_noise_seed, j, signal_noise_run, k - 1, True
                    )
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
            if apply_signal_noise:
                # elem decale de NPTS_PREV : plage disjointe de celle de l'historique.
                g_noise = i_layer
                e_noise = NPTS_PREV + k
                # 🔴 LE POINT DUPLIQUE. `d_k = 0` de la couche courante EST le
                # dernier point de l'historique du bloc : dans les deux cas c'est
                # T de l'empilement arrete a la fin de la couche i_layer - 1. UNE
                # SEULE MESURE, donc UN SEUL tirage.
                #
                # 📏 Y tirer deux bruits independants coutait tres cher, et de
                # facon trompeuse. Le signal PROPRE y a un palier de longueur
                # nulle : `dl = 0`, donc dans la bande morte a 1e-12, donc aucun
                # extremum detecte. Deux tirages independants rendaient cette
                # difference non nulle et de signe aleatoire, ce qui fabriquait un
                # extremum parasite a PILE OU FACE — donc avec une probabilite
                # INDEPENDANTE DE SIGMA. Mesure sur le dichroique 48 couches,
                # historique nominal et bruit d'arret nul :
                #
                #     profondeur d'historique  0      1      2      4
                #     plantage                0,63 % 27,4 % 28,1 % 28,1 %
                #     et a profondeur 4 :  sigma/10 -> 28,5 %,  2 sigma -> 28,1 %
                #
                # Les deux signatures designent le meme defaut : le saut apparait
                # des qu'il existe UN historique (donc une jonction) et ne croit
                # plus avec la profondeur (il n'y a qu'une jonction, quelle que
                # soit la profondeur) ; et il ne depend pas de sigma parce qu'un
                # signe aleatoire ne depend pas de l'amplitude.
                if k == 0 and n_hist > 0:
                    g_noise = i_layer - 1
                    e_noise = NPTS_PREV - 1
                Ts_r[idx] += signal_noise_scale * _seeded_noise_sample(
                    signal_noise_seed, g_noise, signal_noise_run, e_noise, True
                )
            q00 = cpk * Q00 + e01 * Q10
            q01 = cpk * Q01 + e01 * Q11
            q10 = e10 * Q00 + cpk * Q10
            q11 = e10 * Q01 + cpk * Q11
            dn = q00 + n_Sub * q01 + q10 + n_Sub * q11
            if abs(dn) > 1e-09:
                Ts_n[idx] = 4.0 * n_Sub.real / (dn.real**2 + dn.imag**2)
            idx += 1

        if affine_scale != 1.0 or affine_offset != 0.0:
            for k_aff in range(n_tot):
                Ts_r[k_aff] = affine_scale * Ts_r[k_aff] + affine_offset
        # DEUX detections distinctes, et c'est essentiel.
        #
        # La FRACTION POEM est pre-calculee hors ligne sur le signal NOMINAL :
        # c'est la strategie, elle est figee avant le depot.
        #
        # Les ANCRES, elles, sont les points tournants que la machine COMPTE sur
        # le signal REEL. Si les erreurs amont deplacent ou font disparaitre un
        # extremum, la machine n'en compte pas le meme nombre et ancre POEM sur
        # les mauvais : c'est un mode de defaillance DISCRET, invisible a un
        # critere de RMSE, et il ne peut apparaitre que si l'on detecte sur le
        # reel. Detecter sur le nominal reviendrait a doter la machine d'une
        # connaissance qu'elle n'a pas.
        idx_nom_stop = n_hist + int(round((NPTS - 1) / D_SCAN))
        # ---- LE SUBSTRAT NU EST UN POINT TOURNANT, ET IL ETAIT IGNORE ----------
        #
        # Physicien, 2026-08-05 : « pour la couche 1 on demarre la couche sur un
        # turning point, mais ca c'est obligatoire ».
        #
        # C'est exact et c'est automatique. Pour une couche unique sur substrat,
        # R(d) = A + B.cos(2.delta) avec delta = 2.pi.n.d/lambda, donc
        # dR/dd proportionnel a sin(2.delta), qui S'ANNULE en d = 0. Verifie
        # numeriquement (n_H = 2,35, substrat 1,52, lambda = 500 nm) : pente en
        # d = 0 de -8,0e-4 par nm contre -7,9e-3 au milieu du quart d'onde, soit
        # dix fois moins — le residu vient de la difference finie sur un pas de
        # 2,5 nm, la derivee vraie est nulle.
        #
        # Or la boucle de detection commence a k = 1 : un extremum de BORD est
        # structurellement invisible. Consequence mesuree sur l'exemple, dont le
        # premier multiplicateur vaut 1,556 (donc idx_nom_stop ~ 33) :
        #
        #     extrema detectes    [21, 42]        d = 53,2 et 106,4 nm
        #     k = 21 <= 33        tp_b = 21, tp_a reste -1
        #     k = 42 >  33        rejete car tp_b >= 0
        #     => tp_a = -1  =>  poem_ok = FALSE sur la couche 0
        #
        # La couche 0 retombait donc sur la cible absolue, sans compensation. Et
        # cela expliquait qu'elle n'ait qu'UNE seule longueur d'onde survivante
        # sur ~51 scannees, d'ou l'absence de lambda commune avec la couche 1,
        # d'ou le repli force_monolayer qui fabrique une arete invalide.
        #
        # 🔴 CETTE ANCRE EST LA PLUS FIABLE DE TOUTES. En d = 0 sur la couche 0,
        # l'empilement reel et l'empilement nominal sont le MEME objet — le
        # substrat nu. T_prev_real = T_prev_nom exactement, sans erreur amont
        # possible, et la machine mesure ce niveau avant meme de commencer.
        #
        # Condition volontairement etroite : uniquement la premiere couche de
        # l'empilement (i_layer == 0, donc j0 == 0). Pour un bloc demarrant plus
        # haut, d = 0 de sa premiere couche n'est PAS un extremum en general :
        # le sous-empilement deja depose n'a aucune raison d'y etre stationnaire.
        start_is_tp = i_layer == 0 and j0 == 0
        # Le signal REEL : ce que la machine compte.
        n_tp_real, tp_a, tp_b = detect_turning_points(
            Ts_r, n_tot, idx_nom_stop, start_is_tp, tp_hysteresis
        )
        # Le signal NOMINAL : ce que la strategie attend d'elle. MEME regle de
        # detection, imperativement — les deux comptages servent aussi a detecter la
        # DIVERGENCE du nombre d'extrema, qui est l'un des deux modes de plantage, et
        # deux regles differentes en fabriqueraient une a chaque couche. Compter le
        # bord d'un cote et pas de l'autre aurait le meme effet.
        n_tp_nom, tp_a_n, tp_b_n = detect_turning_points(
            Ts_n, n_tot, idx_nom_stop, start_is_tp, tp_hysteresis
        )
        if tp_a >= 0 and tp_b >= 0 and tp_a_n >= 0 and tp_b_n >= 0:
            # fraction : ancrages NOMINAUX  |  report : ancrages REELS mesures
            T_prev_nom = Ts_n[tp_a_n]
            T_last_nom = Ts_n[tp_b_n]
            T_prev_real = Ts_r[tp_a]
            T_last_real = Ts_r[tp_b]
            amp_nom = T_last_nom - T_prev_nom
            amp_real = T_last_real - T_prev_real
            swing_min_thresh = affine_scale * SWING_MIN
            if abs(amp_nom) > SWING_MIN and abs(amp_real) > swing_min_thresh:
                poem_ok = True

    if poem_ok:
        # fraction figee, calculee sur le nominal (eq. 2.2)
        p_poem = (target_nominal - T_prev_nom) / (T_last_nom - T_prev_nom)
        # reportee sur les extrema reellement observes
        target_level = T_prev_real + p_poem * (T_last_real - T_prev_real)
    else:
        target_level = affine_scale * target_nominal + affine_offset

    target_T_noisy = target_level + noise_val_precalc

    # ---- DEFAILLANCE DURE : le niveau d'arret n'est jamais atteint ----------
    #
    # Cas tres defavorable signale en salle : si l'arret theorique tombe JUSTE
    # AVANT un point tournant, une erreur amont peut faire tourner le signal
    # avant d'avoir atteint la valeur visee. La machine attend un niveau qui ne
    # viendra jamais et le depot part en vrille. Ce n'est pas une perte de
    # precision, c'est un PLANTAGE — un evenement discret, invisible a un critere
    # de RMSE tant qu'on ne le detecte pas explicitement.
    #
    # C'est pour cela que s'arreter APRES un point tournant est bien plus sur :
    # l'extremum est deja compte, le signal s'en eloigne de facon monotone, et le
    # niveau est fatalement atteint. C'est aussi la justification de l'asymetrie
    # de check_extrema_proximity — zone interdite 3x plus large AVANT un point
    # tournant qu'APRES.
    #
    # On modelise ici la defaillance telle qu'elle se produit : si le niveau vise
    # n'est pas encadre par le signal reel entre le debut de la couche et le
    # prochain extremum, le run est perdu.
    #
    # ⚠ CE TEST NE DOIT PAS DEPENDRE DE poem_ok. Il l'a fait, et c'etait un trou.
    #
    # Qu'un niveau soit atteignable ou non est une question de PHYSIQUE du signal,
    # pas de la strategie d'ancrage employee pour le calculer. Garder la detection
    # derriere `poem_ok` la desactivait justement dans les cas ou POEM est mal
    # conditionne — swing sous SWING_MIN, moins de deux points tournants — qui sont
    # precisement les plus exposes.
    #
    # Mesure sur example/example_strat/JSON-strat-example.json, 48 couches x 51
    # longueurs d'onde de balayage, erreur amont de +2 nm, bruit nul :
    #   plantage detecte                         :  0,21 %
    #   repli MUTIQUE sur le sommet (disc < 0)   :  6,68 %   <- 30 fois plus
    # Ces 6,68 % sortaient de _solve_quadratic_target par sa branche
    # `discriminant < 0` (certus_strat_math.py:207), qui renvoie le sommet de la
    # parabole sans rien signaler : erreur mediane 5,2 nm, maximum 29 nm, la ou
    # 0,05 nm vaut deja moins d'un atome. Le taux verifie ne dependait PAS de
    # probe_offset (6,63 % a 0,5 nm, 6,88 % a 10 nm) : ce n'etait pas un artefact
    # du fit, mais bien la defaillance physique, non comptee.
    if nominal_th > 0.0001:
        i_lay0 = n_hist
        i_stop = idx_nom_stop
        # borne haute : prochain extremum reel apres l'arret, sinon fin du balayage.
        # Meme regle de detection que le comptage, cf. next_turning_point_after.
        i_end = next_turning_point_after(Ts_r, n_tot, i_stop, tp_hysteresis)
        t_lo = Ts_r[i_lay0]
        t_hi = Ts_r[i_lay0]
        for k in range(i_lay0, i_end + 1):
            if Ts_r[k] < t_lo:
                t_lo = Ts_r[k]
            if Ts_r[k] > t_hi:
                t_hi = Ts_r[k]
        # ✅ AUCUNE TOLERANCE ICI, ET C'EST VOULU.
        #
        # J'ai cru un moment qu'il fallait tolerer un depassement de l'ordre du
        # bruit, au motif qu'un empilement quart d'onde monitore a sa propre
        # longueur d'onde de centrage plantait a 100 %. C'etait une erreur de ma
        # part : ce 100 % est le BON resultat.
        #
        # A QWOT exact l'arret tombe sur le point tournant, ou dT/dd = 0 : un
        # niveau n'a plus aucune sensibilite a l'epaisseur, et la moitie des
        # realisations du bruit place la cible au-dela de l'extremum, ou elle ne
        # sera jamais atteinte. C'est exactement pour cela qu'on ne monitore pas
        # un QWOT a sa lambda_0 par coupure de niveau — et c'est le travail de
        # STRAT que d'aller chercher ailleurs. check_extrema_proximity existe
        # pour la meme raison.
        if target_T_noisy < t_lo - 1e-12 or target_T_noisy > t_hi + 1e-12:
            # niveau jamais atteint : depot non terminable
            return (
                nominal_th + CRASH_LEVEL_UNREACHABLE * CRASH_SENTINEL_UNIT,
                np.max(T_mono) - np.min(T_mono),
            )
        # Comptage d'extrema divergent entre nominal et reel : la machine
        # n'ancre pas POEM sur les memes points tournants que la strategie.
        # Celui-ci, en revanche, RESTE conditionne a poem_ok : sans POEM il n'y a
        # pas d'ancrage sur des points tournants, donc rien qui puisse diverger.
        if poem_ok and n_tp_real != n_tp_nom:
            return (
                nominal_th + CRASH_TP_MISCOUNT * CRASH_SENTINEL_UNIT,
                np.max(T_mono) - np.min(T_mono),
            )
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
            return (nominal_th + CRASH_NON_MONOTONIC * CRASH_SENTINEL_UNIT, dyn_encounter)
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
    block_start_layer: int = -1,
    signal_noise_scale: float = 0.0,
    signal_noise_seed: int = 0,
    tp_hysteresis: float = 0.0,
):
    """Parallel update of simulation states for next layer.

    ``block_start_layer`` doit valoir CELUI DE LA LONGUEUR D'ONDE RETENUE. Les
    etats propages ici deviennent l'historique sur lequel la couche suivante sera
    jugee : les evaluer sans l'historique du bloc alors que les candidates l'ont
    ete avec produirait une Phase A incoherente avec elle-meme.

    ``signal_noise_scale`` / ``signal_noise_seed`` : bruit de lecture du signal de
    monitoring (axe 1.1, cf. ``simulate_growth_kernel``). Ils doivent valoir CEUX
    DE LA VALIDATION DES CANDIDATES, pour la meme raison que ``block_start_layer``.
    L'indice de tirage passe au noyau est ``r``, le meme que celui qui a servi a
    juger les candidates.
    """
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
            block_start_layer,
            signal_noise_scale,
            signal_noise_seed,
            r,
            tp_hysteresis,
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
