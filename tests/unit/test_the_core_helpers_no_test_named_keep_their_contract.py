"""Core helpers that no test named keep their contract (plan S3.7, second batch).

`certus_substrate_db` is the single source of the substrate Sellmeier coefficients, and the production kernel is checked to read it.
`certus_substrate_helpers` decides which column of a measured spectrum file is the BARE SUBSTRATE (the curve the index
extraction is fitted on): a wrong guess there is a wrong refractive index with no error message, and no test said what a
bare-substrate header looks like. `certus_strat_utils` is the bridge through which STRAT finds its material database: an explicit
database first, then the active context, then the application context, then none; a change of that order changes the index of
every layer.

The expected values were read from the code and the headers it is meant to recognise (French and English file conventions of
the lab: `Rnu`, `Tnu1f`, `substrat nu`, `temoin`, `witness`...), then each assertion was broken once on purpose.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# =============================================================================
# certus_substrate_helpers


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Substrat_Nu-Œuvre ", "substrat nu oeuvre"),
        ("Wavelength (nm)", "wavelength (nm)"),
        ("T/R: sub", "t r sub"),
        ("ÉPAISSEUR", "epaisseur"),
        ("a  b\tc", "a b c"),
        (12.5, "12 5"),
    ],
)
def test_a_header_is_lowercased_unaccented_and_its_separators_become_one_space(raw, expected):
    from certus.core.certus_substrate_helpers import norm_header

    assert norm_header(raw) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("substrat nu", "substrate nu"),
        ("subst nu", "substrate nu"),
        ("snu", "substrate nu"),
        ("w/o coat", "no coating"),
        ("no  coat", "no coating"),
        ("temoin", "witness"),
        ("SUBS", "substrate"),
    ],
)
def test_the_abbreviations_of_the_lab_expand_to_one_vocabulary(text, expected):
    from certus.core.certus_substrate_helpers import expand_substrate_abbrevs

    assert expand_substrate_abbrevs(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("substratenu", "substrate nu"), ("subnu", "sub nu"), ("baresub", "bare sub"), ("blanksubstrate", "blank substrate")],
)
def test_words_glued_together_are_separated(text, expected):
    from certus.core.certus_substrate_helpers import unglue_substrate_nu

    assert unglue_substrate_nu(text) == expected


@pytest.mark.parametrize(
    "name",
    [
        "Rnu",
        "Tnu",
        "Tnu1f",
        "rnu 2s",
        "Substrat_nu",
        "substrate nu",
        "SubNu",
        "bare substrate",
        "uncoated",
        "no coating",
        "without coating",
        "polished substrate",
        "T substrate only",
        "witness",
        "temoin",
        "sapphire",
        "Al2O3",
    ],
)
def test_a_bare_substrate_header_is_recognised(name):
    from certus.core.certus_substrate_helpers import is_bare_substrate_column

    assert is_bare_substrate_column(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "multilayer",
        "filter T",
        "Rfilt",
        "Target",
        "design",
        "QWOT",
        "sample 1",
        "lot 3",
        "batch",
        "final",
        "stack",
        "Wavelength",
        "lambda",
        "random column",
        "",
        None,
        "Tnu filter",  # a filter measured on a bare substrate is still a filter: the exclusion wins
        "bare sub filter",
    ],
)
def test_a_coated_or_unrelated_header_is_not_a_bare_substrate(name):
    from certus.core.certus_substrate_helpers import is_bare_substrate_column

    assert is_bare_substrate_column(name) is False


def test_the_filter_keeps_the_wavelength_column_and_the_bare_substrate_columns_in_order():
    from certus.core.certus_substrate_helpers import filter_bare_substrate_columns

    df = pd.DataFrame(
        {"Wavelength (nm)": [400.0, 500.0, 600.0, 700.0], "Tnu": [0.9] * 4, "T filter": [0.5] * 4, "Rnu": [0.08] * 4, "stack": [1.0] * 4}
    )
    kept_frame, kept, dropped = filter_bare_substrate_columns(df)
    assert list(kept_frame.columns) == ["Wavelength (nm)", "Tnu", "Rnu"]
    assert kept == ["Tnu", "Rnu"]
    assert dropped == ["T filter", "stack"]
    assert kept_frame is not df  # a copy
    assert list(df.columns) == ["Wavelength (nm)", "Tnu", "T filter", "Rnu", "stack"]


def test_the_wavelength_column_is_the_first_one_that_names_wavelength_and_holds_numbers():
    """Not the first column: `x` holds three numbers but does not say wavelength."""
    from certus.core.certus_substrate_helpers import filter_bare_substrate_columns

    df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "Tnu": [0.9, 0.9, 0.9], "wavelength": [400.0, 500.0, 600.0]})
    kept_frame, kept, dropped = filter_bare_substrate_columns(df)
    assert list(kept_frame.columns) == ["wavelength", "Tnu"]
    assert (kept, dropped) == (["Tnu"], ["x"])


def test_a_wavelength_column_with_fewer_than_three_numbers_is_not_taken():
    from certus.core.certus_substrate_helpers import filter_bare_substrate_columns

    df = pd.DataFrame({"first": [1.0, 2.0, 3.0], "wavelength": [400.0, 500.0, np.nan], "Tnu": [0.9, 0.9, 0.9]})  # two numbers
    kept_frame, _kept, _dropped = filter_bare_substrate_columns(df)
    assert list(kept_frame.columns) == ["first", "Tnu"]  # falls back to the first column


@pytest.mark.parametrize("frame", [None, pd.DataFrame(), pd.DataFrame({"only": [1.0, 2.0]})])
def test_an_empty_or_one_column_frame_is_returned_untouched(frame):
    from certus.core.certus_substrate_helpers import filter_bare_substrate_columns

    out, kept, dropped = filter_bare_substrate_columns(frame)
    assert out is frame
    assert (kept, dropped) == ([], [])


# =============================================================================
# certus_strat_utils


class _Db:
    def __init__(self, tag):
        self.tag = tag

    def get_refractive_index(self, mat, wl):
        return ("method", self.tag, mat, wl)

    def get_refractive_clues_vectorized(self, mat, wls):
        return ("method-vec", self.tag, mat, len(wls))


class RobustMaterialDatabase(_Db):
    """Named as the class the bridge recognises by name: it is called directly, not through the original function."""


@pytest.fixture
def bridge(monkeypatch):
    """The module with its two original functions replaced by recorders, no active context, an empty application context."""
    import certus.core.certus_strat_utils as utils
    from certus.utils.certus_strat_context import StratContext

    monkeypatch.setattr(utils, "_original_get_refractive_index", lambda mat, wl, db: ("original", mat, wl, db))
    monkeypatch.setattr(utils, "_original_get_refractive_clues_vectorized", lambda mat, wls, db: ("original-vec", mat, len(wls), db))
    monkeypatch.setattr(utils, "APP_CONTEXT", {})
    previous = StratContext.get_current()
    StratContext.set_current(None)
    yield utils
    StratContext.set_current(previous)


def test_an_explicit_database_is_used_before_anything_else(bridge):
    from certus.utils.certus_strat_context import StratContext

    explicit, active = _Db("explicit"), _Db("active")
    with StratContext(material_db=active).activate():
        assert bridge.smart_get_refractive_index("H", 550.0, explicit) == ("original", "H", 550.0, explicit)
        assert bridge.smart_get_refractive_clues_vectorized("H", np.zeros(3), explicit) == ("original-vec", "H", 3, explicit)


def test_the_active_context_database_comes_second(bridge):
    from certus.utils.certus_strat_context import StratContext

    with StratContext(material_db=_Db("active")).activate():
        assert bridge.smart_get_refractive_index("L", 600.0) == ("method", "active", "L", 600.0)
        assert bridge.smart_get_refractive_clues_vectorized("L", np.zeros(4)) == ("method-vec", "active", "L", 4)


def test_without_a_context_database_the_context_application_dict_comes_third(bridge):
    from certus.utils.certus_strat_context import StratContext

    shared = _Db("shared")
    with StratContext(app_context={"materials_db": shared}).activate():
        assert bridge.smart_get_refractive_index("H", 500.0) == ("original", "H", 500.0, shared)


def test_the_context_application_dict_wins_over_the_global_one(bridge):
    from certus.utils.certus_strat_context import StratContext

    bridge.APP_CONTEXT["materials_db"] = _Db("global")
    shared = _Db("shared")
    with StratContext(app_context={"materials_db": shared}).activate():
        assert bridge.smart_get_refractive_index("H", 500.0) == ("original", "H", 500.0, shared)


def test_then_the_global_application_context(bridge):
    glob = _Db("global")
    bridge.APP_CONTEXT["materials_db"] = glob
    assert bridge.smart_get_refractive_index("H", 500.0) == ("original", "H", 500.0, glob)
    assert bridge.smart_get_refractive_clues_vectorized("H", np.zeros(2)) == ("original-vec", "H", 2, glob)


def test_a_robust_database_found_in_the_fallback_is_called_directly(bridge):
    bridge.APP_CONTEXT["materials_db"] = RobustMaterialDatabase("robust")
    assert bridge.smart_get_refractive_index("H", 500.0) == ("method", "robust", "H", 500.0)
    assert bridge.smart_get_refractive_clues_vectorized("H", np.zeros(5)) == ("method-vec", "robust", "H", 5)


def test_with_no_database_anywhere_the_original_is_asked_with_none(bridge):
    assert bridge.smart_get_refractive_index("H", 500.0) == ("original", "H", 500.0, None)
    assert bridge.smart_get_refractive_clues_vectorized("H", np.zeros(2)) == ("original-vec", "H", 2, None)


def test_the_smart_functions_replace_the_names_the_module_exports():
    import certus.core.certus_strat_utils as utils

    assert utils.get_refractive_index is utils.smart_get_refractive_index
    assert utils.get_refractive_clues_vectorized is utils.smart_get_refractive_clues_vectorized


def test_the_legacy_setter_puts_the_database_in_the_current_context(bridge):
    from certus.utils.certus_strat_context import StratContext

    db = _Db("legacy")
    bridge.set_robust_material_db(db)
    assert StratContext.get_current().material_db is db


def test_the_index_wrapper_reads_a_dict_by_get_and_a_list_by_position():
    from certus.core.certus_strat_utils import _IdxWrapper

    wrapped_dict = _IdxWrapper({"a": 1, "b": None})
    assert wrapped_dict["a"] == 1
    assert wrapped_dict["missing"] is None  # a dict is read with .get
    assert ("a" in wrapped_dict, "missing" in wrapped_dict) == (True, False)
    wrapped_list = _IdxWrapper([10, 20, 30])
    assert wrapped_list[1] == 20
    assert (10 in wrapped_list, 2 in wrapped_list) == (True, False)  # `in` is the container's own: a value for a list


def test_the_strategy_constants_are_the_documented_ones():
    import certus.core.certus_strat_utils as utils

    assert utils.DYNAMICS_METRIC_NAME == "peak_to_peak"
    assert utils.DP_DEFAULT_MIN_WL_SEPARATION_NM == 10.0
    assert utils.SYM_DEFAULT_EXTREMA_WINDOW_OT == 12.0
    assert (utils.SYM_DEFAULT_WEIGHT, utils.SYM_DEFAULT_SAME_WL_BONUS, utils.SYM_DEFAULT_CONTINUITY_WEIGHT) == (0.35, 0.15, 0.25)
    assert utils.SYM_DEFAULT_SCORING_MODE == "post"
    assert (utils.SYM_DEFAULT_TIE_EPS_ABS, utils.SYM_DEFAULT_TIE_EPS_REL) == (1e-6, 1e-4)


def test_the_phase_a_bridge_lends_its_kernels_to_the_service_and_gives_them_back(monkeypatch):
    import certus.core.certus_strat_utils as utils
    import certus.utils.certus_strat_service as service

    sentinel_validate, sentinel_update = object(), object()
    monkeypatch.setattr(service, "validate_wavelengths_batch", sentinel_validate)
    monkeypatch.setattr(service, "update_run_states_kernel", sentinel_update)
    seen = {}

    def fake_service(*args, **kwargs):
        seen["kernels"] = (service.validate_wavelengths_batch, service.update_run_states_kernel)
        seen["call"] = (args, kwargs)
        return "result"

    monkeypatch.setattr(utils, "_service_validate_candidates_phase_a", fake_service)
    assert utils._validate_candidates_phase_a(1, 2, key="v") == "result"
    assert seen["call"] == ((1, 2), {"key": "v"})
    assert seen["kernels"] == (utils.validate_wavelengths_batch, utils.update_run_states_kernel)  # lent for the call
    assert (service.validate_wavelengths_batch, service.update_run_states_kernel) == (sentinel_validate, sentinel_update)


def test_the_phase_a_bridge_gives_the_kernels_back_when_the_service_raises(monkeypatch):
    import certus.core.certus_strat_utils as utils
    import certus.utils.certus_strat_service as service

    sentinel = object()
    monkeypatch.setattr(service, "validate_wavelengths_batch", sentinel)

    def failing(*_args, **_kwargs):
        raise RuntimeError("service failed")

    monkeypatch.setattr(utils, "_service_validate_candidates_phase_a", failing)
    with pytest.raises(RuntimeError, match="service failed"):
        utils._validate_candidates_phase_a()
    assert service.validate_wavelengths_batch is sentinel


# =============================================================================
# certus_substrate_db: the single source of truth of the substrate Sellmeier coefficients


def _sellmeier_index(coeffs, wavelength_nm: float) -> float:
    """n of a 3-term Sellmeier law, written here from its definition (wavelength in micrometres, `n^2 - 1 = sum B l^2 / (l^2 - C)`)."""
    l2 = (wavelength_nm / 1000.0) ** 2
    b1, c1, b2, c2, b3, c3 = coeffs
    return float(np.sqrt(1.0 + b1 * l2 / (l2 - c1) + b2 * l2 / (l2 - c2) + b3 * l2 / (l2 - c3)))


@pytest.mark.parametrize(
    ("substrate_id", "published_nd"),
    [(0, 1.45846), (1, 1.51680), (3, 1.76820)],
    ids=["fused silica", "N-BK7", "sapphire (ordinary ray)"],
)
def test_the_catalog_glasses_reproduce_their_published_index_at_the_sodium_d_line(substrate_id, published_nd):
    from certus.core.certus_substrate_db import SELLMEIER_COEFFS_BY_ID

    assert _sellmeier_index(SELLMEIER_COEFFS_BY_ID[substrate_id], 587.56) == pytest.approx(published_nd, abs=1e-4)


@pytest.mark.parametrize(
    ("substrate_id", "sheet", "tolerance"),
    [
        (2, {486.13: 1.5300, 546.07: 1.5255, 587.56: 1.5231, 656.27: 1.5204}, 3e-4),  # the catalog's own n_d is 1.523303
        (4, {435.83: 1.5341, 479.99: 1.5297, 486.13: 1.5292, 546.07: 1.5251, 587.56: 1.5230, 589.29: 1.5229,
             643.85: 1.5207, 656.27: 1.5203}, 1e-4),
    ],
    ids=["D263T eco", "B270i"],
)
def test_the_two_thin_glasses_reproduce_the_line_indices_of_their_maker(substrate_id, sheet, tolerance):
    """D56, decided by the owner on 2026-10-06: the sets committed before gave n_d = 1.5201 (D263T eco) and 1.5257
    (B270i), against 1.5231 and 1.5230 on SCHOTT's sheets. D263T eco now has SCHOTT's Zemax coefficients; B270i, for
    which SCHOTT publishes none, its two visible terms fitted to the eight line indices of the sheet.
    """
    from certus.core.certus_substrate_db import SELLMEIER_COEFFS_BY_ID

    for wavelength_nm, published in sheet.items():
        assert _sellmeier_index(SELLMEIER_COEFFS_BY_ID[substrate_id], wavelength_nm) == pytest.approx(published, abs=tolerance)


@pytest.mark.parametrize("substrate_id", [0, 1, 2, 3, 4])
def test_the_kernel_computes_the_index_of_the_coefficients_of_the_database(substrate_id):
    """The database says `Single Source of Truth`: the production function must read it, not a copy."""
    from certus.core._certus_physics_impl import get_n_substrate_array_by_id
    from certus.core.certus_substrate_db import SELLMEIER_COEFFS_BY_ID

    wavelengths = np.array([420.0, 587.56, 800.0, 1500.0])
    got = get_n_substrate_array_by_id(substrate_id, wavelengths)
    expected = [_sellmeier_index(SELLMEIER_COEFFS_BY_ID[substrate_id], float(w)) for w in wavelengths]
    assert got.tolist() == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("substrate_id", [0, 1, 2, 3, 4])
def test_below_the_shortest_wavelength_of_a_glass_its_index_is_nan_and_at_it_is_finite(substrate_id):
    from certus.core._certus_physics_impl import get_n_substrate_array_by_id
    from certus.core.certus_substrate_db import SUBSTRATE_MIN_LAMBDA

    limit = SUBSTRATE_MIN_LAMBDA[substrate_id]
    below, at = get_n_substrate_array_by_id(substrate_id, np.array([limit - 0.5, limit]))
    assert np.isnan(below)
    assert np.isfinite(at)


def test_the_substrate_tables_agree_with_each_other():
    import certus.core.certus_substrate_db as db

    assert db.SUBSTRATE_LIST == list(db.SUBSTRATES)
    ids = [info["id"] for info in db.SUBSTRATES.values()]
    assert len(set(ids)) == len(ids)
    assert {i for i in ids if i >= 0} == set(db.SELLMEIER_COEFFS_BY_ID) == set(db.SUBSTRATE_MIN_LAMBDA)
    for info in db.SUBSTRATES.values():
        if info["id"] >= 0:
            assert db.SUBSTRATE_MIN_LAMBDA[info["id"]] == info["min_lambda"]
    assert db.SUBSTRATES["Silicon (Si)"]["id"] == -1  # absorbing: tabulated n, k, no Sellmeier law
    assert all(len(coeffs) == 6 for coeffs in db.SELLMEIER_COEFFS_BY_ID.values())


def test_every_canonical_label_is_offered_once_to_the_user():
    import certus.core.certus_substrate_db as db

    assert isinstance(db.SUBSTRATE_CHOICES, tuple)
    assert len(set(db.SUBSTRATE_CHOICES)) == len(db.SUBSTRATE_CHOICES)
    assert set(db.SUBSTRATE_CHOICES) == set(db.CANONICAL_SUBSTRATE_LABELS.values())


@pytest.mark.parametrize(
    ("label", "canonical"),
    [
        ("sapphire", "Sapphire (Al2O3)"),
        ("SAPPHIRE (Al2O3)", "Sapphire (Al2O3)"),
        ("saphir", "Sapphire (Al2O3)"),
        ("Fused Silica", "SiO2"),
        ("bk7", "N-BK7"),
        ("D263T", "D263T eco"),
        ("Si", "Silicon (Si)"),
        ("void", "Air"),
        ("  air ", "Air"),
        ("Sapphire (FR)", "Sapphire Fresnel"),
    ],
)
def test_an_alias_of_a_substrate_resolves_to_its_canonical_label_whatever_the_case(label, canonical):
    from certus.core.certus_substrate_db import canonicalize_substrate_label

    assert canonicalize_substrate_label(label) == canonical


def test_an_unknown_label_is_kept_as_typed_and_an_empty_one_is_none():
    from certus.core.certus_substrate_db import canonicalize_substrate_label

    assert canonicalize_substrate_label("  Corning 7980  ") == "Corning 7980"
    assert canonicalize_substrate_label("") is None
    assert canonicalize_substrate_label("   ") is None
    assert canonicalize_substrate_label(None) is None


@pytest.mark.parametrize(
    ("label", "substrate_id"),
    [("sapphire", 3), ("Fused Silica", 0), ("bk7", 1), ("d263t", 2), ("B270I", 4), ("Silicon (Si)", None), ("Air", None), ("mystery", None), (None, None)],
)
def test_a_substrate_has_a_sellmeier_id_only_when_a_law_describes_it(label, substrate_id):
    from certus.core.certus_substrate_db import substrate_sellmeier_id

    assert substrate_sellmeier_id(label) == substrate_id


def test_the_coefficients_of_a_substrate_are_floats_in_the_order_b1_c1_b2_c2_b3_c3():
    from certus.core.certus_substrate_db import SELLMEIER_COEFFS_BY_ID, substrate_sellmeier_coeffs

    coeffs = substrate_sellmeier_coeffs("N-BK7")
    assert coeffs == SELLMEIER_COEFFS_BY_ID[1]
    assert all(isinstance(v, float) for v in coeffs)
    assert coeffs[0] == pytest.approx(1.03961212)  # B1 of N-BK7
    assert substrate_sellmeier_coeffs("sapphire")[1] == pytest.approx(0.0726631**2)  # C1 is stored squared
    assert substrate_sellmeier_coeffs("Silicon (Si)") is None
    assert substrate_sellmeier_coeffs("Air") is None
    assert substrate_sellmeier_coeffs(None) is None
