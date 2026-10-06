# CERTUS

Optical thin-film suite: design, manufacturing strategy, index extraction and field analysis of multilayer
coatings (Python 3.14, PyQt6, NumPy/SciPy/Numba). The transfer-matrix core is checked against an independent
reference (`tests/oracle/`): a silent error here is a wrong filter that someone builds.

| Module | What it does |
|---|---|
| **DESIGN** | synthesis: stochastic global optimization (PGLOBAL), needle insertion, analytic gradients |
| **STRAT** | manufacturing: predictive monitoring strategy, error self-compensation |
| **INDEX**, **INDEX SPLINE** | n, k extraction: Tauc-Lorentz (Kramers-Kronig consistent), or piecewise-linear splines |
| **RE** | reverse engineering of refractive indices from experimental curves |
| **FIELD** | electric-field profile and LIDT optimization |
| **METAL SINGLE**, **METAL BILAYER** | metal strategies on transparent and on opaque substrates |
| **SMOOTHER**, **SUBSTRATE INDEX** | smoothing of spectral data; refractive index of a substrate |

## Run

Python 3.14.5 or later. CERTUS runs from source: there is no build system, and `pip install .` is not supported.

```bash
uv sync --no-install-project    # the dependencies, never the project
python scripts/preflight.py     # must end with PREFLIGHT=GO
python CERTUS_HUB.py            # the launcher; or CERTUS_DESIGN.py, CERTUS_STRAT.py, ...
```

`pip install -r requirements.lock` installs the same set, with hashes. Windows is the development and release platform.

## Test

```bash
python -m pytest tests/oracle/ -q --no-cov    # the independent transfer-matrix reference
python -m pytest tests/unit/ -q --no-cov
```

## More

- Method pages, to open in a browser: [`pages/CERTUS_DESIGN.html`](pages/CERTUS_DESIGN.html), [`pages/CERTUS_STRAT.html`](pages/CERTUS_STRAT.html).
- Working rules: [`CLAUDE.md`](CLAUDE.md). State of the project (measured figures, decisions, open defects): [`docs/ETAT.md`](docs/ETAT.md).
- Licence: GPL-3.0-only ([`LICENSE`](LICENSE)); third-party notices: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
