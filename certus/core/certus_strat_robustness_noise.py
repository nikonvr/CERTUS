"""CERTUS STRAT ROBUSTNESS - noise levels, resolution noise factor and the Sobol / stream seeds (moved out of certus_strat_robustness.py, S5.2)."""

import numpy as np
from typing import Any


def _parse_noise_factors(raw_factors: Any) -> list[float]:
    if isinstance(raw_factors, str):
        try:
            cleaned = raw_factors.replace("[", "").replace("]", "").strip()
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
        except Exception:
            return [0.5, 1.0, 2.0]
    if isinstance(raw_factors, list):
        return [float(x) for x in raw_factors]
    return [0.5, 1.0, 2.0]


#: 👤 Noise factor on A for each available monochromator slit, 2026-08-09.
#:
#: 🔴 A TABLE, NEVER A LAW, and the distinction is not pedantry. These four values are
#: 👤 *"estimated by me at feeling"* -- a modelling postulate like 9bis, not a
#: constructor specification. Fitting a power law to them would invent a model on
#: invented numbers, AND it would let the search propose slits the machine does not
#: have. Four settings, four table entries.
#:
#: ⚠️ Any conclusion drawn from these is physics only if it SURVIVES their uncertainty.
#: 12.7 requires a sensitivity control -- redo the comparison with /1.2 and x3 instead
#: of /1.5 and x5; if the winning resolution changes, the conclusion rests on a feeling
#: and that must be said in the same sentence.
RESOLUTION_NOISE_FACTOR: dict[float, float] = {5.0: 1.0 / 1.5, 2.0: 1.0, 1.0: 2.0, 0.5: 5.0}


# 👤 "and of course the index biases must always be active, it is the basis"
# (2026-08-12). The indices are PRESUPPOSED, known to +/-0.005 in absolute index units --
# 12.3. A default of 0 describes a machine whose materials are known exactly, which is
# not a machine. Like the slit bias and Rate, this breaks C1 deliberately: the historical
# path is `index_corridor: 0`, and every measurement taken before 2026-08-12 was taken
# there.
INDEX_CORRIDOR_DEFAULT: float = 0.005


def _resolution_noise_factor(params: dict[str, Any]) -> float:
    """Noise multiplier for the configured slit. 1.0 at the nominal 2 nm, hence C1.

    🔴 IT MULTIPLIES THE SAMPLE, NEVER THE SEED -- constraint C2, and the failure it
    prevents would be invisible. Folding the slit into the seed would make the four
    resolutions see four DIFFERENT random realisations, so the gap between them would no
    longer be attributable to the resolution. All four figures would look perfectly
    plausible. Scaling the amplitude keeps the draws identical and only their size
    changes.
    """
    raw = params.get("monochromator_resolution_nm")
    if raw is None:
        return 1.0
    try:
        slit = float(raw)
    except (TypeError, ValueError):
        return 1.0
    factor = RESOLUTION_NOISE_FACTOR.get(slit)
    if factor is None:
        # An unavailable slit is a configuration error, not something to interpolate:
        # a law over four estimated points would authorise settings the machine has not.
        raise ValueError(
            f"monochromator_resolution_nm={slit} is not one of "
            f"{sorted(RESOLUTION_NOISE_FACTOR)} -- the four values the machine offers. "
            "There is no law to interpolate between them (12.7)."
        )
    return factor


def _resolve_robustness_noise_levels(params: dict[str, Any]) -> list[float]:
    """Resolve robustness noise-level vector from STRAT params."""
    noise_factors = _parse_noise_factors(params.get("robustness_noise_factors", [0.5, 1.0, 2.0]))
    if params.get("thickness_tolerance_nm") is not None:
        base_tol = float(params.get("thickness_tolerance_nm"))  # type: ignore[arg-type]  # guarded by the `is not None` above
        return [base_tol * f * _resolution_noise_factor(params) for f in noise_factors]

    try:
        base_noise = float(params["reality_sim_params"]["trigger_tolerance"])
    except KeyError, TypeError:
        base_noise = float(params.get("trigger_tolerance", 0.5))
    return [base_noise * f * _resolution_noise_factor(params) for f in noise_factors]


