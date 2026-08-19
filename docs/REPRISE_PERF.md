# Recovery — CERTUS performance

Written on 2026-08-02, for the agent (or human) who takes over, possibly
on another machine.**All figures in this document have been measured**, never estimated.

Read after`CLAUDE.md`. This document corrected a previous optimization plan on
several points: see §5.

---

> 🔴**WARNING — revision of 2026-08-04**
>
> This document remains useful, but**several of its conclusions have been refuted
> by the measure**since. Read first
> session logs (deleted on 2026-08-06, see`git log`).
>
> What changed under the plan: the repository left Google Drive for a
> local disk, the working machine has**4 cores not 16**, and numba is passed
> from 0.65.1 to**0.66.0**. No before/after comparison can span this
> breakup.
>
> Corrections are reported online, section by section. The five
> main ones:
>
> | Section | Status |
> |---|---|
> | §0, prohibition of parallelism | ❌**denied**— see below |
> | §2, INDEX line at 6.5 s | ❌**false by a factor of 2**, the real reference is 12.8 s |
> | §4.3, “the numba cache is not in question, it is verified” | ❌**false**— he was never in`%TEMP%`|
> | §4.4, the numba reflected list | ⚠️**bad target**— the real deposit was elsewhere |
> | §4.5,`use_cache=True`| ✅**solved**— failover is NOT safe |

---

## 0. Quick start — the five minutes that save hours

### Check environment (30 sec)

```bat
:: 1. Does the venv load the code from here? (a .pth has already pointed elsewhere)
C:\envs\certus\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"

:: 2. Is the auto-push hook to the PUBLIC repository disabled?
dir .git\hooks\post-commit* :: should show post-commit.disabled

:: 3. Does the oracle pass? (8 sec, 552 tests)
C:\envs\certus\Scripts\python.exe -m pytest tests\oracle\ -q --no-cov
```

### How long does it cost?

| Action | Duration |
|---|---|
|`pytesttests/oracle/-q--no-cov`|**8s**—tobelaunchedaftereachcalculationmodification|
| Full suite`pytest tests/ -q --no-cov`| ~6 mins |
| FIELD bench / INDEX_SPLINE | 1–2 sec |
| INDEX bench | 7 sec |
| RE bench | 30 sec |
| METAL_SINGLE / BILAYER bench | 55–70 sec |
| DESIGN bench | 45–90 s (very dispersed) |
| STRAT bench | 50–65 sec |
| An A/B campaign of 4 pairs on DESIGN | ~10 min →**background task**|

The Bash tool timeout is capped at**10 minutes**: any campaign
measurement must run in the background.

### The two everyday commands

Measure a module on its real example — from`cmd`:

```bat
C:\envs\certus\Scripts\python.exe scripts\bench_examples.py strat --auto-yes --sample
```

Prove a gain by alternating the two versions —**from Git Bash**, with
slashes and the`^`in quotes:

```bash
bash scripts/ab_compare.sh certus/physics/certus_optimizers.py "2572f46^" design 4 --auto-yes --time-cost
```

⚠️ These two details are not cosmetic. Under bash,`scripts\ab_compare.sh`
becomes`scriptsab_compare.sh`— the backslash is an escape character, and the
command fails. Under`cmd`, it is the`^`of`2572f46^`which disappears, because it is
the escape character of`cmd`: we then no longer compare to the correct commit.

### What is already red — don't go hunting

**The suite has state leaks between tests.**Multiple files are passing
in isolation and fail in a wide selection. Verified on 2026-08-02:

| Test | In wide selection | Isolated | Status |
|---|---|---|---|
|`test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`| ❌ | ✅ | ✅**fixed**|
|`tests/unit/test_certus_ui.py`(4 failures) | ❌ | ✅ 80 passes | ✅**fixed**|

✅**These two lines are resolved and the fix is ​​committed**— root cause
found on 2026-08-02:`tests/ui/test_ui_module_imports.py`replaced
module objects in`sys.modules`without restoring them, which landed the
`monkeypatch.setattr("<module>.<name>", …)`on an orphaned copy.
Details and remains to be done in**`docs/REPRISE_TESTS_ISOLATION.md`**.

Before acknowledging your change: rerun the test**alone**. If it passes, it's a
Pre-existing state leak, not you. (Also verified by returning the original code.)

