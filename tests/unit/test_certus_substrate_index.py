"""Unit tests: bare substrate (column names) and spectral classification."""





from __future__ import annotations





import sys


from pathlib import Path





import numpy as np


import pandas as pd


import pytest





ROOT = Path(__file__).resolve().parent.parent.parent


sys.path.insert(0, str(ROOT))





csi = pytest.importorskip("certus_substrate_index", reason="certus_substrate_index unavailable")








@pytest.mark.unit


class TestBareSubstrateSpectrumColumn:


    def test_accepts_markers_and_acronyms(self) -> None:


        f = csi.is_bare_substrate_column


        assert f("Tnu2f SNu")


        assert f("Tnu2f")


        assert f("Rnu-2faces")


        assert f("Rnu45s")


        assert f("Rnu45p")


        assert f("R 7157 sapphire 25x1mm vmtim")


        assert f("T 7157 saphir 25x1mm vmtim")


        assert f("sbst nu")


        assert f("bare sub")


        assert f("nocoat")


        assert f("wo coat")


    def test_canonicalize_sapphire_aliases(self) -> None:


        canon = csi.canonicalize_substrate_label


        assert canon("Sapphire") == "Sapphire (Al2O3)"


        assert canon("sapphire") == "Sapphire (Al2O3)"


        assert canon("saphir") == "Sapphire (Al2O3)"


        assert canon("Al2O3") == "Sapphire (Al2O3)"


        assert canon("Sapphire (Al2O3)") == "Sapphire (Al2O3)"





    def test_rejects_bare_tnu_and_stack(self) -> None:


        f = csi.is_bare_substrate_column


        assert not f("stack SNu")


        assert not f("substrat nu design")








@pytest.mark.unit


class TestClassifySubstrateIndexColumns:


    def test_standard_grouping(self) -> None:


        c = csi._classify_substrate_index_columns


        cols = [


            "Tnu2f SNu",


            "Rnu-2faces bare sub",


            "Rnu45s SNU",


            "Rnu45p2f SNU",


        ]


        g = c(cols)


        assert g["t_2f"] == ["Tnu2f SNu"]


        assert g["r_2f"] == ["Rnu-2faces bare sub"]


        assert g["r45s_1f"] == ["Rnu45s SNU"]


        assert g["r45p_2f"] == ["Rnu45p2f SNU"]


        assert g["r45p_1f"] == []


        assert g["r45s_2f"] == []





    def test_rnu_two_face_spelling_variants(self) -> None:


        c = csi._classify_substrate_index_columns


        g = c(["Rnu 2 faces SNU", "rnu2f bare"])


        assert g["r_2f"] == ["Rnu 2 faces SNU", "rnu2f bare"]





    def test_sapphire_generic_r_t_columns_are_grouped_as_two_face(self) -> None:


        c = csi._classify_substrate_index_columns


        g = c(


            [


                "R 7157 sapphire 25x1mm vmtim",


                "T 7157 sapphire 25x1mm vmtim",


                "R 7157 sapphire 45s",


            ]


        )


        assert g["r_2f"] == ["R 7157 sapphire 25x1mm vmtim"]


        assert g["t_2f"] == ["T 7157 sapphire 25x1mm vmtim"]


        assert g["r45s_1f"] == []








@pytest.mark.unit


class TestFilterDataframeBareSubstrateColumns:


    def test_keeps_wavelength_and_bare_columns_only(self) -> None:


        fn = csi._filter_dataframe_bare_substrate_columns


        df = pd.DataFrame(


            {


                "wl": [400.0, 500.0],


                "Tnu2f SNu": [0.5, 0.6],


                "Stack filt": [1.0, 1.0],


            }


        )


        out, kept, dropped = fn(df)


        assert list(out.columns) == ["wl", "Tnu2f SNu"]


        assert kept == ["Tnu2f SNu"]


        assert "Stack filt" in dropped





    def test_prefers_named_wavelength_column_when_first_is_unnamed(self) -> None:


        fn = csi._filter_dataframe_bare_substrate_columns


        df = pd.DataFrame(


            {


                "Unnamed: 0": [0, 1, 2],


                "Wavelength, nm": [400.0, 500.0, 600.0],


                "T 7157 sapphire 25x1mm vmtim": [0.5, 0.6, 0.7],


                "Stack filt": [1.0, 1.0, 1.0],


            }


        )


        out, kept, dropped = fn(df)


        assert list(out.columns) == ["Wavelength, nm", "T 7157 sapphire 25x1mm vmtim"]


        assert kept == ["T 7157 sapphire 25x1mm vmtim"]


        assert "Unnamed: 0" in dropped








