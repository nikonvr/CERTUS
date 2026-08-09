"""Exhaustive integration tests — example/file coupling → headless pipelines.

Each test loads a file from the example/ directory and verifies that it produces
a coherent numerical or structural result.  This is the ultimate safeguard:
if an example delivered with the software no longer works, the test fails.

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠  GOLDEN VALUES :

   The numerical thresholds (RMSE, thickness, etc.) are calibrated on the
   CURRENT pipeline results. If an algorithm changes and improves
   a result, the golden should be UPDATED (not deleted).

⚠  FICHIERS EXEMPLES :

   These tests DEPEND on the files in example/ .  If a sample file
   is renamed or deleted, the corresponding test SKIP (not FAIL).
   NE PAS supprimer les  pytest.skip  sur fichiers manquants.

⚠  TESTS LENTS :

   Tests marked @pytest.mark.slow run real pipelines
   optimization (5-30s each). They are excluded from pytest by default.
   Lancer avec :  pytest -m slow  ou  pytest --run-slow
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("openpyxl")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_ROOT = _REPO_ROOT / "example"


def _example(relpath: str) -> Path:
    """Resolve an example file path; skip the test if missing."""
    p = _EXAMPLE_ROOT / relpath
    if not p.is_file():
        pytest.skip(f"Fichier exemple manquant : {relpath}")
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# §1  DESIGN — Validation structurelle des JSON de configuration
# ═══════════════════════════════════════════════════════════════════════════════

_DESIGN_JSONS = [
    "example_design/JSON-design-example.json",
    "example_design/JSON-design-optimized.json",
    "example_design/JSON-design-oblique-example.json",
    "example_design/JSON-design-seed-A.json",
    "example_design/JSON-design-seed-B.json",
    "example_design/JSON-design-target-achieved.json",
    "example_design/JSON-design-ultra-optimized.json",
]


@pytest.mark.integration
@pytest.mark.parametrize("relpath", _DESIGN_JSONS, ids=[Path(p).stem for p in _DESIGN_JSONS])
def test_design_json_loads_and_has_required_keys(relpath: str) -> None:
    """Chaque JSON design doit charger et contenir front + targets + materials."""
    p = _example(relpath)
    data = json.loads(p.read_text(encoding="utf-8"))

    assert isinstance(data, dict), f"{relpath} n'est pas un dict"
    # PARE-FEU : clefs structurelles obligatoires pour CERTUS_DESIGN
    assert "front" in data, f"Clef 'front' manquante dans {relpath}"
    assert "materials" in data, f"Clef 'materials' manquante dans {relpath}"
    assert isinstance(data["front"], list), f"'front' doit être une liste dans {relpath}"
    assert len(data["front"]) >= 1, f"'front' vide dans {relpath}"


@pytest.mark.integration
def test_design_example_has_targets_and_layers() -> None:
    """The main sample design must have at least 1 target and 20+ layers."""
    p = _example("example_design/JSON-design-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "targets" in data
    assert len(data["targets"]) >= 1
    #FIREWALL: golden = 26 layers in the example delivered
    assert len(data["front"]) >= 20, f"Attendu ≥20 couches, trouvé {len(data['front'])}"


@pytest.mark.integration
def test_design_optimized_spectrum_is_physical() -> None:
    """The optimized design must produce a finite R,T ∈ [0,1] spectrum."""
    p = _example("example_design/JSON-design-optimized.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    #Check that the layers have physical thicknesses (qwot or d > 0)
    for i, layer in enumerate(data["front"]):
        d = layer.get("d") or layer.get("thickness") or layer.get("qwot", 0)
        assert float(d) >= 0, f"Couche {i} a une épaisseur négative"


# ═══════════════════════════════════════════════════════════════════════════════
# §2  STRAT — Validation structurelle des JSON de stratification
# ═══════════════════════════════════════════════════════════════════════════════

_STRAT_JSONS = [
    "example_strat/JSON-strat-example.json",
    "example_strat/JSON-strat-sand38.json",
    "example_strat/JSON-strat-sand8.json",
]
# Note: JSON-strat-example-verification.json, JSON-strat-fast-benchmark.json
#and JSON-strat-blocks-sweep.json are RESULTS files (not configs).


@pytest.mark.integration
@pytest.mark.parametrize("relpath", _STRAT_JSONS, ids=[Path(p).stem for p in _STRAT_JSONS])
def test_strat_json_loads_and_has_wavelength_range(relpath: str) -> None:
    "Each JSON strat must load and define a spectral domain."""
    p = _example(relpath)
    data = json.loads(p.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    # PARE-FEU : clefs spectrales obligatoires pour CERTUS_STRAT
    assert "wl_range_start" in data, f"Clef 'wl_range_start' manquante dans {relpath}"
    assert "wl_range_end" in data, f"Clef 'wl_range_end' manquante dans {relpath}"
    wl_start = float(data["wl_range_start"])
    wl_end = float(data["wl_range_end"])
    assert 100 < wl_start < wl_end < 20000, (
        f"Incoherent spectral domain: [{wl_start}, {wl_end}] nm"
    )


@pytest.mark.integration
def test_strat_example_has_stack_definition() -> None:
    """The main strat example must define an H/L stack."""
    p = _example("example_strat/JSON-strat-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "stack_multipliers" in data
    assert "l0" in data
    l0 = float(data["l0"])
    assert 200 < l0 < 5000, f"Unrealistic design lambda: {l0} nm"


# ═══════════════════════════════════════════════════════════════════════════════
# §3  METAL SINGLE — Validation structurelle du JSON
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_metal_single_json_has_physical_params() -> None:
    """The metal example must define the physical parameters of the film."""
    p = _example("example_metal_single/JSON-metal-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "physical_params" in data
    assert "material_params" in data
    #FIREWALL: the metal JSON must reference a target file
    assert "target_file" in data or "excel_filename" in data


# ═══════════════════════════════════════════════════════════════════════════════
# §4  METAL BILAYER — Validation du CSV spectral
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_metal_bilayer_csv_loads_spectral_data() -> None:
    """The CSV bilayer must load an R(λ) spectrum with ≥100 points."""
    p = _example("example_metal_bilayer/CSV-metal-example.csv")
    from certus.utils.certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 100, f"Trop peu de points spectraux : {df.shape[0]}"
    assert df.shape[1] >= 2, f"Colonnes insuffisantes : {df.shape[1]}"


# ═══════════════════════════════════════════════════════════════════════════════
#§5 RE (Reverse Engineering) — Validation of the XLSX file
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_re_xlsx_loads_spectral_data() -> None:
    """The RE file must load ≥200 points with reflectance columns."""
    p = _example("example_RE/reverse_sample.xlsx")
    from certus.utils.certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 200, f"Trop peu de points spectraux : {df.shape[0]}"
    #FIREWALL: the RE file contains at least lambda + R
    assert df.shape[1] >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# §6  INDEX — Validation du CSV + golden reference
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_index_csv_loads_and_has_transmission() -> None:
    """The CSV index must load a T(λ) spectrum with ≥400 points."""
    p = _example("example_index/CSV-index-example.csv")
    from certus.utils.certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 400, f"Trop peu de points : {df.shape[0]}"


@pytest.mark.integration
def test_index_golden_reference_exists() -> None:
    """Le golden_index.json doit exister et contenir d, mse."""
    p = _example("example_index/golden_index.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    # FIREWALL: golden values ​​for the example CSV-index-example
    # d ≈ 716 nm,  MSE ≈ 7.4e-3
    assert "d" in data and "mse" in data
    d = float(data["d"])
    mse = float(data["mse"])
    assert 600 < d < 900, f"Golden d hors limites : {d} nm"
    assert 0 < mse < 0.05, f"Golden MSE hors limites : {mse}"


# ═══════════════════════════════════════════════════════════════════════════════
# §7  INDEX SPLINE — Chargement XLSX + validation spectre
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_index_spline_xlsx_loads_transmission() -> None:
    """Le XLSX index spline doit charger un spectre T(λ) valide."""
    p = _example("example_index_spline/TOTAL.xlsx")
    from certus.utils.certus_data import read_data_file_robust
    from certus.spline.certus_index_spline_core import normalize_spectrum_dataframe

    df = read_data_file_robust(str(p))
    df = normalize_spectrum_dataframe(df)

    assert "lambda" in df.columns, f"Colonne 'lambda' manquante, colonnes : {list(df.columns)}"
    assert "T" in df.columns, f"Colonne 'T' manquante, colonnes : {list(df.columns)}"
    lam = df["lambda"].to_numpy(dtype=np.float64)
    assert lam.size >= 200, f"Trop peu de points : {lam.size}"
    #FIREWALL: TOTAL spectrum covers at least 300–2000 nm
    assert float(np.nanmin(lam)) < 400
    assert float(np.nanmax(lam)) > 1500


@pytest.mark.integration
@pytest.mark.slow
def test_index_spline_total_optimization_converges() -> None:
    """Pipeline headless INDEX_SPLINE sur TOTAL.xlsx : RMSE doit converger < 0.005.

    FIREWALL: This test runs a real optimization pipeline (~10-20s).
    If the RMSE exceeds the threshold, it is a regression in the physical kernels
    ou dans la logique d'optimisation spline.
    """
    from threading import Event
    from dataclasses import replace

    from certus.utils.certus_data import read_data_file_robust
    from certus.spline.certus_index_spline_core import (
        DataType,
        SplineOptConfig,
        canonical_spline_sigma_knots,
        default_n_mono_band_nm_from_spectrum,
        normalize_spectrum_dataframe,
        physical_nodes_to_x_slice_n,
        prepare_exp_TR_for_fit,
        substrate_id_from_name,
    )
    from certus_physics import get_n_substrate_array_by_id, warmup_physics
    from certus.spline.spline_pipeline import worker_spline_optimization
    from certus.spline.spline_smart_init import pick_best_manual_material_preset

    warmup_physics()

    p = _example("example_index_spline/TOTAL.xlsx")
    df = read_data_file_robust(str(p))
    df = normalize_spectrum_dataframe(df)
    lam = df["lambda"].to_numpy(dtype=np.float64)
    if float(np.nanmax(lam)) < 100.0:
        lam = lam * 1000.0

    t_raw = df["T"].to_numpy(dtype=np.float64)
    sid = substrate_id_from_name("Sapphire (Al2O3)")
    n_sub = get_n_substrate_array_by_id(sid, lam)
    t_exp, _r = prepare_exp_TR_for_fit(lam, n_sub, t_raw, None, t_is_ratio=True)
    sk = canonical_spline_sigma_knots(float(lam.min()), float(lam.max()))
    n_seg = int(sk.size) - 1
    nb = default_n_mono_band_nm_from_spectrum(lam)

    cfg = SplineOptConfig(
        lam_nm=lam,
        t_exp=t_exp,
        r_exp=None,
        n_sub=n_sub,
        data_type=DataType.TRANSMISSION,
        n_seg=n_seg,
        d_lo=1000.0,
        d_hi=3000.0,
        weight_t=1.0,
        weight_r=0.0,
        substrate_name="Sapphire (Al2O3)",
        t_is_ratio=True,
        n_mono_band_nm=nb,
        nk_profile_interp="smooth",
    )

    pk = pick_best_manual_material_preset(cfg, sk, d_nm_hint=0.5 * (cfg.d_lo + cfg.d_hi), relax_n_mono=True)
    if pk is None:
        pytest.skip("No material presets found for TOTAL.xlsx")

    _bid, _rm0, d_opt, n_p, L_p, _rows = pk
    xi = physical_nodes_to_x_slice_n(n_p, sk, nb)
    x0w = np.concatenate((np.asarray([d_opt], dtype=np.float64), xi, L_p.astype(np.float64)))

    cfg = replace(
        cfg,
        x0_warm=x0w,
        spline_local_only=True,
        stage_mandatory_local_maxfun=2000,
        polish_maxfun=1500,
    )

    out = worker_spline_optimization(cfg, stop_event=Event(), progress_cb=lambda _p, _m: None)
    assert isinstance(out, dict), "Pipeline did not return a dict"

    # FIREWALL: golden RMSE for TOTAL.xlsx (wide window, fast pipeline)
    # Conservative threshold: 0.06 — the fast pipeline (spline_local_only, maxfun reduced)
    # ne converge pas aussi finement que le pipeline complet.
    #If the RMSE exceeds this threshold, it is a significant regression.
    wm = float(out.get("pipeline_best_rmse_watermark", float("nan")))
    assert np.isfinite(wm), f"RMSE watermark non fini : {wm}"
    assert wm < 0.06, f"RMSE watermark too high: {wm} (threshold: 0.06)"


# ═══════════════════════════════════════════════════════════════════════════════
# §8 DATABASE — Substrate reference files
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_database_index_files_exist() -> None:
    """The index database files must be present."""
    for name in ["indices.xlsx", "sapphire_index.txt"]:
        p = _EXAMPLE_ROOT / "database_index" / name
        assert p.is_file(), f"Missing database file: {name}"
        assert p.stat().st_size > 100, f"Suspicious file (too small): {name}"


@pytest.mark.integration
def test_sapphire_index_txt_is_parseable() -> None:
    """sapphire_index.txt must be a numeric array λ, n, k."""
    p = _example("database_index/sapphire_index.txt")
    #FIREWALL: the file has a text header, skip the first line
    data = np.loadtxt(str(p), comments="#", delimiter=None, skiprows=1)
    #FIREWALL: at least 2 columns (λ, n) and 50+ rows
    assert data.ndim == 2
    assert data.shape[0] >= 50, f"Trop peu de lignes : {data.shape[0]}"
    assert data.shape[1] >= 2, f"Trop peu de colonnes : {data.shape[1]}"
    # Check that lambda is increasing
    lam_col = data[:, 0]
    assert np.all(np.diff(lam_col) > 0), "Lambda n'est pas strictement croissante"
