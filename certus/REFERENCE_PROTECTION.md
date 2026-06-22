# Internal protection of CERTUS modules

This project uses a working reference version stored in `3105 VERSION OLD OK`.

## Reference
- The `OLD` version is the current reference version.
- It must be considered as the stable base for comparisons.

## Scope
This rule particularly concerns:
- `CERTUS_METAL_SINGLE.py`
- `CERTUS_METAL_BILAYER.py`
- `CERTUS_STRAT.py`
- `CERTUS_INDEX.py`
- `CERTUS_INDEX_SPLINE.py`
- `CERTUS_RE.py`
- `CERTUS_DESIGN.py`

## Protection
- Maintain compatibility of entry points.
- Preserve the dependencies of each module.
- Avoid modifying the reference without reproducing and verifying the behavior.