~~🔴 Do not run two pytest sessions in parallel on this repository.~~
❌**DENIATED BY THE MEASURE on 2026-08-04.**At numba cache**hot**, two sessions
concurrent pytests don't hang at all:

| | Wall | pytest |
|---|---|---|
| 1 pass alone | 17.7 sec | 11.32 sec |
| 2 simultaneous passes | 21.1 and 20.9 s | 12.12 and 12.11 s |

552 tests green in both cases,**+7%**only on pytest time, and
22.3 s in total versus ~35.4 s sequential —**37% gain**.

The cause given by the previous version of this paragraph (“the lock of
numba cache file,`configure_numba_env`") cannot be the correct one:
`configure_numba_env`**never sets**`NUMBA_CACHE_DIR`, cf.
a deleted session log (§10.1). The sighting of 2026-08-02 was
probably done in**cold**cache, where two processes attempt to *write* the
same`.nbi`; hot they only *read* them. Unverified hypothesis.

⚠️**But keep the distinction, it is essential:**

- **Parallelize VALIDATIONS**— oracle, unit tests, lint, while a
  bench turns: ✅ safe and cost-effective.
- **Parallelize MEASUREMENTS**— two benches, or a bench during something else:
  ❌ never. Measured on 2026-08-03: INDEX displayed`RUN_S`**81.5 s**for
  that a copy to Drive and reads were running, compared to**12.4 s**machine at
  rest. On 4 cores, the concurrent load does not add noise, it invents a
  result.

The oracle above is a light charge. Two heavy benches (DESIGN runs at 873%
of CPU) would compete much more for the 4 physical cores.

### Background noises to ignore

These messages appear every time and do not indicate any problems:

- Every`git commit`shows`fatal: bad tree object...`and
  `failed to perform geometric repack`. This is the orphan commit`01047a1b`
  (missing tree) described in`CLAUDE.md §5.4`.**The commit still succeeds**—
  check with`git log --oneline -1`, don't start again.
- ~~`warning: ignoring broken ref refs/heads/desktop.ini`: same, no effect.~~
  ✅**Disappeared**: the broken ref did not survive the repatriation of the deposit outside
  Google Drive (2026-08-03). The orphan commit`01047a1b`is still there.

### Reflex before believing in a gain

The user has an explicit rule:**never announce a gain without having it
measured before/after.**Three traps put it to the test today:

- measure at**frozen**input (an`lru_cache`which touches each call hides everything);
- measure**in sequence**while the machine drifts ±25%;
- measure a module whose**the result naturally varies**by a factor of 2.

---

##1. How to measure — the only method that works

```bat
C:\envs\certus\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes [--sample]
```

`scripts/bench_examples.py`drives the**real examples of`example/`**by
headless, without mock. He documents in his mind the four traps that make a bench
CERTUS fake or blocked — read them before you touch them.

**Do not use`tests/headless/`as a bench.**`test_design.py`replaces
`run_optim`by a function which returns`0.001`without calculating, and`test_strat.py`
replace`_execute_full_pipeline`with a mock. The 9.3 s of STRAT announced in
the old optimization plan (§1) are interface loading.

### Three rules learned the hard way

1. **Alternate the two versions, do not measure them in sequence.**The machine
   drift: on this session, the same code went from 743 to 990 µs/evaluation
   in two hours (thermal, Google Drive sync, other session). A
   A/B in sequence attributes drift to change. Do
   `without / with / without / with…`and count the winning pairs.
2. **Do not conclude from an isolated run on DESIGN or STRAT.**Natural dispersion
   measured: DESIGN 43 → 93 s and RMSE 0.0023 → 0.0051; STRAT 47 → 64 s. When the
   total time is too noisy, measure a stable quantity — for DESIGN, the
   **cost per evaluation**of`cost_numba_fast`(`--time-cost`, ~850,000 calls
   per run) gives a usable signal.
3. **`pytesttests/oracle/-q--no-cov`afteranycalculationmodification.**
   552 tests, 8 sec. And a test that does not fall on the code before the patch does not
   proves nothing: check it by putting back the old version.

---

## 2. Current reference, real examples

Measured on this machine (16 cores), pure calculation excluding loading, after the
corrections to §3.

| Module | Example | Time | Dominant hotspot |
|---|---|---|---|
| STRAT |`JSON-strat-example.json`| 47–64 sec |`compute_batch_rmse`,`simulate_stack_robustness_batch`|
| DESIGN |`JSON-design-example.json`| 43–93 sec |`cost_numba_fast`(873% — pool of ~10 threads) |
| METAL_BILAYER |`JSON-metal-bilayer-example.json`| 67 sec | — |
| METAL_SINGLE |`JSON-metal-example.json`| 52–68 sec |`get_nk_from_spline`, 66,975 calls |
| RE |`reverse_sample.xlsx`| 29–30 sec |`_global_evaluate_oblique_physics`61% |
| INDEX |`H400-RTNBrel-sapphire.xlsx`| ❌ ~~6.5 sec~~ →**12.8 sec**|`certus_index_objectives.py:1755:__call__`54% |
| INDEX_SPLINE |`TSIO2-1700-1.xlsx`| 1.6s |`spline_objective.py:517`25%,`_fast_nk`20% |
| FIELD |`test_hr_mirror.json`| 0.06s | nothing to gain |

Percentages exceed 100%: DESIGN and STRAT run on a thread pool.

> ❌**The INDEX line was wrong by a factor of 2.**It measured the run WITHOUT
> `--auto-yes`, that is to say with the response “No” by default, which skips the
> phase IR — exactly what §6 denounces below (“we measured half of the
> pipeline"). Measured on 2026-08-04 with`--auto-yes`on the 4-core machine:
> **12.425 s**, compared to 12.8 s here.**Correct reference is 12.8 sec.**
>
> ⚠️**INDEX is also DISPERSIVE**, which this table does not say: two passes
> consecutive gives RMSE 0.002568 then 0.002781 (**8%**) and`RUN_S`11.1 then
> 8.1 sec (**27%**). Rule 2 of §1 only applies to DESIGN and STRAT;**it is worth
> also for INDEX**. Nobody could know: the bench returned`RESULT=None`
> on this module, lack of correct extraction (corrected, cf. §3 of the document
> recovery).
>
> **Factors measured on the 4-core machine**(`RUN_S`, hot cache, machine at
> rest): FIELD ×2.0 · INDEX**×0.97, parity**· INDEX_SPLINE**×5.9**.
> The parity of INDEX is explained: the`.nbi`cache of the 16-core machine was alive
> in Google Drive, its CPU advantage was eaten up by I/O.

---

## 3. What is done (commits to`refactor-corridors-mixins`)

| Commit | Object | Gain**measured**|
|---|---|---|
|`a9983c4`| Spline base cache LRU eviction |**0 s**today — see §5 |
|`33af845`| STRAT: njit dispatch removed, factored matrix cache |**−61%**(137.7 · 126.7 → 56.9 · 47.1 s) |
|`2572f46`| PGLOBAL: oversubscription of numba threads |**−29%**per rating, 4 out of 4 alternating pairs |
|`f6f9102`| RE: indexing by`slice`instead of block copies |**−11%**(33.3 → 29.5 s median) |
|`bc2042a`| DESIGN: running on the thickness pad | correction, not performance |

`bc2042a`is worth reading:`app._ep_buffer`was**a single shared array**
between the ~14 threads of the PGLOBAL pool. As soon as a layer is frozen, two threads
crushed each other and the cost was calculated on a mixture of two
stacks. Measured:**278 false reviews out of 48,000**, without any errors
visible. Safeguard:`tests/oracle/test_design_objective_thread_safety.py`.

---

##4. What remains to be done

### 4.1 Physics-informed drawing in PGLOBAL — the most promising

**Choose by user, not started.**

PGLOBAL uniformly samples`[0, 1.2 × QWOT]^N`with scrambled Sobol
(`qmc.Sobol(scramble=True)`,`certus_optimizers.py:646`— the setting is correct,
don't change it for nothing). But for thin layers, the good solutions are
concentrated near QWOT multiples; uniform filling, as well
balanced though it may be, spends most of its points far from there.

Track: draw a multiple in {0; 0.5; 1} × QWOT (beyond 1.2
QWOT we go out of bounds), plus a jitter, keeping a fraction of Sobol points
pure for exploration. Entry point:`PGlobalOptimizer._generate_samples`
(`certus/physics/certus_optimizers.py:694`).

**Mandatory protocol**: compare**to fixed evaluation budget**, on
several seeds, and look at the best RMSE achieved — no time.
Changing samplers can**not**speed up anything:
the sampling weighs 1.5% of the profile. The target gain is the optimum quality at
equal cost. Given the dispersion of DESIGN (RMSE 0.0023 → 0.0051), it is necessary at least
5 seeds by variant.

### 4.2 INDEX — numba compilation during calculation

~15% of the INDEX run goes to JIT**during**optimization, despite
`warmup_physics()`:`llvmlite/binding/ffi.py:210`11%,`numba compiler_lock`
2.9%,`numba/core/caching.py:_load_index`1%. Find which nuclei are not
covered by the warmup, and add them there.

> ⚠️**More profitable track than before**: measured on 2026-08-03, compilation at
> cold of the oracle increased from**60.6 s to 104.6 s**(+73%) between numba 0.65.1
> and 0.66.0.
>
> ❌**These are not forgotten cores, these are forgotten SIGNATURES.**A
> AST scan of the**111`@njit`**functions in the package shows that they carry
> **all**`cache=True`. The real cause is
> `certus/core/certus_index_solvers.py:255`, which allocates samples in
> **float32**while the scipy local phase returns to float64: numba compiles
> **two signatures**of the warm path, and`warmup_physics`— which only passes
> float Python — only covers one. A**third**`readonly`variant exists,
> produced by the`np.frombuffer(key_in_bytes)`idiom of lru caches.
>
> ✅**An entire block of warmup had been dead for years**:
> `certus/core/_certus_physics_impl.py:1492`did
> `np.interp(CIE_LAMBDA, wls, R_test)`with`wls`at 50 points and`R_test`at 10 —
> `ValueError`swallowed by the enclosing`except`, so`_xyz_from_spectrum_kernel`
> and`delta_e_2000`were never compiled by warmup. Diagnosed by
> **the absence of their`.nbi`on disk**, corrected, confirmed by their appearance.
> Remember the method:**the presence of`.nbi`is a check that costs nothing
> calculation.**
>
> ⚠️ Passing`:255`in float64 changes the sampling step, therefore the trajectory
> of the optimizer. To only attempt**after**having exposed a seed in the bank:
> INDEX is dispersive at 8%, an A/B on two isolated runs would give a verdict to the
> chance.

### 4.3 Late imports on slow disk

`<frozen importlib._bootstrap_external>:145:_path_stat`weighs 18.6% of the thread
main of INDEX and 23% of INDEX_SPLINE. The repository lives in a**Google folder
Drive**(`D:\drivefl\…`): each`stat`can be costly.

~~⚠️ The numba cache is NOT in question, it is verified:`configure_numba_env`on
already placed in`%TEMP%\CERTUS_Numba_Cache`. Don't go down that path again.~~

❌**FALSE, and this ban was therefore unfounded.**Verified on 2026-08-04:

| Control | Result |
|---|---|
|`%TEMP%\CERTUS_Numba_Cache`|**does not exist**|
|`.nbi`in the`__pycache__`of the repository |**78 files**|

`configure_numba_env`only sets`NUMBA_CACHE_DIR`in`certus_core.py:359-361`,
but the branch from`:334`**returns to`:352`before getting there**— and
`bench_examples.py:443`imports`certus_physics`, so numba,**before**
`CERTUS_INDEX`does not call`_configure_numba_env()`. The branch is still taken.
Worse: in numba 0.66, the cache locator is frozen**at decoration**
(`numba/core/caching.py:414-420`), so setting the variable too late has no effect.

**The JIT cache lives next to the sources**— that is, at the time of this document,
**in the Google Drive folder**. The 18.6% and 23% of`_path_stat`above,
it was most likely him.

❌**And the measurement itself was an artifact.**`scripts/bench_examples.py:687`
places the sampling window**around the application import**: these
percentages are not calculation time, but module loading.
Re-profiled on 2026-08-04 on local disk, INDEX_SPLINE gives`_path_stat`to
**9.0%**(compared to 23.0%) and 42% in`_call_with_frames_removed`, i.e.
the import itself.

✅**What was left of reality was done**: 8 late imports removed from
`certus/spline/spline_workers.py`, one of which is executed on**each evaluation
L-BFGS-B**. No cycle (verified), and 6 of the 8 names were already at the top of the module.
The 11 late imports of`certus/workers/certus_index_workers.py`are,
**NOT movable**: proven import cycle. Do not touch it.

### 4.4 STRAT — what remains after`33af845`

The row profile is now dominated by real compiled kernels:
`compute_batch_rmse`(146%),`compute_T_front_profile`(107%),
`calculate_extrema_distances`(107%),`simulate_stack_robustness_batch`(44%).

~~A concrete lead remains:`calculate_extrema_distances`accumulates its extrema
in a numba thoughtful list, notoriously slow. Replace it with an array
pre-allocated.~~

⚠️**BAD TARGET.**Reading the code shows that this list only represents
**2 of the 6 NRT**allocations of the function and in practice only contains**0 to 2
elements**— the window covers ±16 nm of optical path when the extrema of T(d)
are spaced by λ/2, i.e. ~275 nm to 550 nm. The real cost is**56 to 88
evaluations**of`_calc_T_added_layer`, each with`cos`/`sin`on argument
complex. The winning ceiling of this track is therefore low.

✅**The real deposit was elsewhere, and it is processed.**The profile block
theoretical from`certus/core/certus_strat_robustness.py:624-658`— where live
precisely the two most expensive lines above,`compute_T_front_profile`
at 107.2% and`calculate_extrema_distances`at 106.7% — is calculated**then thrown away**
by two out of three callers:

- consensus rescoring only reads`robustness_score`;
- the halving ELITE only reads`rmse_p95`and re-stacks the**input**strategy.

Only the main pass and the complete ELITE evaluation exploit it, this
last via`full_res["strategy"]`. A parameter`compute_layer_profile: bool =
True`was added and both sites that throw the result pass`False`.
**Gain not measured**: the mechanism is verified, the volume is not.

⚠️**Track`.tolist()`: do not attack it directly.**`_test_strategy_robustness_task`
stores`rmse_all`and`thicknesses_all`in Python lists, but pass in numpy
would break**four**veracity tests, including**two silently**—
`if thicknesses_all:`on a 2D ndarray raises`ValueError`, swallowed by the`except`
enclosing (`certus/ui/certus_strat_thickness_ui.py:402`and
`certus/ui/certus_strat_table_ui.py:164`). This is the failure mode of
`bc2042a`. You need a**prior and separate commit**replacing the 4 tests with
`is None or len(...) == 0`.

🔴**And a prerequisite for any STRAT measurement**:`certus_strat_robustness.py:314`does
`max_workers = cpu_count() // 2`and`:466`does`numba.set_num_threads(2)`, i.e.
**8 numba threads for 4 physical cores**on the current machine. More
largely,**no place in the repository knows the notion of a physical heart**: all
derives from`cpu_count()`. Six sites listed in §10.4 of the recovery document. On a
15 W, this over-subscription is paid for in thermal throttling, which makes all the noise
A/B comparisons.

### 4.5 METAL — the index cache, and why the gain WAS the error

Always open, and this is the**only**place where §2 of this plan applies.
Toggle`use_cache=True`site by site (`gradient_metal.py`×2,
`CERTUS_METAL_BILAYER.py`×2,`CERTUS_METAL_SINGLE.py`×3).

Measured by globally forcing`use_cache=True`on METAL_SINGLE:
**55.9s → 24.7s**. But**be careful**: the final RMSE changes (0.006100 →
0.006124–0.006190).

🔴**TRACK CLOSED on 2026-08-04, SUPPORTED MEASUREMENTS. THE GAIN IS THE MISTAKE.**

Three runs`metal_single --force-cache --instrument`, machine at rest:

| |`RUN_S`|`RESULT`|`HITRATE`|
|---|---|---|---|
| Without cache | 154.6 sec |`0.006100345590625494`| — |
| Cache,**rounded key**(current code) |**75.2 sec**|`0.00613372429822523`❌ |**88.1%**|
| Cache,**exact key**(test) |**150.3 sec**|`0.006100345473793503`✅ |**18.8%**|

The ×2.06 reproduces. But with an**exact**key, the result becomes correct again and
**the gain disappears entirely**— ×1.03. The 88% success rate was ~70 points
truly distinct geometries, crushed by rounding at 1e-6 nm: these are
precisely the finite difference disturbances of L-BFGS-B. Construction of
matrices: 19.1 s for 5,499 distinct versus 69.3 s for 10,737.

⚠️**Additional trap, invisible in the original measurement**: with the cache, the
number of calls to`get_nk_from_spline`increases from**68,503 to 51,149**. The optimizer does not
does not do the same work faster,**it does 25% less work**because its
trajectory diverges. The “×2” is therefore not even a pure acceleration.

**Do not restart this track.**The rounding of`certus_optical_models.py:419`is
deliberated and documented on site.

---

Analysis of the cause, kept for memory:

These are not the 1.78e-15 of floating reassociation. It's a loss
information in the cache key**.`SplineBasisCache.get`rounds the
node positions to**6 decimal places**to construct your key
(`certus/physics/certus_optical_models.py:419`). The wavelengths of METAL
are in**nanometers**(`CERTUS_METAL_SINGLE.py:1256`), so the quantum of the key
is**1e-6 nm**, or**100× the finite difference step of L-BFGS-B (1e-8)**.

> **Gradient disturbance is exactly canceled by key rounding.**
> The optimizer derives an objective that has become locally constant.

Three corollaries:

- `certus_optical_models.py:453`— the stored matrix is ​​not reconstructed at
  from the key: the objective becomes**dependent on the cache history**,
  therefore not reproducible from one run to another.
- `tests/oracle/test_spline_basis_cache.py:46`— the guardrail supposed to catch this
  bug**can't see it**: it moves the nodes by 1e-4, or 100x the quantum.
- `scripts/bench_examples.py:307`—**55.9 s → 24.7 s does not measure action
  proposed**:`--force-cache`patches globally, including sites that the plan
  does not plan to switch.

Same pathology, 100,000x coarser, in`certus/utils/certus_re_math.py:396`
(nodes rounded to 0.1 nm, grid to 1 nm).

Sites where node positions are**frozen**are immune; those where they
vary are not. ⚠️ Findings resulting from an analysis of which the auditors have
been interrupted:**to cross-check line by line before acting.**

The bench knows how to do it:`--force-cache --trace-nk --instrument`.

### 4.6 Debt not linked to performance

- ~~`tests/unit/test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`
  fails in`-k "re_or reverse or objectives"`selection and passes in isolation.~~
  ✅**Resolved and committed on 2026-08-02**— cf.`docs/REPRISE_TESTS_ISOLATION.md`.
- `_is_busy`is read in`certus_design_ui.py:339`and**never written**anywhere.
- `git gc`always fails on orphan commit`01047a1b`(missing tree) —
  every commit shows`fatal: bad tree object`. No effect on commits.

---

## 5. Three claims refuted by the measure

*They came from a previous optimization plan, deleted on 2026-08-06. They are kept
here because they are CONCLUSIONS, and they avoid having to redo the path.*

This plan remains useful for METAL, but three of its assertions are denied by
the measure. Don't waste time redoing them.

1. **§2.5 “the cache sabotages itself”, “the −53% is a floor” — false.**
   The total emptying only cost**15 reconstructions out of 5,522**: the locality
   timing is so tight that throwing away the cache almost doesn't hurt. The eviction
   LRU (`a9983c4`) reports**+0.124 s**, or 0.4% of a run — and**0 s**in
   production, since`SplineBasisCache`is only called**18 times**per run of
   METAL_SINGLE (99.97% of callers pass`use_cache=False`).
2. **§5, work order: steps 1 and 2 only concern METAL.**Measured:
   INDEX, INDEX_SPLINE, RE and FIELD make**zero calls**to`SplineBasisCache`and
   **zero calls**to`get_nk_from_spline`. For everyday modules, it was necessary
   start with step 3 (profile the other modules).
3. **§1, table of durations: STRAT and DESIGN are undervalued**, because the
   Corresponding headless tests mock the calculation. Real figures in §2 above.

---

## 6. Raw diagnostics from 2026-08-02

Kept so as not to have to re-profile. Stack sampling at 5 ms, all
threads, real examples, auto-answered dialogs. The percentages
exceed 100% when several threads work in parallel.

### STRAT — before`33af845`(137 s)

```
691.4%_compute_theoretical_layer_profile <- ~200 njit dispatches per layer
226.2% threading.wait
104.4%_test_strategy_robustness_task
36.5% calculate_RT_vectorized_real_HL
32.7%_compute_dT_dd_per_layer
```

### STRAT — after (most expensive lines)

```
146.5% certus_strat_robustness.py:596 compute_batch_rmse
107.2% certus_strat_objectives.py:489 compute_T_front_profile
106.7% certus_strat_objectives.py:497 calculate_extrema_distances
67.7% certus_strat_objectives.py:376 precompute_matrix_cache_kernel
44.5% certus_strat_robustness.py:567 simulate_stack_robustness_batch
```

### DESIGN

```
872.9% certus_design_core.py:264 cost_numba_fast
85.4% gradient_oblique.py:1136
  1.5% certus_optimizers.py:438 <- all PGLOBAL machinery
```

**PGLOBAL itself only weighs 1.5%.**There is nothing to scratch in its code:
the remaining gains are in the objective function, or in the *number*
evaluations (therefore sampling, §4.1).

### RE — before`f6f9102`(lines)

```
32.1% certus_re_objectives.py:599 yR_all[idx], dR_all[idx, :] <- copies
17.7% certus_re_objectives.py:600 same for T
15.5% certus_re_objectives.py:434 grad_raw += np.dot(coeff, dy_vals)
12.2% certus_re_objectives.py:424 np.sum / np.dot on weights
10.8% gradient_oblique.py:869
```

### INDEX (❌ ~~6.5 s, with`--auto-yes`~~ →**12.8 s with`--auto-yes`**)

> This headline contradicted itself with its own paragraph below, which says that the
> “No” by default drops the run**from 12.8 s to 6.5 s**. Sliced ​​by measure
> from 2026-08-04:`--auto-yes`gives**12.425 s**on the 4-core machine. This is the
> body of text which was right —**6.5 s is the measurement WITHOUT`--auto-yes`**,
> i.e. the half-pipeline. The table in §2 showed the wrong figure.

```
[WORK] 54.5% certus_index_objectives.py:1755:__call__
[MAIN] 18.6% <frozen importlib._bootstrap_external>:145:_path_stat
[WORK] 11.0% llvmlite/binding/ffi.py:210 <- JIT DURING run
[MAIN] 7.5% <frozen importlib._bootstrap_external>:947:get_data
[WORK] 4.2% certus_index_objectives.py:1535:gradient
[WORK] 2.9% numba/core/compiler_lock.py:11
```

Without`--auto-yes`, the same run shows 26% in`_ask_keep_raw_or_smoothed`and
28 % in`_on_tlu_constrained_finished`: these are**modal QMessageBoxes**, not
of the calculation. And the default “No” skips the IR phase: the loading drops
from 5.7 s to 0.6 s and the run from 12.8 s to 6.5 s — we measured half of the pipeline.

### INDEX_SPLINE (1.6 sec)

```
25.2% spline_objective.py:517 spline_objective_mse_on_masked_grid
23.0% <frozen importlib._bootstrap_external>:145:_path_stat
19.7% spline_objective.py:973_fast_nk
8.5% llvmlite/binding/ffi.py:210
```

### Spline base cache — why §2 of the plan only applies to METAL

METAL_SINGLE, production code:

```
CACHE_CALLS=18 CACHE_CLEARS=0
NK_CALLS=66975 NK_DISTINCT_KNOTS=18402 NK_REPEAT=72.5%
NK_USE_CACHE_FALSE=66957 (99.97%)
```

The same run with`--force-cache`:

```
CACHE_CALLS=55611 CACHE_DISTINCT=5457 CACHE_HITS=50104 HITRATE=90.1%
```

Deterministic replay of the real sequence against the two eviction policies:

```
total dump (>500) 4.524 sec 5522 builds
eviction LRU (512) 4,400 s 5507 constructions
```

INDEX, INDEX_SPLINE, RE, FIELD:`CACHE_CALLS=0`and`NK_CALLS=0`.

### Tooling Pitfalls (Windows)

- Exit code**127**=`ERROR_PROC_NOT_FOUND`. Two causes encountered:
  QApplication picked up by the GC, and numpy/scipy imported before Qt.
- `os._exit()`**does not empty**the`stdout`buffers: a`print`before it is
  lost when the output is redirected. Flush explicitly.
- From bash (MSYS), pass script paths in**Windows form**
  (`C:/…`) to`python.exe`; the form`/c/…`fails with a misleading code 127.
- The timeout of the Bash tool is capped at 10 min: launch the campaigns
  measurement in the background.

---

## 7. Environmental reminders

- Venv:`C:\envs\certus\Scripts\python.exe`. Check what is actually imported:
  `python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"`.
- 🔴`.git/hooks/post-commit`pushes each commit to the**public**repository
  `nikonvr/CERTUS`. Currently renamed to`post-commit.disabled`.`--no-verify`does not
  not neutralize it.**Check its status before committing.**
- `numba.set_num_threads`is**thread-local**(checked at runtime): we can
  restrict a pool without affecting the rest of the process.
