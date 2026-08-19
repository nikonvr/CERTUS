# CERTUS improvement plan

Resumption document, written on 2026-08-02. Intended for an agent who takes over.
Read**after**`CLAUDE.md`, which gives the project context and conventions.

The construction sites are ordered:**each one makes the next safe**. Don't take them in the
disorder, in particular does not start with batch C.

---

## 0. Work rules — non-negotiable

### 0.1 The oracle above all else

`tests/oracle/`contains a TMM reference**independent**of`certus.physics`, validated
on four analytical identities. She has already unmasked two sign convention bugs
worth**46 and 82 points**of reflectance, both exact at k=0 therefore invisible to the
test suite then.

```bash
C:/envs/certus/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov # 237 tests, ~2 s
```

Before you touch any optical calculation, run it. Afterwards too.

### 0.2 A test that cannot fail is not a test

When you fix a bug,**check that the test you add fails on the code before
patch**.Reintroducethefault,runthetest,notethefailure,submitthefix.
Without this step you haven't proven anything.

Five assertions in this filing codified false behavior (see CLAUDE.md §7). Beware
of a test that seems to protect something absurd: perhaps it protects the bug.

### 0.3 Verifies an audit finding before applying it

Out of 13 audit findings verified by second opinion,**3 were irrelevant**— including one
classified “blocking” and one “high”:

| Observation | Why it was wrong |
|---|---|
| “the gradient kernel calculates a gain medium” |`phi_img = phi_base * ni`with negative`ni`gives`δ = φ_base·n̂`|
| “poorly normalized rear face gradient” | it coincides with the finite differences of its own cost at 3e-8 |
| “clipping`eps1`inconsistent with gradient” | no gradient kernel operates on`eps1`|

**Reproduce by execution before correcting.**A plausible and well-written observation is not
not a true observation.

### 0.4 `LOCKED`markers prove nothing

A proven bug carried one, with a docstring asserting precisely the opposite of what
the code did. Read the code.

### 0.5 Three traps that bite

- **Auto-push hook.**`.git/hooks/post-commit`pushes each commit to the repository
  **audience**.`--no-verify`does not neutralize it. Currently renamed to`.disabled`—
  check its status before any commit you don't want to publish.
- **`reports/`**contains the user's**scientific results**. It is
  git ignored, so git won't protest if you delete it, and it's unrecoverable.
- **`git gc`fails**(`fatal: bad tree object f26d9e1a`) because of an orphan commit
  packed. No impact on commits, but automatic recompaction does not work.

---

## 1. Starting state

| | |
|---|---|
| Tests |**2373 pass**, 0 failures |
| Branch |`refactor-corridors-mixins`, 138 commits ahead of`main`|
| Lint visible (project config) | 2 errors |
| Real lint (without`extend-ignore`) | see lot C |
| Root | 15 files |

Fourteen defects producing**false silent results**have been fixed (see
`git log`). The dominant reason to keep in mind during reviews:**a calculated value
correctly then lost**— a guard never read again, a mode resolved then overwritten, a
context imported then replaced by an empty dict, a mesh decoded then overwritten by the
following.

---

## 2. The construction sites

### Lot A — The remaining 6 audit findings

None produces false results: performance and statistical validity.
Process them in this order.

**A1. Correlated Sobol seeds**—`certus/core/certus_strat_robustness.py:414`
`local_seed = base_seed + noise_idx`causes seeds to collide between draws of
consensus: two different configurations can receive the same noise, which biases
the robustness estimate. Use a hash combining the two indices.
*Check*: generate the draws of two neighboring configurations, measure the correlation
crossroads of noise — it must be zero.

**A2.`SplineBasisCache`with variable nodes**— ✅**CLOSED 2026-08-06, by measurement.**

📏**Neither “the cache systematically misses” nor “it makes a database outdated”.**The positions of
nodes**are**in the key of`SplineBasisCache.get`— so no stale bases are returned by
omission. But this key is**rounded to 1e-6 µm**, which the observation had not anticipated, and it is
the third situation:

- `compute_metal_bilayer_gradient_analytic`consults the cache**directly**
  (`gradient_metal.py:319`), so neither`use_cache=False`nor`--force-cache`governs it;
