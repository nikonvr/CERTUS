# CERTUS — Headless tests

Headless tests: each module is driven without user interaction (Qt offscreen). They run in
the standard suite (`python -m pytest tests/ -q --no-cov --ignore=tests/oracle
--ignore=tests/unit --ignore=tests/ui`) and one by one as scripts.

⚠️ **`test_design.py` and `test_strat.py` replace the computation with a mock** (the optimiser
and the STRAT pipeline respectively): they check the plumbing, never a result. Do not measure
anything with them — the benchmark without mocks is `scripts/bench_examples.py`.

| file | module | data |
|---|---|---|
| `test_metal_single.py` | CERTUS METAL SINGLE | `example/example_metal_single/` |
| `test_metal_bilayer.py` | CERTUS METAL BILAYER | `example/example_metal_bilayer/` |
| `test_field.py` | CERTUS FIELD — 1064 / 532 / 355 nm | `example/example_field/test_hr_mirror.json` |
| `test_re.py` | CERTUS RE | `example/example_RE/reverse_sample.xlsx` |
| `test_spline.py` | CERTUS INDEX SPLINE — Al2O3 substrate, ~1700 nm film | `example/example_index_spline/TSIO2-1700-1.xlsx` |
| `test_index.py` | CERTUS INDEX | — |
| `test_design.py` | CERTUS DESIGN, optimiser mocked | `example/example_design/JSON-design-optimized.json` |
| `test_design_campaign.py` | CERTUS DESIGN, campaign plumbing | — |
| `test_strat.py` | CERTUS STRAT, pipeline mocked | — |
| `test_code_duplication.py` | AST duplication guard on `certus/` | — |

```bat
python -m pytest tests/headless/ -q --no-cov
python tests/headless/run_all.py
```
