@njit(cache=True, fastmath=True, nogil=True)
def _calculate_RT_absorbing_sub_single(
    wavelength: float,
    n_film_real: float,
    n_film_imag: float,
    thickness_nm: float,
    n_sub_real: float,
    k_sub: float,
    D_sub_nm: float,
) -> tuple[float, float]:
    """Scalar: R+T for one layer on absorbing substrate (Beer-Lambert incoherent)."""

    if not np.isfinite(n_sub_real) or n_sub_real < 1.0:
        return np.nan, np.nan

    ns = complex(n_sub_real, 0.0)  # substrate optical index (real part only for TMM)

    n_film = complex(n_film_real, -n_film_imag)  # Macleod: n̂ = n - ik

    phi = (TWO_PI / wavelength) * n_film * thickness_nm

    cp = np.cos(phi)

    sp = np.sin(phi)

    if abs(n_film) < 1e-12:
        return np.nan, np.nan

    M01 = +1j * sp / n_film

    M10 = +1j * n_film * sp

    # --- Forward: Air -> Film -> Sub ---

    B = cp + M01 * ns

    C = M10 + cp * ns

    Y = B + C

    Y_mag_sq = Y.real * Y.real + Y.imag * Y.imag

    if Y_mag_sq < 1e-25:
        return 0.0, 0.0

    r_num = B - C

    R_front = (r_num.real * r_num.real + r_num.imag * r_num.imag) / Y_mag_sq

    T_front = 4.0 * ns.real / Y_mag_sq

    # --- Reverse: Sub -> Film -> Air (R_prime for denom) ---

    Bp = cp + M01

    Cp = M10 + cp

    Yp = ns * Bp + Cp

    Yp_mag_sq = Yp.real * Yp.real + Yp.imag * Yp.imag

    if Yp_mag_sq < 1e-25:
        R_prime = 0.0

        T_prime = 0.0

    else:
        rp_num = ns * Bp - Cp

        R_prime = (rp_num.real * rp_num.real + rp_num.imag * rp_num.imag) / Yp_mag_sq

        T_prime = 4.0 * ns.real / Yp_mag_sq

    # --- Backside interface Sub|Air (bare Fresnel, real ns for interface) ---

    r_b = (n_sub_real - 1.0) / (n_sub_real + 1.0)

    R_back = r_b * r_b

    T_back = 1.0 - R_back

    # --- Beer-Lambert attenuation through substrate bulk ---

    alpha = 4.0 * math.pi * k_sub / wavelength  # nm⁻¹

    att1 = math.exp(-alpha * D_sub_nm)  # single-pass

    att2 = att1 * att1  # double-pass

    denom = 1.0 - R_prime * R_back * att2

    if abs(denom) < 1e-12:
        denom = 1e-12

    R_total = R_front + (T_front * T_prime * R_back * att2) / denom

    T_total = (T_front * T_back * att1) / denom

    R_total = max(0.0, min(1.0, R_total))

    T_total = max(0.0, min(1.0, T_total))

    return R_total, T_total
