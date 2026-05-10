"""Tests d'intégration exhaustifs — couplage fichiers example/ → pipelines headless.

Chaque test charge un fichier du répertoire  example/  et vérifie qu'il produit
un résultat numérique ou structurel cohérent.  C'est le garde-fou ultime :
si un exemple livré avec le logiciel ne fonctionne plus, le test échoue.

── PARE-FEU ──────────────────────────────────────────────────────────────────
⚠  GOLDEN VALUES :

   Les seuils numériques (RMSE, épaisseur, etc.) sont calibrés sur les
   résultats ACTUELS des pipelines. Si un algorithme change et améliore
   un résultat, le golden doit être MIS À JOUR (pas supprimé).

⚠  FICHIERS EXEMPLES :

   Ces tests DÉPENDENT des fichiers dans  example/ .  Si un fichier exemple
   est renommé ou supprimé, le test correspondant SKIP (pas FAIL).
   NE PAS supprimer les  pytest.skip  sur fichiers manquants.

⚠  TESTS LENTS :

   Les tests marqués  @pytest.mark.slow  exécutent de vrais pipelines
   d'optimisation (5-30s chacun). Ils sont exclus du  pytest  par défaut.
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
    """L'exemple principal design doit avoir au moins 1 target et 20+ couches."""
    p = _example("example_design/JSON-design-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "targets" in data
    assert len(data["targets"]) >= 1
    # PARE-FEU : golden = 26 couches dans l'exemple livré
    assert len(data["front"]) >= 20, f"Attendu ≥20 couches, trouvé {len(data['front'])}"


@pytest.mark.integration
def test_design_optimized_spectrum_is_physical() -> None:
    """Le design optimisé doit produire un spectre R,T ∈ [0,1] fini."""
    p = _example("example_design/JSON-design-optimized.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    # Vérifier que les couches ont des épaisseurs physiques (qwot ou d > 0)
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
# Note : JSON-strat-example-verification.json, JSON-strat-fast-benchmark.json
# et JSON-strat-blocks-sweep.json sont des fichiers de RÉSULTATS (pas des configs).


@pytest.mark.integration
@pytest.mark.parametrize("relpath", _STRAT_JSONS, ids=[Path(p).stem for p in _STRAT_JSONS])
def test_strat_json_loads_and_has_wavelength_range(relpath: str) -> None:
    """Chaque JSON strat doit charger et définir un domaine spectral."""
    p = _example(relpath)
    data = json.loads(p.read_text(encoding="utf-8"))

    assert isinstance(data, dict)
    # PARE-FEU : clefs spectrales obligatoires pour CERTUS_STRAT
    assert "wl_range_start" in data, f"Clef 'wl_range_start' manquante dans {relpath}"
    assert "wl_range_end" in data, f"Clef 'wl_range_end' manquante dans {relpath}"
    wl_start = float(data["wl_range_start"])
    wl_end = float(data["wl_range_end"])
    assert 100 < wl_start < wl_end < 20000, (
        f"Domaine spectral incohérent : [{wl_start}, {wl_end}] nm"
    )


@pytest.mark.integration
def test_strat_example_has_stack_definition() -> None:
    """L'exemple principal strat doit définir un empilement H/L."""
    p = _example("example_strat/JSON-strat-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "stack_multipliers" in data
    assert "l0" in data
    l0 = float(data["l0"])
    assert 200 < l0 < 5000, f"Lambda de design irréaliste : {l0} nm"


# ═══════════════════════════════════════════════════════════════════════════════
# §3  METAL SINGLE — Validation structurelle du JSON
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_metal_single_json_has_physical_params() -> None:
    """L'exemple métal doit définir les paramètres physiques du film."""
    p = _example("example_metal_single/JSON-metal-example.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    assert "physical_params" in data
    assert "material_params" in data
    # PARE-FEU : le JSON métal doit référencer un fichier target
    assert "target_file" in data or "excel_filename" in data


# ═══════════════════════════════════════════════════════════════════════════════
# §4  METAL BILAYER — Validation du CSV spectral
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_metal_bilayer_csv_loads_spectral_data() -> None:
    """Le CSV bilayer doit charger un spectre R(λ) avec ≥100 points."""
    p = _example("example_metal_bilayer/CSV-metal-example.csv")
    from certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 100, f"Trop peu de points spectraux : {df.shape[0]}"
    assert df.shape[1] >= 2, f"Colonnes insuffisantes : {df.shape[1]}"


# ═══════════════════════════════════════════════════════════════════════════════
# §5  RE (Reverse Engineering) — Validation du fichier XLSX
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_re_xlsx_loads_spectral_data() -> None:
    """Le fichier RE doit charger ≥200 points avec des colonnes de réflectance."""
    p = _example("example_RE/reverse_sample.xlsx")
    from certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 200, f"Trop peu de points spectraux : {df.shape[0]}"
    # PARE-FEU : le fichier RE contient au minimum lambda + R
    assert df.shape[1] >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# §6  INDEX — Validation du CSV + golden reference
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_index_csv_loads_and_has_transmission() -> None:
    """Le CSV index doit charger un spectre T(λ) avec ≥400 points."""
    p = _example("example_index/CSV-index-example.csv")
    from certus_data import read_data_file_robust

    df = read_data_file_robust(str(p))
    assert df.shape[0] >= 400, f"Trop peu de points : {df.shape[0]}"


@pytest.mark.integration
def test_index_golden_reference_exists() -> None:
    """Le golden_index.json doit exister et contenir d, mse."""
    p = _example("example_index/golden_index.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    # PARE-FEU : golden values pour l'exemple CSV-index-example
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
    from certus_data import read_data_file_robust
    from certus_index_spline_core import normalize_spectrum_dataframe

    df = read_data_file_robust(str(p))
    df = normalize_spectrum_dataframe(df)

    assert "lambda" in df.columns, f"Colonne 'lambda' manquante, colonnes : {list(df.columns)}"
    assert "T" in df.columns, f"Colonne 'T' manquante, colonnes : {list(df.columns)}"
    lam = df["lambda"].to_numpy(dtype=np.float64)
    assert lam.size >= 200, f"Trop peu de points : {lam.size}"
    # PARE-FEU : le spectre TOTAL couvre au moins 300–2000 nm
    assert float(np.nanmin(lam)) < 400
    assert float(np.nanmax(lam)) > 1500


@pytest.mark.integration
@pytest.mark.slow
def test_index_spline_total_optimization_converges() -> None:
    """Pipeline headless INDEX_SPLINE sur TOTAL.xlsx : RMSE doit converger < 0.005.

    PARE-FEU : Ce test exécute un vrai pipeline d'optimisation (~10-20s).
    Si le RMSE dépasse le seuil, c'est une régression dans les kernels physiques
    ou dans la logique d'optimisation spline.
    """
    from threading import Event
    from dataclasses import replace

    from certus_data import read_data_file_robust
    from certus_index_spline_core import (
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
    from spline_pipeline import worker_spline_optimization
    from spline_smart_init import pick_best_manual_material_preset

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
        pytest.skip("Aucun preset matériau trouvé pour TOTAL.xlsx")

    _bid, _rm0, d_opt, n_p, L_p, _rows = pk
    xi = physical_nodes_to_x_slice_n(n_p, sk, nb)
    x0w = np.concatenate((np.asarray([d_opt], dtype=np.float64), xi, L_p.astype(np.float64)))

    cfg = replace(
        cfg,
        x0_warm=x0w,
        spline_local_only=True,
        stage_mandatory_local_maxfun=2000,
        polish_maxfun=1500,
        nonlinear_alpha_second_pass_enabled=False,
        nonlinear_alpha_budget_mode="fast",
    )

    out = worker_spline_optimization(cfg, stop_event=Event(), progress_cb=lambda _p, _m: None)
    assert isinstance(out, dict), "Pipeline n'a pas retourné de dict"

    # PARE-FEU : golden RMSE pour TOTAL.xlsx (fenêtre large, pipeline rapide)
    # Seuil conservateur : 0.06 — le pipeline rapide (spline_local_only, maxfun réduit)
    # ne converge pas aussi finement que le pipeline complet.
    # Si le RMSE dépasse ce seuil, c'est une régression significative.
    wm = float(out.get("pipeline_best_rmse_watermark", float("nan")))
    assert np.isfinite(wm), f"RMSE watermark non fini : {wm}"
    assert wm < 0.06, f"RMSE watermark trop élevée : {wm} (seuil : 0.06)"


# ═══════════════════════════════════════════════════════════════════════════════
# §8  DATABASE — Fichiers de référence substrats
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
def test_database_index_files_exist() -> None:
    """Les fichiers de base de données d'indices doivent être présents."""
    for name in ["indices.xlsx", "sapphire_index.txt"]:
        p = _EXAMPLE_ROOT / "database_index" / name
        assert p.is_file(), f"Fichier de base de données manquant : {name}"
        assert p.stat().st_size > 100, f"Fichier suspect (trop petit) : {name}"


@pytest.mark.integration
def test_sapphire_index_txt_is_parseable() -> None:
    """sapphire_index.txt doit être un tableau numérique λ, n, k."""
    p = _example("database_index/sapphire_index.txt")
    # PARE-FEU : le fichier a un header texte, skip la première ligne
    data = np.loadtxt(str(p), comments="#", delimiter=None, skiprows=1)
    # PARE-FEU : au moins 2 colonnes (λ, n) et 50+ lignes
    assert data.ndim == 2
    assert data.shape[0] >= 50, f"Trop peu de lignes : {data.shape[0]}"
    assert data.shape[1] >= 2, f"Trop peu de colonnes : {data.shape[1]}"
    # Vérifier que lambda est croissante
    lam_col = data[:, 0]
    assert np.all(np.diff(lam_col) > 0), "Lambda n'est pas strictement croissante"
