"""`scripts/c1_diff.py` proves C1 on bits: it must see one ulp, and it must not see what is not there.

C1 (CLAUDE.md section 5): a new parameter is inactive by default, and the inactive path returns exactly the same
bits as before. Until 2026-09-30 the harness that proves it "did not exist yet": tests do not prove numerical
identity, and a recompilation moves the last digits (2.8e-11, reproducible), so a green suite said nothing.

Two halves are guarded here. The comparison (fast): it works on bits, so a sign of zero or one ulp is a
difference, NaN equals itself, and the ulp distance keeps its last bits (the first version converted the ordered
integers to float64 and reported "512 ulp" for one planted ulp). The pipeline (about ten seconds): two trees, one
of them with a 1-ulp change planted in `compute_RT_from_matrix`, each run in its own interpreter with its own cold
Numba cache: the clean pair must be identical, the planted pair must be flagged, on the right array only.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("certus_scripts_c1_diff", ROOT / "scripts" / "c1_diff.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c1 = _load()


# =============================================================================
# The comparison
# =============================================================================


def test_the_same_bits_are_not_a_difference() -> None:
    x = np.array([1.0, 0.5, 1e-10, -3.0, 0.0])

    assert c1.comparer_tableaux(x, x.copy()) is None
    assert c1.comparer_tableaux(x.astype(np.complex128), x.astype(np.complex128)) is None


def test_one_ulp_is_a_difference_and_is_counted_as_one() -> None:
    x = np.array([1.0, 0.5, 1e-10, -3.0])

    diff = c1.comparer_tableaux(x, np.nextafter(x, 10.0))

    assert diff is not None
    assert diff["ulp"] == 1.0  # the first version said 512: it lost the last ten bits in a float64
    assert c1.comparer_tableaux(x, np.nextafter(np.nextafter(x, 10.0), 10.0))["ulp"] == 2.0


def test_the_sign_of_a_zero_is_a_difference() -> None:
    assert c1.comparer_tableaux(np.array([0.0]), np.array([-0.0])) is not None


def test_nan_equals_itself_bit_for_bit_and_nothing_else() -> None:
    nan = np.array([np.nan])

    assert c1.comparer_tableaux(nan, nan.copy()) is None
    assert c1.comparer_tableaux(nan, np.array([1.0])) is not None


def test_both_parts_of_a_complex_number_are_compared() -> None:
    z = np.array([1.0 + 2.0j])

    assert c1.comparer_tableaux(z, np.array([1.0 + np.nextafter(2.0, 3.0) * 1j])) is not None
    assert c1.comparer_tableaux(z, np.array([np.nextafter(1.0, 2.0) + 2.0j])) is not None


def test_a_different_shape_or_type_is_a_difference() -> None:
    assert c1.comparer_tableaux(np.zeros(3), np.zeros(4)) is not None
    assert c1.comparer_tableaux(np.zeros(3), np.zeros(3, dtype=np.float32)) is not None


def test_a_key_on_one_side_only_is_a_difference() -> None:
    both = np.array([1.0])

    rows = c1.comparer({"a#0#0": both, "b#0#0": both}, {"a#0#0": both}, {}, {})

    assert rows["a"]["differents"] == 0
    assert rows["b"]["differents"] == 1


def test_a_refusal_that_only_one_side_makes_is_a_difference() -> None:
    same = {"a#001": "ValueError: nope"}

    assert c1.comparer({}, {}, same, dict(same)) == {}  # both refuse alike: nothing differs, nothing to report
    assert c1.comparer({}, {}, same, {})["a"]["differents"] == 1  # the base refuses, the head answers
    assert c1.comparer({}, {}, same, {"a#001": "TypeError: other"})["a"]["differents"] == 1


# =============================================================================
# The corpus itself
# =============================================================================


def test_the_default_corpus_reaches_the_strat_kernels_without_a_refusal() -> None:
    """A corpus whose calls are refused on the head compares nothing: a changed signature must be seen here, not as
    a harmless "both refuse alike" in a comparison. Measured 2026-09-30: 1 703 arrays, 0 refusals, 80.6 % of
    `certus_strat_growth.py` reached with the JIT off (this corpus is also what exercises `simulate_growth_kernel`)."""
    assert c1.CORPUS_PAR_DEFAUT == ("normal", "oblique", "strat")
    rec = c1.Enregistreur()

    c1.corpus_strat(rec)

    assert rec.erreurs == {}, rec.erreurs
    entries = {key.split("#")[0] for key in rec.tableaux}
    assert entries == {"strat.growth", "strat.states", "strat.turning", "strat.next", "strat.margins", "strat.scan", "strat.tprofile", "strat.detailed"}
    assert len(rec.tableaux) > 1500


# =============================================================================
# The pipeline
# =============================================================================

#: `compute_RT_from_matrix` is the single TMM source: one ulp added to R there moves the whole suite.
ANCHOR = "    r = (n_inc * B - C) / Y_sys\n\n    R = abs(r) ** 2\n"
PLANTED = ANCHOR.replace("R = abs(r) ** 2", "R = abs(r) ** 2 * (1.0 + 2.220446049250313e-16)")


def _copy_tree(destination: Path) -> Path:
    for package in ("certus", "certus_physics"):
        shutil.copytree(
            ROOT / package, destination / package, ignore=shutil.ignore_patterns("__pycache__", "*.nbi", "*.nbc")
        )
    return destination


@pytest.fixture(scope="module")
def trees(tmp_path_factory):
    base = tmp_path_factory.mktemp("c1")
    clean, same, planted = (_copy_tree(base / name) for name in ("clean", "same", "planted"))
    target = planted / "certus" / "physics" / "certus_opt_tmm.py"
    text = target.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert text.count(ANCHOR) == 1, "compute_RT_from_matrix changed: update ANCHOR, the plant must land in R"
    target.write_bytes(text.replace(ANCHOR, PLANTED).encode("utf-8"))
    return clean, same, planted


def test_two_identical_trees_are_identical_bit_for_bit(trees, capsys) -> None:
    clean, same, _ = trees

    assert c1.main([str(clean), "--tete", str(same), "--corpus", "selftest"]) == 0

    assert "C1 TENU" in capsys.readouterr().out


def test_one_ulp_planted_in_the_single_tmm_source_is_found_on_the_right_array(trees, capsys) -> None:
    clean, _, planted = trees

    assert c1.main([str(clean), "--tete", str(planted), "--corpus", "selftest"]) == 1

    out = capsys.readouterr().out
    assert "C1 VIOLE" in out
    assert "selftest#000#0" in out  # R moved
    assert "selftest#000#1" not in out  # T did not
    assert " 2 ulp" in out or " 1 ulp" in out


def test_cold_against_warm_runs_the_same_tree_twice_in_one_cache(trees, monkeypatch, capsys) -> None:
    """Measured 2026-09-30: a kernel read back from the cache does not always return the bits of the one
    compiled a moment ago (the gradient kernels, because of fastmath). The mode that measures it must share
    the cache between its two runs, or it compares two cold runs and finds nothing."""
    clean, _, _ = trees
    caches = []
    real_launch = c1.lancer

    def spy(tree, output, names, threads, tmp, name):
        caches.append(name)
        return real_launch(tree, output, names, threads, tmp, name)

    monkeypatch.setattr(c1, "lancer", spy)

    assert c1.main([str(clean), "--froid-contre-chaud", "--corpus", "selftest"]) == 0

    assert caches == ["commun", "commun"]  # one NUMBA_CACHE_DIR for both runs
    assert "a froid" in capsys.readouterr().out