- but this base is only used for the gradient with respect to the**values**of nodes. Whatever depends
  of their**positions**goes through the two non-memorized paths (lines 270 and 342);
- 📏 verified: a node displacement of**1e-9 µm**— a thousand times under rounding — causes the
  gradient of 2.1e-9. The optimizer is therefore**not**blind.

There remains an expiration of order`(dB/dλ) × 1e-6`on the value components only:
**bounded and negligible.**A2 therefore**does not**have absolute priority.

⚠️**What the measurement corrected for me**: I had first written a demanding test *zero*
consultation of the cache by the gradient. He was failing — and he was wrong, not the code. The guardrail
is not a call count, it is the**gradient response**to a shift under rounding.
Locked by`tests/oracle/test_spline_basis_cache_key.py`(4 tests).

**A3.`lru_cache`keys by`tuple()`**— ✅**DONE.**The key is constructed by`.tobytes()`, and
the on-site commentary documents the measurement: 35.9 µs per call on a 601-point grid, i.e.
85 % of hot path cost, spent making the key.

**A4. Spline basis reconstructed node by node**—`certus/physics/gradient_metal.py:291`
`num_knots`constructs`CubicSpline`instead of just one over the entire base.

**A5. Mixed f32/c64 precision with no effect**—`certus/core/certus_core.py:666`
The policy announces a SIMD gain that the TMM accumulators cancel. Either remove it,
or document it as inoperative. Measure before slicing.

**A6. Import cycle`physics ↔ core`**—`certus/physics/certus_opt_kernels.py:3`
See batch E, of which this is a special case.

---

### Lot B — Extending the oracle to gradients

**Why now.**The oracle covers R and T, normal and oblique incidence. He doesn't
**does not**cover analytical gradients — but a false gradient does not produce an error:
it makes the optimizer converge to a bad optimum, silently. Two of the flaws
corrected this session were exactly of this nature.

**What to do.**A systematic gradient-analytic harness against finite differences
centered, on a fixed corpus, for each function exporting a gradient:

- `compute_gradient_all_layers_analytic`(already spot checked, to be frozen)
- `compute_oblique_gradient_contrib_analytic`
- `compute_metal_bilayer_gradient_analytic`
- `_compute_gradient_analytic_kernel`
- the spline gradient of`spline_objective.py::_compute_analytic_gradient`

**Method.**The test must compare the gradient to the FD**of the cost that the function returns
itself**, not at a reconstructed cost — that's what makes the test litmus. With weights
**non-uniform**: several normalization bugs are only seen this way. Tolerance
relative 1e-6 for a central step of 1e-6.

**Risk**: zero, purely additive.

---

### Lot C — Eradicate`import *`

**Don't start there.**This batch is only safe once batch B is in place.

**The magnitude, measured on 2026-08-02**:

| Rule | Occurrences | What it means |
|---|---|---|
| F401 |**5,261**| unused imports |
| F405 |**3,156**| symbol coming from an`import *`, untraceable origin |
| F822 |**202**|`__all__`listing**non-existent**names |
| F403 | 75 | the`import *`s themselves |
| F821 | 29 | undefined names |

**Why it is the root of evil.**As long as a symbol can "come from nowhere",
any module extraction is a gamble — that's precisely how module extraction
`certus_opt_gradients.py`lost two`@njit`decorators and swapped a signature
public without anything indicating it.

**Processing order**:

1. **F822 first**— the 202 lying`__all__`, concentrated on 4 UI files
   (`certus_ui_widgets_factory.py`,`certus_base_app.py`,`certus_ui_utils.py`,
   `certus_ui.py`). These are names that do not exist: any`import *`on these modules
   raises`AttributeError`. Mechanical and risk-free correction: remove dead names.
2. **F403/F405 then**, module by module, never in bulk. For each`import *`,
   list the symbols actually used (`ruff --select F405`gives them) and
   import by name.
3. **F401 last**, and**never with`--fix`global**: some “unused” imports
   are intentional re-exports or recording side effects.

**After each module**:`pytest tests/oracle/ tests/core/ tests/unit/ -q`.

**Risk**: high if done in bulk, low module by module with the oracle in place.

