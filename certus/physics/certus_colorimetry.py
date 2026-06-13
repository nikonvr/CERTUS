import numpy as np
from numba import njit
import math


# COLORIMETRY


# =============================================================================


CIE_LAMBDA = np.arange(380, 781, 5, dtype=np.float64)


CIE_X = np.array(
    [
        0.0014,
        0.0022,
        0.0042,
        0.0076,
        0.0143,
        0.0232,
        0.0435,
        0.0776,
        0.1344,
        0.2148,
        0.3230,
        0.4479,
        0.5970,
        0.7621,
        0.9163,
        1.0263,
        1.0622,
        1.0456,
        1.0026,
        0.9564,
        0.9154,
        0.8634,
        0.7889,
        0.6954,
        0.5945,
        0.4900,
        0.3856,
        0.2899,
        0.2091,
        0.1484,
        0.1041,
        0.0734,
        0.0514,
        0.0358,
        0.0249,
        0.0172,
        0.0117,
        0.0081,
        0.0058,
        0.0045,
        0.0036,
        0.0029,
        0.0024,
        0.0020,
        0.0017,
        0.0014,
        0.0011,
        0.0009,
        0.0007,
        0.0005,
        0.0004,
        0.0003,
        0.0002,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


CIE_Y = np.array(
    [
        0.0000,
        0.0001,
        0.0001,
        0.0002,
        0.0004,
        0.0006,
        0.0012,
        0.0022,
        0.0040,
        0.0073,
        0.0129,
        0.0230,
        0.0380,
        0.0600,
        0.0910,
        0.1390,
        0.2080,
        0.3230,
        0.5030,
        0.7100,
        0.8620,
        0.9540,
        0.9950,
        0.9950,
        0.9520,
        0.8700,
        0.7570,
        0.6310,
        0.5030,
        0.3810,
        0.2650,
        0.1750,
        0.1170,
        0.0782,
        0.0526,
        0.0353,
        0.0231,
        0.0154,
        0.0106,
        0.0074,
        0.0053,
        0.0039,
        0.0029,
        0.0021,
        0.0016,
        0.0012,
        0.0008,
        0.0006,
        0.0004,
        0.0003,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


CIE_Z = np.array(
    [
        0.0065,
        0.0105,
        0.0201,
        0.0362,
        0.0679,
        0.1102,
        0.2074,
        0.3713,
        0.6456,
        1.0391,
        1.5281,
        2.0561,
        2.5861,
        3.0781,
        3.4828,
        3.7008,
        3.6551,
        3.4481,
        3.1870,
        2.9080,
        2.6480,
        2.3481,
        1.9961,
        1.6361,
        1.2880,
        0.9693,
        0.6934,
        0.4692,
        0.3162,
        0.2120,
        0.1419,
        0.0954,
        0.0640,
        0.0426,
        0.0283,
        0.0188,
        0.0125,
        0.0084,
        0.0057,
        0.0041,
        0.0031,
        0.0023,
        0.0018,
        0.0014,
        0.0011,
        0.0009,
        0.0006,
        0.0005,
        0.0003,
        0.0002,
        0.0002,
        0.0001,
        0.0001,
        0.0001,
        0.0001,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
        0.0000,
    ],
    dtype=np.float64,
)


D65 = np.array(
    [
        49.9755,
        52.3118,
        54.6482,
        68.7015,
        82.7549,
        87.1204,
        91.486,
        92.4589,
        93.4318,
        90.057,
        86.6823,
        95.7736,
        104.865,
        110.936,
        117.008,
        117.41,
        117.812,
        116.336,
        114.861,
        115.392,
        115.923,
        112.367,
        108.811,
        109.082,
        109.354,
        108.578,
        107.802,
        106.296,
        104.79,
        106.239,
        107.689,
        106.047,
        104.405,
        104.225,
        104.046,
        102.023,
        100.0,
        98.1671,
        96.3342,
        96.0611,
        95.788,
        92.2368,
        88.6856,
        89.3459,
        90.0062,
        89.8026,
        89.5991,
        88.6489,
        87.6987,
        85.4936,
        83.2886,
        83.4939,
        83.6992,
        81.863,
        80.0268,
        80.1207,
        80.2146,
        81.2462,
        82.2778,
        80.281,
        78.2842,
        74.0027,
        69.7213,
        70.6652,
        71.6091,
        72.979,
        74.349,
        67.9765,
        61.604,
        65.7448,
        69.8856,
        72.4863,
        75.087,
        69.3398,
        63.5927,
        55.0054,
        46.4182,
        56.6118,
        66.8054,
        65.0941,
        63.3828,
    ],
    dtype=np.float64,
)


XYZ_N = np.array([95.047, 100.0, 108.883], dtype=np.float64)


XYZ_TO_RGB = np.array(
    [
        [3.2404542, -1.5371385, -0.4985314],
        [-0.9692660, 1.8760108, 0.0415560],
        [0.0556434, -0.2040259, 1.0572252],
    ],
    dtype=np.float64,
)


D65_CIE_X = D65 * CIE_X


D65_CIE_Y = D65 * CIE_Y


D65_CIE_Z = D65 * CIE_Z


_denom_y = np.sum(D65_CIE_Y)


K_COLOR = 100.0 / _denom_y if _denom_y != 0 else 0.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _xyz_from_spectrum_kernel(
    R_interp: np.ndarray,
    D65_X: np.ndarray,
    D65_Y: np.ndarray,
    D65_Z: np.ndarray,
    k_color: float,
) -> tuple[float, float, float]:
    """JIT kernel for XYZ tristimulus computation."""

    X = 0.0

    Y = 0.0

    Z = 0.0

    for i in range(len(R_interp)):
        X += R_interp[i] * D65_X[i]

        Y += R_interp[i] * D65_Y[i]

        Z += R_interp[i] * D65_Z[i]

    return k_color * X, k_color * Y, k_color * Z


def xyz_from_spectrum(wls: np.ndarray, R: np.ndarray) -> np.ndarray:

    R_interp = np.interp(CIE_LAMBDA, wls, R)

    X, Y, Z = _xyz_from_spectrum_kernel(R_interp, D65_CIE_X, D65_CIE_Y, D65_CIE_Z, K_COLOR)

    return np.array([X, Y, Z])


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _lab_f(t: float) -> float:
    """CIE Lab f() function - JIT scalar."""

    delta = 6.0 / 29.0

    if t > delta * delta * delta:
        return t ** (1.0 / 3.0)

    return t / (3.0 * delta * delta) + 4.0 / 29.0


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _lab_f_inv(t: float) -> float:
    """CIE Lab f_inv() function - JIT scalar."""

    delta = 6.0 / 29.0

    if t > delta:
        return t * t * t

    return 3.0 * delta * delta * (t - 4.0 / 29.0)


def xyz_to_lab(xyz_val: np.ndarray) -> np.ndarray:

    xyz_norm = xyz_val / XYZ_N

    fx = _lab_f(xyz_norm[0])

    fy = _lab_f(xyz_norm[1])

    fz = _lab_f(xyz_norm[2])

    L = 116.0 * fy - 16.0

    a = 500.0 * (fx - fy)

    b = 200.0 * (fy - fz)

    return np.array([L, a, b])


def lab_to_xyz(lab_val: np.ndarray) -> np.ndarray:

    L, a, b = lab_val

    fy = (L + 16.0) / 116.0

    fx = a / 500.0 + fy

    fz = fy - b / 200.0

    xyz = XYZ_N * np.array([_lab_f_inv(fx), _lab_f_inv(fy), _lab_f_inv(fz)])

    return xyz


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _gamma_correct_scalar(c: float) -> float:
    """sRGB gamma correction - JIT scalar."""

    c_safe = max(c, 0.0)

    if c_safe <= 0.0031308:
        return 12.92 * c_safe

    return 1.055 * (c_safe ** (1.0 / 2.4)) - 0.055


def lab_to_rgb(lab_val: np.ndarray) -> np.ndarray:

    xyz = lab_to_xyz(lab_val)

    rgb_linear = XYZ_TO_RGB @ (xyz / 100.0)

    rgb_gamma = np.array(
        [
            _gamma_correct_scalar(rgb_linear[0]),
            _gamma_correct_scalar(rgb_linear[1]),
            _gamma_correct_scalar(rgb_linear[2]),
        ]
    )

    return np.clip(rgb_gamma * 255.0, 0.0, 255.0).astype(np.int32)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
    """CIE DeltaE 2000 - fully JIT-compiled."""

    L1 = lab1[0]

    a1 = lab1[1]

    b1 = lab1[2]

    L2 = lab2[0]

    a2 = lab2[1]

    b2 = lab2[2]

    C1 = np.sqrt(a1 * a1 + b1 * b1)

    C2 = np.sqrt(a2 * a2 + b2 * b2)

    C_avg = (C1 + C2) / 2.0

    C_avg7 = C_avg**7

    G = 0.5 * (1.0 - np.sqrt(C_avg7 / (C_avg7 + 25.0**7)))

    a1p = a1 * (1.0 + G)

    a2p = a2 * (1.0 + G)

    C1p = np.sqrt(a1p * a1p + b1 * b1)

    C2p = np.sqrt(a2p * a2p + b2 * b2)

    TWO_PI_VAL = 2.0 * np.pi

    h1p = np.arctan2(b1, a1p) % TWO_PI_VAL

    h2p = np.arctan2(b2, a2p) % TWO_PI_VAL

    dL = L2 - L1

    dC = C2p - C1p

    if C1p * C2p == 0.0:
        dh = 0.0

    else:
        diff = h2p - h1p

        if abs(diff) <= np.pi:
            dh = diff

        elif diff > np.pi:
            dh = diff - TWO_PI_VAL

        else:
            dh = diff + TWO_PI_VAL

    dH = 2.0 * np.sqrt(C1p * C2p) * np.sin(dh / 2.0)

    L_avg = (L1 + L2) / 2.0

    C_avgp = (C1p + C2p) / 2.0

    if C1p * C2p == 0.0:
        h_avgp = h1p + h2p

    else:
        if abs(h1p - h2p) <= np.pi:
            h_avgp = (h1p + h2p) / 2.0

        elif h1p + h2p < TWO_PI_VAL:
            h_avgp = (h1p + h2p + TWO_PI_VAL) / 2.0

        else:
            h_avgp = (h1p + h2p - TWO_PI_VAL) / 2.0

    T = (
        1.0
        - 0.17 * np.cos(h_avgp - np.pi / 6.0)
        + 0.24 * np.cos(2.0 * h_avgp)
        + 0.32 * np.cos(3.0 * h_avgp + np.pi / 30.0)
        - 0.20 * np.cos(4.0 * h_avgp - 63.0 * np.pi / 180.0)
    )

    L_avg_m50 = L_avg - 50.0

    SL = 1.0 + (0.015 * L_avg_m50 * L_avg_m50) / np.sqrt(20.0 + L_avg_m50 * L_avg_m50)

    SC = 1.0 + 0.045 * C_avgp

    SH = 1.0 + 0.015 * C_avgp * T

    C_avgp7 = C_avgp**7

    RC = 2.0 * np.sqrt(C_avgp7 / (C_avgp7 + 25.0**7))

    delta_theta = 30.0 * np.exp(-(((h_avgp * 180.0 / np.pi - 275.0) / 25.0) ** 2))

    RT = -RC * np.sin(2.0 * delta_theta * np.pi / 180.0)

    return np.sqrt((dL / SL) ** 2 + (dC / SC) ** 2 + (dH / SH) ** 2 + RT * (dC / SC) * (dH / SH))


# =============================================================================


# =========================================================================================
