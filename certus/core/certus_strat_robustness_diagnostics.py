"""CERTUS STRAT ROBUSTNESS - the layer diagnostics: margin profile, critical layer, forced layers, worst swing, witness resets (moved out of certus_strat_robustness.py, S5.2)."""

from typing import Any

import numpy as np

#: 👤 The cause is named in PHYSICAL WORDS, never by its sentinel. `CRASH_TP_MISCOUNT`
#: tells a chamber operator nothing about what to watch; "ripple too faint to be seen"
#: does. Decided 2026-08-10.
_CAUSE_WORDS = {
    "level": "niveau d'arret hors d'atteinte",
    "missed": "ondulation trop faible pour etre vue",
    "fabricated": "point tournant fabrique par le bruit",
}


#: Above this many multiples of A a margin carries no ranking information: the draws are
#: bounded, so the event is impossible and one impossibility does not beat another. Kept
#: well above the 2 A verdict threshold so the boundary itself stays visible.
_MARGIN_REPORT_CEILING_A = 5.0


def _margin_profile_sparse(
    margin_profile: dict[str, np.ndarray], noise_amp: float
) -> dict[str, dict[str, float]]:
    """Per-layer margins, in multiples of A, keeping only what can ever matter.

    Sparse on purpose. A healthy stack has most layers far from any failure, so a dense
    48-long list per cause per strategy would be mostly `null` -- weight without
    information, and 228 strategies of it. Absence of a layer therefore reads as "not
    constrained here", which is the honest statement.

    ⚠️ Rounded to 3 decimals: the margin inherits the ~6 % Monte-Carlo dispersion of the
    run (17-26), so further digits are noise dressed as precision.
    """
    if noise_amp <= 0.0:
        return {}
    out: dict[str, dict[str, float]] = {}
    for cause, arr in margin_profile.items():
        hits = {
            str(i): round(float(v) / noise_amp, 3)
            for i, v in enumerate(arr)
            if np.isfinite(v) and v / noise_amp < _MARGIN_REPORT_CEILING_A
        }
        if hits:
            out[cause] = hits
    return out


def _critical_layer(margin_profile: dict[str, np.ndarray], noise_amp: float) -> dict[str, Any]:
    """The layer that will give way first, its cause, and its margin in multiples of A.

    🔑 WHY A MARGIN AND NOT A RATE. On this stack every strategy reads 0 crashes out of
    150 draws, which says p < 2 % and nothing more. A rate cannot rank what never
    failed. A margin is continuous, always defined, and it designates the binding layer
    even when the yield is a perfect 100 %.

    🔴 AND WHY MULTIPLES OF A. The draws of this model are BOUNDED -- reading noise
    lives in +/-A, the corridor respects |a|+|b| <= delta_max. So a margin larger than
    the largest possible perturbation does not mean "unlikely", it means the event
    CANNOT HAPPEN. A23 fixes the reporting rule that follows: beyond 2 A one writes
    "impossible", never a probability. Writing "0.1 %" there would be false, and false
    in the direction that makes a good strategy be discarded.

    ⚠️ `inf` means "this cause never constrained this layer", which is not the same as
    a large margin and is why it is filtered rather than averaged.
    """
    if noise_amp <= 0.0:
        return {}
    best_key, best_layer, best_margin = "", -1, np.inf
    for key, arr in margin_profile.items():
        if arr.size == 0:
            continue
        finite = np.isfinite(arr)
        if not finite.any():
            continue
        idx = int(np.argmin(np.where(finite, arr, np.inf)))
        val = float(arr[idx])
        if val < best_margin:
            best_key, best_layer, best_margin = key, idx, val
    if best_layer < 0:
        return {}
    in_a = best_margin / noise_amp
    # Multiplicity matters as much as the minimum: one layer at 0.6 A is not the same
    # profile as twelve under 1 A, and an operator reads that difference immediately.
    n_below_2a = int(sum(
        int(np.count_nonzero(np.isfinite(arr) & (arr < 2.0 * noise_amp)))
        for arr in margin_profile.values()
    ))
    return {
        "layer": best_layer,                 # 0-based, as everywhere in the kernel
        "cause": _CAUSE_WORDS.get(best_key, best_key),
        "margin_in_A": in_a,
        # 🔴 The rule that is not negotiable: bounded draws mean p = 0 EXACTLY beyond
        # the largest possible perturbation, so no probability is quoted there.
        "verdict": "PEUT ECHOUER" if in_a <= 2.0 else "impossible",
        "n_layers_below_2A": n_below_2a,
    }


