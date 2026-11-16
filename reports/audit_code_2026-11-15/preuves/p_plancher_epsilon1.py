"""Owner's question of 2026-11-16 (M-L1): does the floor eps1 >= 1 of the INDEX model act on real fits?

Fits the INDEX examples as `bench_examples.py index` does, then, on the fitted wavelength window, compares the eps1
of CERTUS (floored) with the Kramers-Kronig transform of the fitted Tauc-Lorentz absorption, computed by the
independent helper of tests/unit/test_tauc_lorentz_kernels_match_kramers_kronig_and_finite_differences.py.
Counts the points where the physical eps1 is under 1, i.e. where the floor changes the model.
    python reports/audit_code_2026-11-15/preuves/p_plancher_epsilon1.py
"""

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests" / "unit")]
import bench_examples as B  # noqa: E402
import numpy as np  # noqa: E402

B.qapp()
B.autoanswer_dialogs(True)
from test_tauc_lorentz_kernels_match_kramers_kronig_and_finite_differences import kramers_kronig_eps1  # noqa: E402

import certus_physics  # noqa: E402
from certus.core.certus_core import HC_EV_NM  # noqa: E402
from certus.physics.certus_optical_models import epsilon1_TL_analytic  # noqa: E402
from CERTUS_INDEX import CertusIndexApp  # noqa: E402

certus_physics.warmup_physics()
FILES = tuple(sys.argv[1:]) or ("H400-RTNBrel-sapphire.xlsx", "H400-RTSIrel-sapphire.xlsx", "H800-sapphire-RTrelNB.xlsx", "NB sur sapphire.xlsx")
for name in FILES:
    app = CertusIndexApp()
    app.load_file(str(ROOT / "example" / "example_index" / name))
    app.run_optimization()
    res = B.wait_for(getattr(app, "worker", None) or getattr(app, "_worker", None))
    tlu = getattr(res, "tlu_params", None)
    if tlu is None:
        print(f"{name}: no TLU result ({type(res).__name__})")
        continue
    lam = np.asarray(app.target_data["lambda"], dtype=float)
    lam = lam[np.isfinite(lam)]
    E = np.sort(HC_EV_NM / lam)
    certus = epsilon1_TL_analytic(E, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf)
    physical = np.array([kramers_kronig_eps1(e, tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf) for e in E])
    under = physical < 1.0
    print(f"{name}: RMSE {float(res.final_mse) ** 0.5:.6f} | Eg {tlu.Eg:.3f} E0 {tlu.E0:.3f} eps_inf {tlu.eps_inf:.3f} | "
          f"window {lam.min():.0f}-{lam.max():.0f} nm, {E.size} points | physical eps1 < 1 at {int(under.sum())} points "
          f"(min {physical.min():.4f}) | max |CERTUS - KK| where >= 1: {float(np.max(np.abs(certus - physical)[~under])) if (~under).any() else float('nan'):.2e}")
    i = int(np.argmax(np.abs(certus - physical)))
    wide = kramers_kronig_eps1(E[i], tlu.Eg, tlu.A, tlu.E0, tlu.C, tlu.eps_inf, e_max=5000.0)
    print(f"    A {tlu.A:.4g} C {tlu.C:.4g} | worst at E {E[i]:.4f} eV: CERTUS {certus[i]:.6f}, KK(200 eV) {physical[i]:.6f}, KK(5000 eV) {wide:.6f}")
    app.close()
