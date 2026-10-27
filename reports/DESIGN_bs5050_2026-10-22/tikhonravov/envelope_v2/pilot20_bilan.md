# Robustness pilot, N = 20 (2026-10-27)

Random, independent errors on optical thickness. Sources: `pilot20_mc.txt`, `pilot20_confirm.txt`,
`pilot20_entropy.txt`, `predict_vs_n.txt`, `check_stats.txt` (CHECKS=OK).

**Catalogue.**
- 1297 starts at 0.75 s each gave 399 nominal minima plus 10 smoothed designs.
- Many "distinct" minima are one valley displaced along flat directions: the 0.05 nm duplicate threshold is too strict
  for a sloppy landscape.

**Quadratic regime.**
- Monte Carlo agrees with the J^T J prediction to within about 5 % at OT 0.2, 0.5 and 1 nm and at 1 %.
- The active subspace coincides with J^T J (|cos| 0.86-1.00).

**Sensitivity is nearly design-independent at fixed N.**
- Among the 68 designs with nominal RMSE < 1.5e-3, sqrt(sigma^2 S)/sigma ranges from 7.7e-3 to 1.06e-2 per nm of OT,
  about +-15 %.
- With the nominal RMSE held fixed, the descriptors give partial Spearman correlations near 0: thinnest OT,
  layers under 10 nm OT, total QWOT, H share, stored energy and peak field (|rho| <= 0.07). The exception is cond(J^T J),
  at -0.17.
- H3 (field in a layer against the sensitivity of that layer) gives rho from -0.23 to +0.25.

**N is the main lever.**
- The error term per nm of OT error, for the best nominal design at each N: about 6.6e-3 at N = 13, 8.4e-3 at N = 20,
  9.6e-3 at N = 28 and 1.24e-2 at N = 37.
- Not yet checked on robust-optimised designs.

**The winner depends on sigma, as MSE0 + sigma^2 S predicts.**
- OT 0.2 nm: design 118 (nominal 5.3e-4).
- OT 0.5 and 1 nm: design 130 (nominal 1.22e-3, TOT 18.8 QWOT, thinnest layer 19 nm OT).
- The rankings across sigma are otherwise identical (rho 1.00).

**Out-of-sample confirmation (2000 fresh draws).**
- There is no winner's curse: design 130 gives 4.047e-3 at selection and 4.048e-3 on fresh draws.
- The 10 finalists lie between 4.05e-3 and 4.20e-3.

**Local entropy.**
- The harmonic log volume follows the trace (rho 0.96-1.00) and lambda_max (0.88-0.95).
- The Monte Carlo local entropies (tau >= 1e-5, eps 3-6e-3) agree with the mean (|rho| 0.90-0.94) and the yield (0.80-0.82).
- At low temperature (tau = 1e-6) the "widest" design is 118, the deep OT 0.2 nm winner. The temperature behaves like
  sigma, as the free-energy analogy predicts.
- On this problem the three widths (mean, worst case, volume) largely agree.

**Law against N** (`law_vs_n.txt`, `law_vs_n.png`; 8-min catalogues at N = 10-28, robust selection at OT 0.5 nm).
- s = sqrt(S) of the robust design: 6.9e-3 (N = 10), 8.0e-3, 7.6e-3, 7.7e-3, 8.7e-3, 9.3e-3 (N = 28).
- Fit S ~ N^a gives a = 0.51 for the robust designs. The "every layer contributes the same" law (a = 1) is rejected:
  S/N falls from 4.7e-6 to 3.1e-6.
- The minimum over "good" designs gives a = 0.95, but that set tightens with N, so the estimate is biased.
- Within a design, the 3 largest layer contributions hold 50 % at N = 10-14 and 21 % at N = 28: sensitivity spreads over
  more layers as N grows, without becoming uniform.
- Monte Carlo against prediction: 0.99-1.02.
- The robust optimum N depends on sigma (estimated from these designs): about 17-20 at 0.5 and 1 nm OT, about 24 at 0.2 nm.

**Smoothed search.**
- It costs 20-50 s per start.
- From random starts it fails; from nominal minima it finds nothing better than the catalogue (4.08e-3 against 4.05e-3).