def _phase_a_forced_layers(params: dict[str, Any]) -> dict[str, Any]:
    """How many layers Phase A had NO admissible wavelength for -- 17-37.

    When no candidate meets the crash tolerance on a layer, Phase A keeps the least
    bad one and logs a warning. That is the right behaviour -- returning nothing would
    stop the search -- but it means the wavelength was **not chosen, it was forced**,
    and until now nothing said so beyond a per-layer log line.

    🔴 WHY THIS MATTERS ENOUGH TO CARRY IN EVERY RESULT. Measured on 2026-08-11, at a
    corridor of 0.010 on seed 77: 108 candidates offered, 103 forbidden, a median of
    ONE survivor per layer, and 32 of 48 layers on the fallback -- at a minimum
    observed crash rate of 0.7 %, seven times the tolerance. Phase B then found that
    strategy crashes 100 % of the time. And the final result announced a winner with a
    score and a SEEL, indistinguishable from a healthy run.

    A strategy built on 32 forced layers is not comparable to a freely chosen one. This
    is a run-level property: every strategy of a given Phase A inherits the same forced
    layers, so it qualifies the whole candidate pool, not one candidate.
    """
    stats = params.get("phase_a_admissibility_stats") or []
    if not stats:
        return {}
    forced = [int(s.get("layer", 0)) for s in stats if s.get("fallback_on_min_crash")]
    return {
        "n_forced": len(forced),
        "n_layers": len(stats),
        "layers": forced,                       # 1-based, as the admissibility census is
    }


def _worst_layer_swing(results_per_noise: list[dict[str, Any]]) -> dict[str, Any]:
    """Poorest optical swing across layers, and where it sits.

    The batch already returns the average dynamic range per layer; it was stored and
    never read. The MINIMUM over layers is the quantity that binds: 14-5 states that
    the trigger is precise in proportion to the swing, so the layer with the poorest
    swing is the one whose stopping level is most exposed to reading noise.

    Read at the NOMINAL noise level only. Mixing noise levels here would compare a
    strategy against itself under three different machines -- and the swing is a
    property of the signal, not of the noise.
    """
    for entry in results_per_noise:
        dyns = entry.get("avg_dynamics")
        if not dyns:
            continue
        arr = np.asarray(dyns, dtype=np.float64)
        if arr.size == 0:
            continue
        idx = int(np.argmin(arr))
        return {
            "layer": idx,          # 0-based, as everywhere in the kernel
            "swing": float(arr[idx]),
            "median_swing": float(np.median(arr)),
            "n_below_swing_min": int(np.count_nonzero(arr < 0.04)),  # SWING_MIN
        }
    return {}


#: At most this many Rate variants per strategy, and the DEEPEST boundaries win.
#: 👤 asked for the trial "on the 10 best strategies", not on everything: an unbounded
#: expansion costs a factor 6 on the whole Monte-Carlo for candidates nobody asked about.
def _resolve_witness_resets(raw: Any) -> list[int]:
    """MULTIPLE-TESTGLASS: accepts a list, or a string separated by `;` or `,`.

    🔑 WHY THIS STRING FORM EXISTS. 👤, 2026-08-22: *"a user does not know at the start
    whether the multiple testglass will be needed, so it must be addable"*. For an
    orchestrator to arm it without writing a configuration file, it has to go through the
    override channel -- which carries SCALARS only. A string is therefore the only
    vehicle, and this resolver turns it into a list.

    ⚠️ The `;` separator is preferred to `,` because the override parser of
    `probe_blocs_vs_plantage.py` already splits on commas: a list written with commas
    would be chopped up before it even got here. Both are accepted anyway, so that a
    hand-written configuration file surprises nobody.

    🔒 INERT BY DEFAULT: absent, empty or unreadable returns `[]`, which reproduces the
    single-testglass behaviour BIT FOR BIT. This resolver therefore cannot change an
    existing measurement.
    """
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, str):
        morceaux = [m.strip() for m in raw.replace(";", ",").split(",")]
    elif isinstance(raw, (list, tuple)):
        morceaux = [str(m).strip() for m in raw]
    else:
        morceaux = [str(raw).strip()]
    out: list[int] = []
    for m in morceaux:
        if not m:
            continue
        try:
            v = int(float(m))
        except (TypeError, ValueError):
            continue
        # 🔴 Index 0 is meaningless and is dropped: layer 0 already grows on bare glass.
        if v > 0 and v not in out:
            out.append(v)
    return sorted(out)