---

### Lot D — The ratchet

**D1.`extend-ignore`can only shrink.**`pyproject.toml`hides 73 rules. Add
a test that reads the list and fails if it grows. A debt that can no longer be increased
eventually disappears.

**D2. The CI runs the real suite.**`lint.yml`only monitors`main`, which has 138 commits
delay, and does not run any tests.`release-windows.yml`executes 3 files out of 226.
- also trigger on`refactor-corridors-mixins`;
- run`pytest tests/ -q --no-cov`on`ubuntu-latest`— the validated Linux recipe is
  in CLAUDE.md §4 (Python 3.14.5, PyQt6 offscreen, numba 0.66) and runs much faster
  than`windows-latest`;
- do NOT touch`release-windows.yml`: the frozen build and checking the hashes of the
  lockfile are correct.

**D3. Invariants in property-based.**Hypothesis is already a dependency. Four
properties cover an entire class of bugs that no example test catches:
`R+T <= 1`on all passive stacking,`k >= 0`, reciprocity, gradient/FD agreement.

**D4. Contracts rather than examples.**Contract`isinstance(f, CPUDispatcher)`already exists
for 6 cores (`tests/oracle/test_tmm_oracle.py`). Extend it to public signatures:
a permuted signature went unnoticed because all the tests called by
keywords.

---

### Lot E — Architecture

To be done only after C: the cycles break much more easily when the
imports are self-explanatory.

- **Layer boundaries.**CLAUDE.md lists 12`utils → ui`inversions, 10
  `core → workers`, and a cycle`physics ↔ core`(29/22). The 3 inversions**at the level
  module**are the most harmful: import a calculation module loads PyQt6.
- **DTO from`workers`to`domain`**: this is what breaks the`core ↔ workers`cycle.
- **Divergent duplication.**`prepare_targets_vectorized`and`make_cost_function`exist
  duplicate in`gradient_utils.py`and`gradient_analytic.py`, with implementations
  **different**— copy of`gradient_utils`reads a`.val`attribute that`Target`does not have
  not. The anti-duplication safeguard has been whitelisted to let this pass
  (`tests/headless/test_code_duplication.py:75`, “Temporary tolerance”). To resolve,
  then remove the whitelist.
- **`certus/metal/`migration incomplete**:`CERTUS_METAL_SINGLE.py`(2721 l.) and
  `CERTUS_METAL_BILAYER.py`(2,850 l.) remained at the root.

---

### Lot F — Purge history`.env`

**Absolute prerequisite: revoke the key at console.anthropic.com.**Until it is
done, the rest is cosmetic — the key is public since commit`35348c0`of
3 July.

`.env`is no longer tracked since commit`8bb51b2`, so it won't restart. Stay there
history rewrite (`git filter-repo`), which requires a force-push and invalidates all
clones. To be done at once, in coordination with the user.

---

##3. What not to do

- **Do not run`ruff --fix`globally.**Some “unused” imports are
  voluntary re-exports.
- **Do not remove the three`certus_*.py`from the root**— these are fronts of
  re-export that tests import by bare name.
- **Do not recreate a session report at the root.**58 had been accumulated there, all
  contradictory between them.`git log`is the log.
- **Do not modify`calculate_transmission_single`**to “correct” its deviation with a
  Bare TMM: It deliberately includes backside reflection.
- **Do not trust`.coverage`**: it dates from July 13 and points to another folder.
- **Do not apply an audit finding without having reproduced it.**See §0.3.

---

##4. Verification, every step of the way

```bash
#fast,before/afteranyopticalcalculationmodification
C:/envs/certus/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov

#wide, before committing
C:/envs/certus/Scripts/python.exe -m pytest tests/core/tests/unit/tests/oracle/ \
    tests/domain/ tests/property/ -q --no-cov

# complete — count ~12 min, launch it in two halves to avoid waiting times
C:/envs/certus/Scripts/python.exe -m pytest tests/integration/tests/headless/ \
    tests/ui/ tests/performance/ tests/regression/ tests/utils/ -q --no-cov
```

Check what Python actually imports, if in doubt:

```bash
C:/envs/certus/Scripts/python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```
