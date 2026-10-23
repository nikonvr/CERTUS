"""Judge 50/50 splitter designs the way Tikhonravov, Trubetskov and DeBell (Appl. Opt. 35, 5493, 1996) report them.

    python reports/DESIGN_bs5050_2026-10-22/tikhonravov/judge_like_the_article.py FILE.json [FILE.json ...]

Their merit function (eq. 3): MF = sqrt(mean(((T - 0.5) / 0.01)^2)) over 80 wavelengths of 400-1200 nm,
so MF = 100 x RMSE. Their beam splitter: 34 layers, 31.39 QWOT, MF = 1.276685e-2 as printed.
Indices are those of the file at 400 nm (n4), taken constant as in the article (1.45, 2.35, glass 1.52);
T comes from the independent oracle tests/oracle/tmm_reference.py, front face only, normal incidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "oracle"))

from tmm_reference import rt_stack  # noqa: E402


def judge(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    l0 = float(cfg.get("l0", 500.0))
    mats = cfg["materials"]
    rows = [r for r in cfg["front"] if float(r["qw"]) > 0.0]
    n = [float(mats[r["mat"]]["n4"]) for r in rows]
    d = np.array([float(r["qw"]) * l0 / (4.0 * k) for r, k in zip(rows, n, strict=True)])
    n_sub = float(mats["Substrate"]["n4"])

    def rmse(wls):
        t = np.array([rt_stack(w, n, d, n_sub=n_sub)[1] for w in wls])
        return float(np.sqrt(np.mean((t - 0.5) ** 2))), float(np.max(np.abs(t - 0.5)))

    r80, m80 = rmse(np.linspace(400.0, 1200.0, 80))
    r1601, m1601 = rmse(np.linspace(400.0, 1200.0, 1601))
    return {"file": path.name, "layers": len(rows), "total_qwot": round(sum(float(r["qw"]) for r in rows), 3),
            "thinnest_nm": round(float(d.min()), 2), "MF_80": r80 / 0.01, "rmse_80": r80, "max_dev_80": m80,
            "rmse_1601": r1601, "max_dev_1601": m1601}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(json.dumps(judge(Path(arg))))