@pytest.mark.unit


class TestAutoFitRange:


    def test_suggest_trimmed_fit_range_trims_bad_high_edge(self) -> None:


        wl = pd.Series(range(400, 2400, 10), dtype=float).values


        res = pd.Series([0.002] * len(wl), dtype=float).to_numpy(copy=True)


        res[wl >= 2000] = 0.08


        lo, hi, changed = csi.IndexCore.suggest_trimmed_fit_range(wl, res, 400.0, 2300.0)


        assert changed


        assert lo == pytest.approx(400.0)


        assert hi < 2050.0








@pytest.mark.unit


class TestGeomFitMask:


    def test_geom_fit_mask_orders_bounds(self) -> None:


        wl = np.asarray([100.0, 500.0, 900.0], dtype=float)


        m = csi._substrate_index_geom_fit_mask(wl, 800.0, 200.0)


        assert list(m) == [False, True, False]








@pytest.mark.unit


class TestModelsOrderByRmse:


    def test_substrate_index_models_ordered_by_rmse(self) -> None:


        poly, sell, spl = [m[1] for m in csi.SUBSTRATE_INDEX_MODELS]


        rms = {poly: 0.01, sell: 0.05, spl: 0.002}


        order = csi._substrate_index_models_ordered_by_rmse(rms)


        assert [m[1] for m in order] == [spl, poly, sell]





    def test_non_finite_rmse_sorts_last(self) -> None:


        poly, sell, spl = [m[1] for m in csi.SUBSTRATE_INDEX_MODELS]


        rms = {poly: 0.01, sell: float("nan"), spl: 0.02}


        order = csi._substrate_index_models_ordered_by_rmse(rms)


        assert order[-1][1] == sell





    def test_model_selection_score_penalizes_monotonicity_violation(self) -> None:


        wl = np.asarray([400.0, 500.0, 600.0, 700.0], dtype=float)


        fit_mask = np.asarray([True, True, True, True], dtype=bool)


        n_good = np.asarray([1.8, 1.79, 1.78, 1.77], dtype=float)


        n_bad = np.asarray([1.8, 1.77, 1.79, 1.76], dtype=float)


        s_good = csi._model_selection_score(


            rmse_fit=0.01,


            n_fit=n_good,


            wl_nm=wl,


            fit_mask=fit_mask,


            fit_meta={"source": "analytic-polynomial-4"},


            col_name="sample",


        )


        s_bad = csi._model_selection_score(


            rmse_fit=0.01,


            n_fit=n_bad,


            wl_nm=wl,


            fit_mask=fit_mask,


            fit_meta={"source": "analytic-polynomial-4"},


            col_name="sample",


        )


        assert s_bad > s_good





    def test_model_selection_score_does_not_penalize_sellmeier_monotonicity(self) -> None:


        wl = np.asarray([400.0, 500.0, 600.0, 700.0], dtype=float)


        fit_mask = np.asarray([True, True, True, True], dtype=bool)


        n_good = np.asarray([1.8, 1.79, 1.78, 1.77], dtype=float)


        n_bad = np.asarray([1.8, 1.77, 1.79, 1.76], dtype=float)


        s_good = csi._model_selection_score(


            rmse_fit=0.01,


            n_fit=n_good,


            wl_nm=wl,


            fit_mask=fit_mask,


            fit_meta={"source": "analytic-sellmeier-3poles-A"},


            col_name="sample",


        )


        s_bad = csi._model_selection_score(


            rmse_fit=0.01,


            n_fit=n_bad,


            wl_nm=wl,


            fit_mask=fit_mask,


            fit_meta={"source": "analytic-sellmeier-3poles-A"},


            col_name="sample",


        )


        assert s_bad == pytest.approx(s_good)








