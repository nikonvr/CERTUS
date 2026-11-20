r"""Run tools/release_checks.py on a frozen build made outside the repository (lot 3, 2026-11-20).

The build is written to %TEMP%\certus_gel_1120 (`--distpath`), not to dist/ of the Drive tree: 422 MB of binaries kept out
of the synchronization. This wrapper points `DIST_DIR` there and runs the same checks.

    python reports/nuit_2026-11-19/gel/release_checks_temp.py --check-frozen --check-frozen-run --startup-timeout-sec 45
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
import release_checks  # noqa: E402

release_checks.DIST_DIR = Path(os.environ["TEMP"]) / "certus_gel_1120" / "dist"
raise SystemExit(release_checks.main())
