@njit(cache=True, fastmath=True, nogil=True)
def calculate_transmission_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub: complex,
) -> tuple[float, float]:
    """

    R_front + T_total (exact incoherent backside) for a single layer.

    Uses native complex arithmetic matching compute_TMM_generic convention.

    Returns:

        (R_front, T_total_with_backside)

    CRITICAL PHYSICS NOTE:

    This function explicitly INCLUDES incoherent backside reflection.

    It is designed for Standard Mode (Transparent substrate).

    DO NOT REMOVE THE BACKSIDE TERM.

    """

    if not np.isfinite(n_sub.real) or n_sub.real < 1.0:
        return np.nan, np.nan

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    ns = n_sub

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    # Layer matrix elements

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # M00 = M11 = cp

    # --- Forward: Air -> Film -> Sub ---

    # Air index = 1.0 (real)

    B = cp + M01 * ns

    C = M10 + cp * ns

    # Y = n0 * B + C = 1.0 * B + C

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    # r = (n0*B - C) / (n0*B + C)

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    # Transmittance into substrate (T_front)

    # T = 4 * Re(ns) * Re(n0) / |n0*B + C|^2

    # n0 = 1

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (for incoherent denominator) ---

    # Incident medium is Sub (ns), Exit is Air (1)

    # M_total = M_layer (same)

    # B' = M00 + M01 * n_exit = cp + M01

    # C' = M10 + M11 * n_exit = M10 + cp

    Bp = cp + M01

    Cp = M10 + cp

    # Y' = ns * B' + C'

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0

    else:
        # r' = (ns*B' - C') / (ns*B' + C')

        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq

    # --- Backside interface Sub|Air ---

    # r_b = (ns - 1) / (ns + 1)

    r_b_num = ns - 1.0

    r_b_den = ns + 1.0

    r_b = r_b_num / r_b_den

    R_sub = r_b.real * r_b.real + r_b.imag * r_b.imag

    # T_sub = 1 - R_sub (Assuming no absorption at interface itself, Fresnel)

    T_sub = 1.0 - R_sub

    # --- Exact incoherent combination ---

    # If substrate is absorbing, we should account for absorption in the substrate volume?

    # Standard formula T_total = T_front * T_back * exp(-alpha*d) / (1 - R_front_back * R_back * exp...)

    # Here we assume transparent substrate logic (exp terms = 1) but capable of handling n complex.

    # If thick absorbing substrate, T_total goes to 0 independently.

    # For now, keeping logic "incoherent sum" unmodified except for types.

    denom_incoh = 1.0 - R_prime * R_sub

    if abs(denom_incoh) < 1e-12:
        denom_incoh = 1e-12

    # T_total = (T_front * T_sub) / (1 - R' * R_sub)

    T_total = (T_front * T_sub) / denom_incoh

    # R_total = R_front + (T_front * T_prime * R_sub) / (1 - R' * R_sub)

    # T_prime (transmission stack from substrate side) = T_front (reciprocity for linear optics?)

    # Strictly T_front = (4 Re(ns) Re(n0)) / |D|^2.

    # T_prime = (4 Re(n0) Re(ns)) / |D'|^2.

    # D' is Y' = ns*B' + C'. D is Y = n0*B + C.

    # B' = cp + M01, C' = M10 + cp. B = cp + M01*ns, C = M10 + cp*ns.

    # For lossless films, |D|=|D'|. Absorption breaks this?

    # Let's verify T_prime calculate to be safe.

    # T_prime (Sub -> Air)

    # T' = 4 * Re(1) * Re(ns) / |Y'|^2 = 4 * ns.real / Yp_mag_sq

    T_prime = 4.0 * ns.real / Yp_mag_sq

    R_back_contribution = (T_front * T_prime * R_sub) / denom_incoh

    R_total = R_front + R_back_contribution

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total
