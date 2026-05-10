# CERTUS — Optical Suite

A suite of applications for thin-film analysis and design (refractive index, transmission/reflection, multilayer strategies, metal single/bilayer, reverse engineering).

## Prerequisites

- Python 3.14+
- Dependencies: PyQt6, NumPy, SciPy, pandas, Numba, pyqtgraph, openpyxl (optional for Excel)

## Installation

From the project root:

```bash
pip install -r requirements.txt
```

For deterministic Windows CI/release builds:

```bash
pip install -r requirements.lock
```

## Launching Applications

From the project root:

- **Hub** (entry point): `python CERTUS_HUB.py`
- **Index** (n/k, TLU, Phase 2 IR): `python CERTUS_INDEX.py`
- **Index Spline** (spline variant): `python CERTUS_INDEX_SPLINE.py`
- **Strat** (multilayer strategies): `python CERTUS_STRAT.py`
- **Design** (optical design): `python CERTUS_DESIGN.py`
- **Reverse engineering**: `python CERTUS_RE.py`
- **Metal Single**: `python CERTUS_METAL_SINGLE.py`
- **Metal Bilayer**: `python CERTUS_METAL_BILAYER.py`
- **Substrate Index** (bare substrate determination): `python certus_substrate_index.py`

## Tests

- **pytest suite**:  
  `python -m pytest tests/ -q --tb=short`  
  (or `-v` for detail)

- **Global Verifications**:  
  `python tests/run_all_verifications.py`  
  Runs the entire pytest suite and displays the result (OK / fail).

- **Release smoke (offscreen)**:  
  `powershell -ExecutionPolicy Bypass -File tools/smoke_release.ps1`

- **Frozen build (PyInstaller/spec)**:  
  `powershell -ExecutionPolicy Bypass -File tools/build_frozen.ps1`

- **Release checks (lock + artifact guards)**:  
  `python tools/release_checks.py`  
  `python tools/release_checks.py --check-frozen` (after frozen build)

- **Code Coverage**: `pytest.ini` mainly measures shared modules (`certus_core`, `certus_ui`, `certus_errors`, `certus_data`, `certus_physics`). Monolithic applications `CERTUS_*.py` are not included in this threshold — see comments in `pytest.ini`.

## Project Structure

- **Root**: `CERTUS_*.py` applications, `certus_*.py` shared modules, `_certus_physics_impl.py` physics engine.
- **certus_physics/**: re-export of engine + structures (Layer, Target, Sample, etc.).
- **tests/**: unit, integration, and performance tests.
- **pages/**: HTML documentation; regenerate the shared `<head>` and assets with `python tools/build_certus_pages.py`.
- **example/**: example data and configurations.
- **artifacts/**: specific outputs (manual exports, run logs, temporary images/spreadsheets).
- **docs/project_meta/**: assistant notes/tools (e.g., `GEMINI.md`).

## Organization Convention (Clean Root)

- Keep only application code (`CERTUS_*.py`, `certus_*.py`) and configuration in the root.
- Do not leave output files in the root (`*.xlsx`, `*.png`, `*_out.txt`, `*_err.txt` from runs).
- Place these outputs in `artifacts/` (or `reports/` for standardized reports).

## Maintenance Documentation

- [AUDIT_CERTUS.md](AUDIT_CERTUS.md) — Entry point for audits (including [docs/comprehensive_audit.md](docs/comprehensive_audit.md)).