@pytest.mark.unit


class TestMonotonicConstraint:


    def test_polynomial_fit_enforces_non_increasing_in_fit_range(self) -> None:


        wl = pd.Series(range(250, 5001, 50), dtype=float).values


        n = 1.8 - 0.00003 * (wl - 250.0)


        # Add an artificial bump violating monotonic decrease.


        n[(wl >= 3600) & (wl <= 3900)] += 0.08


        n_fit = csi.IndexCore.fit_sellmeier(


            n, wl, 250.0, 5000.0, model_kind="polynomial"


        )


        m = (wl >= 250.0) & (wl <= 5000.0)


        dn = np.diff(n_fit[m])


        assert np.all(dn <= 1e-12)








@pytest.mark.unit


class TestFitMeta:


    def test_fit_sellmeier_return_meta_polynomial(self) -> None:


        wl = pd.Series(range(300, 5001, 25), dtype=float).values


        n = 1.9 - 0.00005 * (wl - 300.0)


        n_fit, meta = csi.IndexCore.fit_sellmeier(


            n,


            wl,


            300.0,


            5000.0,


            model_kind="polynomial",


            return_meta=True,


        )


        assert isinstance(n_fit, np.ndarray)


        assert n_fit.shape == n.shape


        assert meta["requested_model_kind"] == "polynomial"


        assert str(meta["source"]).startswith("analytic-polynomial")


        assert isinstance(meta["coeffs"], list)


        assert len(meta["coeffs"]) == 7





    def test_fit_sellmeier_return_meta_skipped_on_insufficient_points(self) -> None:


        wl = np.asarray([400.0, 500.0, 600.0, 700.0, 800.0], dtype=float)


        n = np.asarray([1.8, 1.79, 1.78, 1.77, 1.76], dtype=float)


        n_fit, meta = csi.IndexCore.fit_sellmeier(


            n,


            wl,


            400.0,


            800.0,


            model_kind="sellmeier3poles",


            return_meta=True,


        )


        assert np.allclose(n_fit, n)


        assert meta["requested_model_kind"] == "sellmeier3poles"


        assert meta["source"] == "skipped-insufficient-points"


        assert meta["coeffs"] is None





    def test_fit_sellmeier_spline_adaptive_bspline_lsq(self) -> None:


        wl = np.linspace(400.0, 2400.0, 80, dtype=float)


        # Decreasing (dispersion type) to avoid "non-monotonic" rejection of the spline.


        n = 1.85 - 0.00007 * (wl - 400.0)


        n_fit, meta = csi.IndexCore.fit_sellmeier(


            n,


            wl,


            400.0,


            2400.0,


            model_kind="spline_adaptive",


            return_meta=True,


        )


        assert meta["requested_model_kind"] == "spline_adaptive"


        assert str(meta["source"]).startswith("analytic-bspline-lsq")


        coef = meta.get("coeffs")


        assert coef is not None and len(coef) >= 6


        assert float(coef[0]) == pytest.approx(4.0)


        n_coef = int(float(coef[5 + int(coef[4])]))


        assert n_coef >= 4


        assert n_fit.shape == n.shape





    def test_sellmeier_standard_3term_eval_matches_reference(self) -> None:


        wl_um = np.asarray([0.4, 0.5, 0.7], dtype=float)


        coeffs = np.asarray(csi.SELLMEIER_COEFFS_BY_ID[3], dtype=float)


        n_ref = np.sqrt(


            1.0


            + (coeffs[0] * wl_um**2) / (wl_um**2 - coeffs[1])


            + (coeffs[2] * wl_um**2) / (wl_um**2 - coeffs[3])


            + (coeffs[4] * wl_um**2) / (wl_um**2 - coeffs[5])


        )


        n_mod = csi._sellmeier_3term_standard_eval(coeffs, wl_um)


        assert np.allclose(n_mod, n_ref, rtol=1e-12, atol=1e-12)





    def test_clipboard_line_formats_bspline_lsq_packed_vector(self) -> None:


        t_nm = np.array([400.0] * 4 + [2400.0] * 4, dtype=np.float64)


        nc = 4


        c_b = np.ones(nc, dtype=np.float64)


        head = np.array([4.0, 3.0, 400.0, 2400.0, float(t_nm.size)], dtype=np.float64)


        packed = np.concatenate([head, t_nm, np.array([float(nc)]), c_b])


        line = csi.IndexCore._clipboard_coeffs_line_from_source(


            "analytic-bspline-lsq-nc4", packed.tolist()


        )


        assert "B-spline coefficients (LSQ" in line


        assert "degree k = 3" in line


        assert "n_t = 8" in line


        assert "n_c = 4" in line










