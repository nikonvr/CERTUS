# Most stable N = 20 design: campaign plan (2026-10-27)

Free 50/50 problem (400-1200 nm, nH 2.35, nL 1.45, glass 1.52, 1601 points). Plan checked against optimisation under
uncertainty (stochastic programming, robust and distributionally robust optimisation, uncertainty quantification).
References are listed from abstracts only: read them before citing.

**Goal: the levers a designer can act on to obtain a robust design a priori.** Finding robust designs numerically is a
means. The path: (1) correlate sensitivity with controllable descriptors over hundreds of equivalent designs;
(2) test each candidate lever by intervention (constrain it, re-optimise, measure the robust cost: causation, not
correlation); (3) explain it physically (sensitivity of T to layer i through the field in that layer); (4) state design
rules and check them prospectively on another N and another error level.

## Error models and criteria

Random, independent errors only, on the **optical thickness** n d of each layer (no systematic errors):

| model | errors |
|---|---|
| OT x nm | sigma(n d) = 0.2, 0.5, 1 nm per layer |
| OT 1% | sigma(n d) = 1 % of n d |

Thin layers are judged by their optical thickness.

Scope: the design itself, the structure least sensitive to thickness errors. Monitoring and recourse are out of scope.

Criteria for every design: sqrt(E[MSE]), CVaR95 (not the 95th percentile, which is not coherent: Rockafellar & Uryasev
2000), yield P(max|T-0.5| < 1 %) and bPOE (inverse CVaR, Mafusalov & Uryasev 2018), each with a bootstrap interval.

## Theory: a robust design is a wide valley

Width must be measured at the error scale, in every direction, in the metric fixed by the OT error covariance Sigma
(flatness is otherwise parametrisation-dependent: Dinh et al., ICML 2017). Three widths, three criteria:

| width | criterion | references |
|---|---|---|
| lambda_max(H) | worst case | minimax (Bertsimas, Nohadani & Teo 2010); SAM (Foret et al. 2021) |
| tr(Sigma H) | mean E[MSE] under random errors | Gaussian smoothing (Nesterov & Spokoiny 2017); continuation (Mobahi & Fisher 2015) |
| local entropy, basin volume | yield | Baldassi et al., PNAS 113 (2016); Entropy-SGD (Chaudhari et al. 2017); Wales |

For random OT errors the mean is set by the trace, not by lambda_max. The quadratic (harmonic) estimate can fail:
Monte Carlo is the judge. Analogy: sigma is a temperature and the smoothed cost a free energy; deep against wide is the
nominal/robust Pareto front.

## Literature read in full

**Tikhonravov, Trubetskov, Amotchkina & Pervak, Appl. Opt. 50, C141 (2011)** — practical optimal design from production
yields.
- **Setup:** ramp target 400-800 nm; 4 nearly equivalent designs with N = 18-21.
- **Non-correlated random errors** (0.5 % of thickness, 5000 runs; Table 3): yield in the +-1 % corridor of 44.7-55.7 %;
  +-1.5 %: 85-92.5 %; +-2 %: 97.5-99.1 %. Modest differences between equivalent designs, consistent with the +-15 %
  near-invariance found here.
- **With optical monitoring** (Tables 1-2): much larger differences (21-56 %, 35-79 %). Out of our scope.
- **What it already establishes:** the practical-optimal-design paradigm (select among theoretical designs by yield,
  not by merit function). It also says, qualitatively, that adding layers is not worth it once the merit gain is small.
- **What it does not contain:** a closed-form robust criterion (it uses Monte Carlo and stresses that thousands of runs
  are needed), an analysis of what makes one design more robust, or a law in N.

**Pervak, Trubetskov & Tikhonravov, Opt. Express 19, 2371 (2011)** — robust synthesis.
- **Method:** a "design cloud" of M = 50 perturbed designs (absolute 0.5 nm physical, optional relative part), whose
  merit is averaged (a sample average) inside needle optimisation and gradual evolution, with the P-function summed over
  the cloud.
- **Practical limits:** the cloud is regenerated from time to time; the method is not deterministic and is stopped by hand.
- **Deliberate choice:** it does **not** use perturbation theory, judged unsuitable for resonant designs.
- **Earlier approaches it cites:** a sensitivity penalty function (ref. 47: Tikhonravov et al., SPIE 4829, 2003, **to
  read**) and minimax (Nohadani et al. 2008; Birge et al., AO 50, C36, 2011).
- **Its structural explanation:** for dispersive mirrors (resonant), robustness comes from fewer cavities and a weaker
  field enhancement. Its robust design also has fewer layers (74 against 92).
- **Consequences here:**
  - our smoothed search is their cloud method;
  - the second-order criterion is valid on the non-resonant 50/50 (Monte Carlo/prediction 0.99-1.02), deterministic and
    cheap;
  - the field descriptor, which explains nothing on the 50/50, is their lever for resonant targets: the two results are
    complementary.

