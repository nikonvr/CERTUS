# CERTUS KPI Snapshot

- Generated (UTC): `2026-04-25T15:48:42Z`

## KPI-1 Broad Exception Debt
- Active codebase `except Exception`: **0**
- Archive `except Exception`: **25**

## KPI-2 Event Loop Purity Debt (runtime modules)
- Total debt (`processEvents` + `time.sleep`): **0**
- `processEvents`: 0
- `time.sleep`: 0

## KPI-3 Manifest Coverage (static wiring proxy)
- Request construction sites: **9**
- Sites with non-empty `source_paths` wiring: **9**
- Coverage: **100.0%**

## KPI-4 Deterministic Coverage (CI contract proxy)
- Deterministic test contracts declared: **2/2**
- Coverage: **100.0%**

## KPI-5 Physics Direct Coverage (_certus_physics_impl.py)
- Line coverage baseline: **5.4%**
- Function coverage baseline (proxy): **93.3%**

## KPI-6 Headless Service Coverage (proxy)
- Headless service flows tested: **3/3**
- Coverage: **100.0%**