def _sapphirenu_example_path() -> Path:
    return ROOT / "example" / "sapphirenu.xlsx"


def _load_sapphirenu_example_dataframe() -> tuple[pd.DataFrame, np.ndarray, dict[str, list]]:
    """Charge example/sapphirenu.xlsx comme l'UI (lambda fini, colonnes substrat nu)."""
    pytest.importorskip("openpyxl", reason="openpyxl required to read sapphirenu.xlsx")
    path = _sapphirenu_example_path()
    if not path.is_file():
        pytest.skip(f"Missing example file : {path}")
    raw = pd.read_excel(path)
    df2, _kept, _drop = csi._filter_dataframe_bare_substrate_columns(raw)
    x = np.asarray(pd.to_numeric(df2.iloc[:, 0], errors="coerce").values, dtype=np.float64)
    m_x = np.isfinite(x)
    if int(np.count_nonzero(m_x)) < 5:
        pytest.skip("Invalid lambda column in sapphirenu.xlsx")
    if not np.all(m_x):
        df2 = df2.loc[m_x].reset_index(drop=True)
        x = np.asarray(pd.to_numeric(df2.iloc[:, 0], errors="coerce").values, dtype=np.float64)
    groups = csi._classify_substrate_index_columns(df2.columns[1:])
    return df2, x, groups


def _n_raw_sapphirenu_column(df2: pd.DataFrame, x: np.ndarray, col: str, groups: dict[str, list]) -> np.ndarray:
    """Same chain as SubstrateIndexGUI._get_clean_fraction_column + n_from_* (15/2/25 window)."""
    y_raw = np.asarray(pd.to_numeric(df2[col], errors="coerce").values, dtype=np.float64)
    m = np.isfinite(x) & np.isfinite(y_raw)
    if int(np.count_nonzero(m)) < 5:
        raise ValueError(f"colonne {col!r}")
    if not np.all(m):
        y_raw = np.interp(x, x[m], y_raw[m])
    y_clean = csi.IndexCore.apply_dynamic_filtering(x, y_raw, 15, 2, 25)
    frac = csi.IndexCore.to_fraction(y_clean)
    if col in groups["t_2f"]:
        return csi.IndexCore.n_from_tnu2f(frac)
    if col in groups["r_2f"]:
        n0 = csi.IndexCore.n_from_rnu2f(frac)
        return csi.IndexCore.enforce_normal_dispersion(x, n0)
    raise ValueError(f"unhandled column type: {col!r}")


@pytest.mark.integration


