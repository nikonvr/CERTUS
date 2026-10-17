"""
CERTUS STRAT MACHINE SPECIFICATIONS
===================================
Part of CERTUS Suite (2026)

The published specifications of the optical monitoring system the strategies are scored against (Buhler Leybold Optics OMS 5100).
No solver reads them: the machine grid is opt-in (`tp_hysteresis_factor` is 0 by default), and the factor the UI offers is typed
there. They are kept as the one place where the machine's numbers are written down, cited by the STRAT page.
"""

OMS5100_DEFAULT_READING_NOISE_PCT: float = 0.05
OMS5100_DEFAULT_MONOCHROMATOR_STEP_NM: float = 0.5
OMS5100_DEFAULT_5_SIGMA_FACTOR: float = 1.66
