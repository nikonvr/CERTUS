"""ELITE wavelength histograms -- the instrument that separates PARENTS from GATE.

WHY THESE TESTS EXIST. Measured 2026-08-20 on `r75x2` at 2 nm: seed 77 yields 547
depositable strategies, ALL from ELITE, and 544 of them monitor layer 35 at 685 nm --
a wavelength absent from every one of seed 42's 1617 strategies. At seed 42 ELITE
generates 4226 candidates and retains none. The pre-existing counters say which gate
rejected; they cannot say which wavelengths were ever on the table, and that is what
decides whether to repair the parent selection or the gate.

The counting rule under test is the one that makes the log readable: a candidate counts
ONCE per DISTINCT wavelength. Getting that wrong would report block counts as candidate
counts -- a mis-scaled quantity, which is the failure mode this repository keeps paying
for.
"""

from __future__ import annotations

import logging

import pytest

from certus.core.certus_strat_consensus import (
    _crash_bucket,
    _elite_wl_histogram,
    _format_wl_histogram,
    _log_elite_wl,
)


def _strat(*wls: float) -> dict:
    """A strategy with one block per wavelength given, tiling contiguously."""
    return {
        "blocks": [
            {"start": i * 5, "end": (i + 1) * 5, "wavelength": wl}
            for i, wl in enumerate(wls)
        ]
    }


class TestEliteWlHistogram:
    def test_counts_each_wavelength_once(self):
        assert _elite_wl_histogram([_strat(685.0, 610.0)]) == {685.0: 1, 610.0: 1}

    def test_a_candidate_reusing_one_wavelength_counts_once(self):
        """Two blocks at 685 nm in the SAME candidate is one candidate, not two."""
        assert _elite_wl_histogram([_strat(685.0, 610.0, 685.0)]) == {685.0: 1, 610.0: 1}

    def test_sums_over_candidates(self):
        hist = _elite_wl_histogram([_strat(685.0), _strat(685.0), _strat(686.0)])
        assert hist == {685.0: 2, 686.0: 1}

    def test_accepts_index_strategy_pairs(self):
        """The ELITE stage carries `(e_idx, strat)` at its halving rejection site."""
        assert _elite_wl_histogram([(3, _strat(685.0))]) == {685.0: 1}

    def test_ignores_missing_and_malformed_blocks(self):
        assert _elite_wl_histogram([{}]) == {}
        assert _elite_wl_histogram([{"blocks": None}]) == {}
        assert _elite_wl_histogram([{"blocks": [{"start": 0, "end": 5}]}]) == {}
        assert _elite_wl_histogram([{"blocks": [{"wavelength": None}]}]) == {}
        assert _elite_wl_histogram([{"blocks": ["not a dict"]}]) == {}
        assert _elite_wl_histogram([None, 42, "x"]) == {}

    def test_wavelengths_are_floats_even_when_given_as_int(self):
        assert _elite_wl_histogram([{"blocks": [{"wavelength": 685}]}]) == {685.0: 1}

    def test_empty_input(self):
        assert _elite_wl_histogram([]) == {}


class TestFormatWlHistogram:
    def test_empty_is_named_not_blank(self):
        assert _format_wl_histogram({}) == "(none)"

    def test_heaviest_first_then_wavelength_ascending(self):
        out = _format_wl_histogram({610.0: 1, 685.0: 9, 686.0: 1})
        assert out == "685:9 610:1 686:1"

    def test_a_RARE_wavelength_is_NEVER_hidden(self):
        """🔴 LE GARDE QUI COMPTE, ET IL A REMPLACE UN GARDE PLUS FAIBLE LE 2026-08-21.

        L'ancienne version affichait les 14 λ les plus lourdes et DISAIT « [+N wl not shown] ».
        📏 Mesure : la λ qu'on cherchait -- 685 nm sur `r75x2` -- porte UNE OU DEUX candidates
        par ronde, donc elle tombait dans cette queue masquee, et 61 histogrammes d'un seul run
        etaient tronques. Le compte lu au journal etait un PLANCHER, pas une mesure.

        Dire qu'on tronque ne sert a rien quand ce qu'on cherche est, PAR CONSTRUCTION,
        exactement ce qui est tronque. Un evenement rare est toute la question.
        """
        hist = {610.0: 3701, 686.0: 3185, 689.0: 2769}
        hist.update({float(500 + i): 40 for i in range(70)})   # une longue queue moyenne
        hist[685.0] = 2                                        # la λ rare, la plus legere
        out = _format_wl_histogram(hist)
        assert "685:2" in out, "une λ rare NE DOIT JAMAIS etre masquee par le classement"
        assert "OVER HARD CAP" not in out, "73 λ tiennent tres largement sous le plafond dur"
        assert len(out.split()) == len(hist), "toutes les λ doivent etre imprimees"

    def test_the_hard_cap_is_a_safety_net_and_it_SAYS_when_it_bites(self):
        """Le plafond ne sert qu'a empecher une entree pathologique de produire un mega-octet.

        Sur la grille reelle -- au plus ~301 λ -- il ne mord jamais. S'il mord, il le DIT.
        """
        hist = {float(600 + i): 1 for i in range(20)}
        out = _format_wl_histogram(hist, top=5)
        assert "[+15 wl OVER HARD CAP 5]" in out
        assert len(out.split(" [")[0].split()) == 5

    def test_the_real_grid_is_never_truncated(self):
        """301 λ, la grille de controle complete : elle passe entiere."""
        hist = {float(450 + i): 1 for i in range(301)}
        out = _format_wl_histogram(hist)
        assert "OVER HARD CAP" not in out
        assert "450:1" in out and "750:1" in out