class TestSapphirenuexampleSellmeier:


    """


    Regression on example/sapphirenu.xlsx.





    Past numerical problems (poorly chosen optimization domain, not "physical"):





    1. L1/L2 >> lambda_min: lambda²-L² < 0 on the grid, floor on the denominator -> inconsistent n(lambda) / rejection.


    2. sqrt(max(n², 1e-9)) with negative n²: n ~ 3e-5 -> outside n acceptance band.


    3. Artificial clip of n²: flat n -> huge RMSE.





    Here we verify that with L bounded for lambda²-L²>0 on the window, the Sellmeier law is accepted


    (source analytic-sellmeier-3poles-A); the polynomial may remain better in the RMSE sense.


    """





    @pytest.fixture(scope="class")


    def sapphire_ctx(self) -> tuple[pd.DataFrame, np.ndarray, dict[str, list]]:


        return _load_sapphirenu_example_dataframe()





    def test_columns_classified_as_two_face(self, sapphire_ctx) -> None:


        df2, _x, groups = sapphire_ctx


        assert groups["t_2f"] == ["T 7157 sapphire_nu_2f"]


        assert groups["r_2f"] == ["R 7157 sapphire_nu_2f"]





    @pytest.mark.parametrize(


        "col",


        ["T 7157 sapphire_nu_2f", "R 7157 sapphire_nu_2f"],


    )


    def test_sellmeier_fit_accepted_on_fit_window(self, sapphire_ctx, col: str) -> None:


        df2, x, groups = sapphire_ctx


        n_raw = _n_raw_sapphirenu_column(df2, x, col, groups)


        wl_lo, wl_hi = 2500.0, 4000.0  # IR: area where the Sapphire IR pole (~18 µm) is decisive


        _nr, n_sell, meta = csi.IndexCore.get_smoothed_and_fits(


            n_raw,


            x,


            wl_lo,


            wl_hi,


            model_kind="sellmeier3poles",


            log_preprocess=False,


            sellmeier_timeout_s=8.0,


            sellmeier_de_maxiter=300,


            sellmeier_ls_max_nfev=3000,


        )


        assert str(meta.get("source", "")).startswith("analytic-sellmeier-")


        coeffs = meta.get("coeffs")


        assert isinstance(coeffs, list) and len(coeffs) in (6, 7)


        fit_m = csi.IndexCore._fit_mask(x, wl_lo, wl_hi) & np.isfinite(n_raw)


        ne = np.asarray(n_sell[fit_m], dtype=np.float64)


        assert np.all(ne >= float(csi.SELLMEIER_N_ACCEPT_LO))


        assert np.all(ne <= float(csi.SELLMEIER_N_ACCEPT_HI))


        lam_min_um = float(np.min(x[fit_m]) / 1000.0)


        if len(coeffs) == 7:


            L1, L2, L3 = float(coeffs[2]), float(coeffs[4]), float(coeffs[6])


            assert L1 < lam_min_um and L2 < lam_min_um and L3 < lam_min_um, "Li < lambda_min(fit) required for lambda²-Li²>0 on the window"





    @pytest.mark.parametrize(


        "col",


        ["T 7157 sapphire_nu_2f", "R 7157 sapphire_nu_2f"],


    )


    def test_polynomial_beats_sellmeier_rmse_on_same_mask(self, sapphire_ctx, col: str) -> None:


        """On the 2500-4000 nm IR range, Sellmeier must be competitive (Sapphire IR pole at ~18 µm)."""


        df2, x, groups = sapphire_ctx


        n_raw = _n_raw_sapphirenu_column(df2, x, col, groups)


        wl_lo, wl_hi = 2500.0, 4000.0


        fit_m = csi.IndexCore._fit_mask(x, wl_lo, wl_hi) & np.isfinite(n_raw)


        _nr_p, n_poly, meta_p = csi.IndexCore.get_smoothed_and_fits(


            n_raw,


            x,


            wl_lo,


            wl_hi,


            model_kind="polynomial",


            log_preprocess=False,


        )


        _nr_s, n_sell, meta_s = csi.IndexCore.get_smoothed_and_fits(


            n_raw,


            x,


            wl_lo,


            wl_hi,


            model_kind="sellmeier3poles",


            log_preprocess=False,


            sellmeier_timeout_s=8.0,


            sellmeier_de_maxiter=300,


            sellmeier_ls_max_nfev=3000,


        )


        assert str(meta_p.get("source", "")).startswith("analytic-polynomial")


        assert str(meta_s.get("source", "")).startswith("analytic-sellmeier-")


        d_p = n_poly[fit_m] - n_raw[fit_m]


        d_s = n_sell[fit_m] - n_raw[fit_m]


        rmse_p = float(np.sqrt(np.mean(d_p * d_p)))


        rmse_s = float(np.sqrt(np.mean(d_s * d_s)))


        assert rmse_p < rmse_s