**Tikhonravov, Trubetskov, Amotchkina & Tikhonravov, Proc. SPIE 4829, 1061 (2003)** — two pages, no numerical result.
- **Its Eq. (5)** is the composite merit Phi + sum_ij (alpha_i / Delta R_j * dR_j/dd_i)^2, with alpha_i "estimations of
  errors in individual layer thicknesses". **This is our R^2 = MSE0 + sum sigma_i^2 |dr/dd_i|^2. The robust merit is not
  ours; it must be cited to this paper.**
- **How they reach it:** a linearisation with a deterministic delta d, then the cross term and the off-diagonal terms are
  dropped without justification.
- **Analytic second derivatives** come from their 1993 paper (Comput. Math. Math. Phys. 33, 1339). They also mention
  needle optimisation on this merit.
- **In 2011** (Pervak et al.) they turned to the cloud method instead of perturbation theory.
- **What remains ours:**
  - Eq. (5) is exactly E[MSE] at second order for independent zero-mean errors (the cross and off-diagonal terms vanish
    in expectation), so alpha_i = sigma_i, physically fixed, not a tuning weight; in optical thickness,
    alpha_i = sigma_OT / n_i;
  - the Monte Carlo validation (0.99-1.02 on the 50/50) and its validity domain (non-resonant);
  - everything measured with it: invariance at fixed N, S ~ N^0.5, robust optimum N against sigma, descriptors,
    local entropy.

**Tikhonravov & Trubetskov, Appl. Opt. 51, 7319 (2012)** — the "practically optimal design" paradigm.
- **Sec. 4 (robust AR):** cloud method, M = 20, sigma_abs = 1 nm and sigma_rel = 1 % (physical).
- **The same materials as our 50/50:** R = 0 at 380-720 nm (2 nm step), nH 2.35, nL 1.45, substrate 1.52.
- **Their Table 3, MF / E(MF) (10 000 draws):** AR-6 0.263 / 0.343, AR-10 0.135 / 0.295, AR-14 0.129 / 0.372,
  AR-robust (N = 9, TOT 1102.1 nm) 0.169 / 0.277.
- **They already state, qualitatively, the robust optimum in N:** the composite merit "stops decreasing when some TOT
  and N values are achieved".
- **Consistent with our results:**
  - robust synthesis gains only 6 % on E(MF) over AR-10, so the structure is a weak lever;
  - AR-14 is worse than AR-10, so N is a lever.
- **Thicknesses:** only drawn as index profiles; the problem itself is fully specified and can be re-run.

**Reproducible case:** Amotchkina et al., AO 51, 8677 (2012) tabulates every thickness of 10 edge-filter designs (EF1-EF10),
with merit values (Table 3) to validate the reproduction and yields from monitoring simulations (Table 4).

## Revisions after a critical review (2026-10-27)

- Pilot first at N = 20 (30 min, `pilot20_*`), then the long campaign; N set by `CAT_N`.
- `predict_vs_n.py`: second-order robust cost of the best nominal design at each N, before fixing N.
- Deliverable: the nominal/robust Pareto front, not a single "most stable" design.
- Finalists confirmed on fresh draws never used for selection (`catalog.py confirm`): winner's curse.
- `check_stats.py`: known-answer checks of CVaR, bPOE, control variate, Pareto, layer field.
- Physical hypotheses: H1 thin layers, H2 total thickness (Spearman over the catalogue), H3 field in layer i
  against |J_i|^2 (Spearman over layers); ranking stability across error models.
- Timings printed by every command.

## Phases

1. **Catalogue at N = 20 (pilot), then the N chosen** (`catalog.py`, `CAT_N`).
   - `build`: nominal local minima.
   - `smooth`: direct search on the smoothed cost E[MSE(d+e)] (sample average with common random numbers, continuation
     sigma 2 -> 1 -> 0.5 nm of optical thickness). The robust optimum need not lie near a nominal minimum.
   - `analyse`: J^T J prediction; Monte Carlo with the quadratic model as control variate; CVaR, yield, bPOE with bootstrap;
     active subspace C = E[grad f grad f^T] (Constantine) against the local J^T J; per-wavelength sensitivity (Orchard test).
   - Questions: are nominal and robust correlated? What makes a design robust?
2. **Robustness at no nominal cost**: minimise tr(Sigma J^T J) under MSE <= (1+alpha) MSE0 along sloppy directions.
3. **Direct robust optimisation**: compare SAA (control variates), CVaR, bPOE, DRO penalty rho |grad F| (Wasserstein DRO,
   Gao, Chen & Kleywegt 2022), each with sigma continuation and global moves (needles, removals, thickening).
4. **CERTUS DESIGN**: a robust cost as an option; default only if measured better on the 50/50 and other examples.

## Figures planned for the article

- nominal against robust scatter;
- J^T J spectra, active subspaces, S(lambda);
- Pareto fronts;
- Monte Carlo histograms, best nominal against most stable;
- robust RMSE(N), N chosen from `predict_vs_n.py`.
