"""A forced strategy must say so -- defect 17-37.

When no candidate wavelength meets the crash tolerance on a layer, Phase A keeps the
least bad one rather than returning nothing. That is the right call: an empty return
would stop the search. But the wavelength was then **not chosen, it was forced**, and
nothing downstream said so.

📏 Why it matters, measured 2026-08-11 at corridor 0.010 on seed 77:

    candidates offered                       108
    forbidden on crash                       103
    survivors, median over 48 layers           1
    layers on the least-bad fallback       32/48
    crash tolerance 0.001, min observed    0.007      <- seven times the tolerance

Phase B then found that strategy crashes 100 % of the time -- and the report announced
a winner, a score and a SEEL indistinguishable from a healthy run. The information was
in a per-layer log line and nowhere else.
"""

from __future__ import annotations

from certus.core.certus_strat_robustness import _phase_a_forced_layers


def test_no_stats_at_all_returns_empty():
    """Absent census must not be reported as 'zero forced'.

    The two are different claims: 'nothing was forced' and 'nobody looked'. Returning
    {} lets the report show an em dash rather than a reassuring 0.
    """
    assert _phase_a_forced_layers({}) == {}
    assert _phase_a_forced_layers({"phase_a_admissibility_stats": []}) == {}


def test_a_clean_run_reports_zero_forced():
    params = {"phase_a_admissibility_stats": [
        {"layer": i + 1, "survivors": 90} for i in range(48)
    ]}
    out = _phase_a_forced_layers(params)
    assert out["n_forced"] == 0
    assert out["n_layers"] == 48
    assert out["layers"] == []


def test_forced_layers_are_counted_and_named():
    """The count is not enough: WHICH layers were forced is the actionable part."""
    stats = [{"layer": i + 1, "survivors": 90} for i in range(48)]
    for idx in (34, 40, 46):                     # 0-based -> layers 35, 41, 47
        stats[idx]["fallback_on_min_crash"] = True
        stats[idx]["survivors"] = 1
    out = _phase_a_forced_layers({"phase_a_admissibility_stats": stats})
    assert out["n_forced"] == 3
    assert out["layers"] == [35, 41, 47]         # 1-based, as the census is
    assert out["n_layers"] == 48


def test_the_collapse_case_is_representable():
    """The real measurement: 32 of 48 layers forced. It must come out as 32, loudly."""
    stats = [{"layer": i + 1, "survivors": 1} for i in range(48)]
    for s in stats[:32]:
        s["fallback_on_min_crash"] = True
    out = _phase_a_forced_layers({"phase_a_admissibility_stats": stats})
    assert out["n_forced"] == 32
    assert out["n_forced"] / out["n_layers"] > 0.5, (
        "plus de la moitie des couches subies : le score de cette strategie n'est pas "
        "comparable a celui d'un run libre, et c'est tout l'objet de ce champ"
    )