class TestLogEliteWl:
    def test_emits_one_line_for_generated_and_one_per_cause(self, caplog):
        import collections

        logger = logging.getLogger("test_elite_wl")
        rejects = {
            "halving": collections.Counter({686.0: 4}),
            "score_non_fini": collections.Counter({685.0: 2}),
        }
        with caplog.at_level(logging.INFO, logger="test_elite_wl"):
            _log_elite_wl(logger, 7, "COMPLETE", {685.0: 3, 686.0: 1}, rejects)

        lines = [r.getMessage() for r in caplog.records]
        assert len(lines) == 3
        assert all("[ELITE-WL] Round 7 exit=COMPLETE" in ln for ln in lines)
        assert any("generated 685:3 686:1" in ln for ln in lines)
        assert any("rejected_halving 686:4" in ln for ln in lines)
        assert any("rejected_score_non_fini 685:2" in ln for ln in lines)

    def test_a_cause_with_no_reject_is_still_reported(self, caplog):
        """Silence must not be confused with "nothing was rejected here"."""
        import collections

        logger = logging.getLogger("test_elite_wl_empty")
        with caplog.at_level(logging.INFO, logger="test_elite_wl_empty"):
            _log_elite_wl(logger, 1, "HALVING", {}, {"full_rmse": collections.Counter()})

        lines = [r.getMessage() for r in caplog.records]
        assert any("generated (none)" in ln for ln in lines)
        assert any("rejected_full_rmse (none)" in ln for ln in lines)


@pytest.mark.parametrize("wl_present", [True, False])
def test_the_diagnostic_the_instrument_is_for(wl_present):
    """The reading the instrument was built to make, exercised end to end.

    685 nm ABSENT from the generated histogram  -> ELITE never looks there -> fix PARENTS.
    685 nm PRESENT and in a reject histogram    -> ELITE looks, discards   -> fix the GATE.
    """
    generated = _elite_wl_histogram([_strat(685.0 if wl_present else 686.0, 610.0)])
    assert (685.0 in generated) is wl_present


class TestCrashBucket:
    """The band of a rejected candidate decides WHICH repair is possible at all.

    Rejects sitting just above 👤's 5 % tolerance can be kept by a confidence-bounded
    gate. Rejects at 100 % cannot be kept by any gate setting -- only by relaxing the
    search, and then everything found must be re-judged at nominal. Reading one for the
    other would send the work down the wrong branch.
    """

    @pytest.mark.parametrize(
        "rate,expected",
        [
            (0.0, "<=1%"),
            (0.0033, "<=1%"),
            (0.01, "<=1%"),
            (0.0133, "1-2%"),
            (0.02, "1-2%"),
            (0.0267, "2-5%"),
            (0.05, "2-5%"),
            (0.06, "5-10%"),
            (0.10, "5-10%"),
            (0.24, "10-25%"),
            (0.38, "25-50%"),
            (0.98, "50-99%"),
            (1.0, "100%"),
        ],
    )
    def test_bands(self, rate, expected):
        assert _crash_bucket(rate) == expected

    def test_the_tolerance_boundary_is_straddled(self):
        """5 % is the tolerance: just under and just over must not share a band."""
        assert _crash_bucket(0.05) != _crash_bucket(0.0501)

    def test_missing_or_malformed_is_named_not_guessed(self):
        assert _crash_bucket(None) == "unknown"
        assert _crash_bucket("nan-ish") == "unknown"

    def test_a_full_crash_is_never_confused_with_a_marginal_one(self):
        assert _crash_bucket(1.0) == "100%"
        assert _crash_bucket(0.999) == "50-99%"


class TestLogEliteWlCrashBands:
    def test_bands_are_logged_when_present(self, caplog):
        import collections

        logger = logging.getLogger("test_elite_wl_bands")
        bands = collections.Counter({
            ("score_non_fini", "100%"): 1116,
            ("score_non_fini", "5-10%"): 7,
            ("full_rmse", "<=1%"): 211,
        })
        with caplog.at_level(logging.INFO, logger="test_elite_wl_bands"):
            _log_elite_wl(logger, 3, "COMPLETE", {685.0: 1}, {}, bands)

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "reject_crash_bands" in joined
        assert "score_non_fini/100%:1116" in joined
        assert "score_non_fini/5-10%:7" in joined
        assert "full_rmse/<=1%:211" in joined

    def test_no_band_line_when_nothing_was_rejected(self, caplog):
        logger = logging.getLogger("test_elite_wl_nobands")
        with caplog.at_level(logging.INFO, logger="test_elite_wl_nobands"):
            _log_elite_wl(logger, 1, "HALVING", {}, {})
        assert "reject_crash_bands" not in "\n".join(r.getMessage() for r in caplog.records)

    def test_crash_bands_is_optional_for_backward_compatibility(self, caplog):
        """Omitting the argument must not raise: the two call sites are the only ones."""
        logger = logging.getLogger("test_elite_wl_optional")
        with caplog.at_level(logging.INFO, logger="test_elite_wl_optional"):
            _log_elite_wl(logger, 1, "HALVING", {685.0: 2}, {})
        assert any("generated 685:2" in r.getMessage() for r in caplog.records)