_SOBOL_NOISE_CACHE: dict[tuple[int, int, int, int], np.ndarray] = {}


def _get_cached_sobol_noise(base_seed: int, noise_idx: int, num_runs: int, num_layers: int) -> np.ndarray:
    key = (base_seed, noise_idx, num_runs, num_layers)
    if key in _SOBOL_NOISE_CACHE:
        return _SOBOL_NOISE_CACHE[key]
        
    import math
    from scipy.stats import qmc, norm
    # Multiplicative mixing, NOT a sum.
    #
    # `base_seed + noise_idx` makes distinct pairs collide: the consensus
    # generates its seeds by `base_seed + i * stride` with a stride of 1 by default
    # (certus/utils/certus_strat_context.py:598 and :610), so (seed 42, level 1) and
    # (seed 43, level 0) both gave local_seed = 43 — the SAME noise.
    # The overlap is triangular and massive:
    #     3 seeds x 3 levels =  9 draws ->  5 distincts (44% lost)
    #     5 seeds x 4 levels = 20 draws ->  8 distincts (60% lost)
    #     8 seeds x 5 levels = 40 draws -> 12 distincts (70% lost)
    # Yet the consensus is supposed to average over INDEPENDENT seeds: sharing the
    # noise between members inflates their apparent agreement, thus overestimating robustness.
    #
    # The two constants are odd integers close to 2^32/phi and 2^16/phi:
    # they scatter the low-order bits, which are precisely the ones that varied
    # here (small and consecutive indices).
    #
    # NOTE: this fix changes the draws, so the robustness results are not
    # numerically comparable to before. It is inevitable — the old ones
    # were statistically biased.
    local_seed = (base_seed * 2_654_435_761 + noise_idx * 40_503) % (2**31)
    sobol_engine = qmc.Sobol(d=num_layers, seed=local_seed)
    n_pow2 = 2 ** math.ceil(math.log2(num_runs)) if num_runs > 0 else 0
    sobol_samples = sobol_engine.random(n=n_pow2)[:num_runs]
    
    # Inverse CDF transform (uniform to normal distribution N(0, 1/3))
    raw_noise = norm.ppf(sobol_samples, loc=0.0, scale=1.0 / 3.0)
    raw_noise = np.clip(raw_noise, -1.0, 1.0).astype(np.float64)
    
    _SOBOL_NOISE_CACHE[key] = raw_noise
    return raw_noise


def _signal_noise_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the READ noise stream of the monitoring signal (axis 1.1).

    🔴 IT DEPENDS ONLY ON THE DRAW CONFIGURATION, NEVER ON THE STRATEGY.
    This is the condition for common random numbers: two strategies evaluated
    at the same (seed, noise level) see exactly the same read noise,
    and the difference in their scores remains attributable to the strategy alone. The same achievement
    as `_get_cached_sobol_noise` protects for the stopping noise — `_strat_idx` is
    deliberately unused there.

    Multiplicative and non-additive mixing, for the reason explained in
    `_get_cached_sobol_noise`: the consensus generates its seeds by
    `base_seed + i * stride` with a stride of 1 by default, so a sum
    would collide (seed 42, level 1) and (seed 43, level 0).

    The final constant distances this stream from the nucleation one, which calls the
    same `_seeded_noise_sample` with an unshifted `seed_base`.
    """
    mixed = int(base_seed) * 2_246_822_519 + int(noise_idx) * 668_265_263 + 0x5F35_6495
    return mixed % (2**53)


def _affine_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the affine distortion stream (axis 1.1).

    🔴 IT DEPENDS ONLY ON THE DRAW CONFIGURATION, NEVER ON THE STRATEGY.
    This is the condition for common random numbers.
    """
    mixed = int(base_seed) * 3_266_489_917 + int(noise_idx) * 1_274_126_177 + 0x7E2A_8431
    return mixed % (2**53)


def _index_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the index uncertainty stream (T5)."""
    mixed = int(base_seed) * 2_654_435_761 + int(noise_idx) * 850_507 + 0x3F1B_79C5
    return mixed % (2**53)
