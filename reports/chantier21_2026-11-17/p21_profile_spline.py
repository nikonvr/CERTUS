"""Chantier 21 : profil de l'optimisation SPLINE a noeuds libres (`tests/headless/test_spline.py`, exemple TSIO2-1700-1).

Combien du temps passe dans les fonctions de cout appelees par `minimize` (L-BFGS-B sans gradient, differences finies) ?
Le script de test finit par `os._exit(0)`, qui perdrait le profil : on appelle sa fonction et on ecrit le profil ici.

set PYTHONPATH=. && set QT_QPA_PLATFORM=offscreen && python reports/chantier21_2026-11-17/p21_profile_spline.py
"""
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("tests").resolve()))
sys.path.insert(0, str(Path("tests/headless").resolve()))

import test_spline  # noqa: E402

prof = cProfile.Profile()
t0 = time.perf_counter()
prof.enable()
test_spline.test_spline_headless()
prof.disable()
total = time.perf_counter() - t0

out = io.StringIO()
stats = pstats.Stats(prof, stream=out)
print(f"\nPROFIL total {total:.1f} s (sous cProfile)")
stats.sort_stats("cumulative").print_stats(45)
text = out.getvalue()
print("\n".join(line[:200] for line in text.splitlines() if line.strip())[:12000])
