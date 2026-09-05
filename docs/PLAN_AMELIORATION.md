# CERTUS improvement plan

Resumption document, written on 2026-08-02. Intended for an agent who takes over.
Read**after**`CLAUDE.md`, which gives the project context and conventions.

The construction sites are ordered:**each one makes the next safe**. Don't take them in the
disorder, in particular does not start with batch C.

> 🔴 **What survives, after the audit of 2026-09-06.** This document was written to be worked
> through, and **most of it has been.** What is still open:
>
> | still open | done, do not redo |
> |---|---|
> | **A6 / lot E** — the`physics ↔ core`cycle and the layer inversions | **lot A**, five findings of six |
> | **lot B** — extending the oracle to gradients | **F822 and F821**, both at 0 since 2026-08-19 |
> | **lot C** — import hygiene, F401 / F403 / F405 only | **D1**, the`extend-ignore`ratchet |
> | **D2 / D3 / D4** — CI, property-based, signature contracts | **lot F**, which describes a history that is not this repository's |
>
> ⚠️ **Three classes of defect were found in the document itself**, and each is annotated in
> place rather than quietly deleted, because the pattern is worth more than the correction:
> **rules copied from `CLAUDE.md` that went stale there** (§0, including the oracle count
> `CLAUDE.md` §16 records as refuted); **facts asserted with no command attached, three of
> three false** (§0.4); and **`file:line` references that had drifted onto unrelated
> statements** (A1's `:414`). Counts in §1 are a snapshot of 2026-08-02 — measure, do not
> compare.

---

## 0. Work rules — they are NOT here

🔴 **The rules live in `CLAUDE.md`, and this section used to copy them.** That copy went
stale, as copies do — it carried `# 237 tests, ~2 s` for the oracle suite, **the very figure
`CLAUDE.md` §16 records as refuted** (563 passed in 89,72 s, measured 2026-08-17, a factor 2,4
out on the count). Copying a rule does not reinforce it; it creates a second place for it to
rot. So:

| what it said | where it actually lives |
|---|---|
| the oracle comes first, run it before and after touching optics | `CLAUDE.md` §16 — **with the measured count and duration** |
| a test that cannot fail is not a test | `CLAUDE.md` §12, control 2 — the highest-yield check of the protocol |
| `LOCKED`markers prove nothing | `CLAUDE.md` §16 — the single-layer sign bug carried one |
| the auto-push hook, `reports/`, `git gc` | `CLAUDE.md` §2 and interdit 3 — ⚠️ **and all three were wrong here**, see the header |

**Only §0.3 below is kept**, because it is a measurement this document made and nothing else
records.

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

### 0.4 The three “traps” this document added — ALL THREE MEASURED FALSE, 2026-09-06

Kept as a worked example of why §0 was cut, not as guidance. Each was stated flatly, none
carried its command, and each is contradicted by one line of shell:

| what §0.5 asserted | measured on this snapshot |
|---|---|
| “`.git/hooks/post-commit`pushes each commit […] currently renamed to`.disabled`” | `core.hooksPath` **unset**, `.git/hooks/`holds **no**`post-commit`at all. The hook is *armable*, not armed — `CLAUDE.md` §2 has the measured version |
| “`reports/`[…] is git ignored, so git won't protest if you delete it” | 🔴 **backwards.** `git check-ignore reports/` exits **1** (not ignored) and `git ls-files reports \| wc -l` returns **2141** tracked files. Interdit 3 of `CLAUDE.md` is the authority |
| “`git gc`fails (`fatal: bad tree object f26d9e1a`)” | `git cat-file -t f26d9e1a` → *Not a valid object name*. `git fsck --connectivity-only` exits **0**, reporting only dangling commits, which are normal |

🔑 **The pattern, and it is the one this repository fights**: three plausible, well-written
sentences, no command attached to any of them, all three wrong. That is interdit n° 9 —
*soit tu colles la sortie, soit tu écris « je n'ai pas mesuré »*.

---

## 1. Starting state — A SNAPSHOT OF 2026-08-02, NOT A REFERENCE

⚠️ **Do not compare anything to this table.** Every row below is a count that changes as soon
as somebody works: the test total moves with each added test, the commit lead moves with each
commit. `CLAUDE.md` §2 makes the same point about test counts, which it carried wrong four
times running (2 300, 2 301, 2 310, 2 450) before dropping the number for the only criterion
that survives — `0 failed`.

| | 2026-08-02 |
|---|---|
| Tests | 2373 pass, 0 failures |
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

### Lot A — ✅ **FIVE OF THE SIX ARE CLOSED** (verified in the code, 2026-09-06)

⚠️ **This heading said “the remaining 6 audit findings” and listed them as work to do.
Only A6 is left.** Verified against the source, not against a report — each closure below
was read in the file that carries it.

| | state | evidence in the code |
|---|---|---|
| A1 Sobol seeds | ✅ **fixed** |`certus_strat_robustness.py:2153`|
| A2 `SplineBasisCache` | ✅ closed by measurement, 2026-08-06 | see below |
| A3 `lru_cache`keys | ✅ done |`.tobytes()`|
| A4 spline basis per knot | ✅ **fixed** |`gradient_metal.py:307`|
| A5 f32/c64 policy | ✅ **measured and reverted** |`certus_core.py:663-680`|
| A6 cycle`physics ↔ core`| 🔴 **open** | see lot E |

**A1. Correlated Sobol seeds**— ✅ **FIXED.** The prescription was “use a hash combining the
two indices”, and that is what the code now does:

```python
local_seed = (base_seed * 2_654_435_761 + noise_idx * 40_503) % (2**31)
```

`certus/core/certus_strat_robustness.py:2153`, with the collision it repairs documented
in place at`:2135-2138`— *(seed 43, level 0)* and its neighbour *“both gave
local_seed = 43 — the SAME noise”*. ⚠️ **The`:414`this line used to cite now points at
`val = idx_dict[float(w)]`**, an unrelated statement: line numbers drift, which is why
`CLAUDE.md` §22 says to **cite the function, not the number**.

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

**A4. Spline basis reconstructed node by node**— ✅ **FIXED.** The basis is now memorised by
`SplineBasisCache`instead of being rebuilt at every gradient call, and the comment at
`certus/physics/gradient_metal.py:307`states the cost that was removed, measured on a
601-point grid: **1,0 ms for 5 knots, 1,6 ms for 8, 3,9 ms for 20** — about 0,9 s over 500
evaluations, 3,4 s over 2000, for a result identical from one call to the next as long as the
knots do not move.`extrapolate=False`is part of the key, so both variants coexist without
mixing. 🔑 Read this together with **A2**, which bounds what the cache can get wrong.

**A5. Mixed f32/c64 precision with no effect**— ✅ **MEASURED, AND THE POLICY DID NOT HOLD.**
The instruction was *“measure before slicing”*; it was measured on 2026-08-02, on
`compute_TMM_generic`, 12-layer stack, best of 5 passes of 5000 calls:

```
c128/f64 : 0.9045 us/call   R error = 0          (reference: TMM oracle)
c64/f32  : 0.9144 us/call   R error = 2.7e-08
```

**1,1 % slower for eight orders of magnitude of precision** — LLVM does not vectorise
complex64 better than complex128 on this loop, and the conversions cost more than they save.
Reverted to double precision;`get_precision_config()`is now a stub always returning`False`
(`certus/core/certus_core.py:657-680`). 🔑 **Why it mattered beyond speed**: 2,7e-08 on R sits
below spectrophotometer noise, but with a finite-difference step`h = 1e-6`it becomes **~3 %
error on the derivative** — a wrong gradient does not raise, it converges somewhere wrong.

**A6. Import cycle`physics ↔ core`**— 🔴 **STILL OPEN**, and the only survivor of this lot.
See lot E, of which it is a special case — **and take the counts from `CLAUDE.md` §13**, not
from lot E's own line, which carried four refuted figures.

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

**The magnitude, measured on 2026-08-02 — and remeasured since**:

| Rule | 2026-08-02 | remeasured 2026-08-19 (`CLAUDE.md` §27) | What it means |
|---|---|---|---|
| F401 |**5,261**| 5 293 | unused imports |
| F405 |**3,156**| 3 122 | symbol coming from an`import *`, untraceable origin |
| F822 |**202**| 🟢 **0** |`__all__`listing**non-existent**names |
| F403 | 75 | 52 | the`import *`s themselves |
| F821 | 29 | 🟢 **0** | undefined names |

🟢 **The two dangerous rules are already at zero.**`ruff check . --select F821,F822`returns
`All checks passed!`across the whole repository. Step 1 below — “the 202 lying`__all__`” — is
**done**; do not go looking for them. What is left is import hygiene (F401/F403/F405), which
is a different and much milder class of risk.

**Why it is the root of evil.**As long as a symbol can "come from nowhere",
any module extraction is a gamble — that's precisely how module extraction
`certus_opt_gradients.py`lost two`@njit`decorators and swapped a signature
public without anything indicating it.

**Processing order**:

1. ~~**F822 first**— the 202 lying`__all__`, concentrated on 4 UI files
   (`certus_ui_widgets_factory.py`,`certus_base_app.py`,`certus_ui_utils.py`,
   `certus_ui.py`).~~ ✅ **DONE** — F822 and F821 both measure **0** since 2026-08-19.
2. **F403/F405 then**, module by module, never in bulk. For each`import *`,
   list the symbols actually used (`ruff --select F405`gives them) and
   import by name.
3. **F401 last**, and**never with`--fix`global**: some “unused” imports
   are intentional re-exports or recording side effects.

**After each module**:`pytest tests/oracle/ tests/core/ tests/unit/ -q`.

**Risk**: high if done in bulk, low module by module with the oracle in place.

---

### Lot D — The ratchet

**D1.`extend-ignore`can only shrink.**~~`pyproject.toml`hides 73 rules. Add a test that reads
the list and fails if it grows.~~ ✅ **DONE** — the guard is`tests/oracle/test_lint_debt_ratchet.py`,
and the ban on growing the list is interdit n° 2 of`CLAUDE.md`. ⚠️ **The count is 68 rules,
not 73** (counted 2026-08-19); this line carried a figure nobody had recounted.

**D2. The CI runs the real suite.**`lint.yml`only monitors`main`, which is far behind, and
does not run any tests.`release-windows.yml`executes 3 files out of 226. ⚠️ **“138 commits
delay” was a 2026-08-02 count — recount it**, it moves with every commit.
- also trigger on`refactor-corridors-mixins`;
- run`pytest tests/ -q --no-cov`on`ubuntu-latest`. 🔴 **This line pointed at a “validated
  Linux recipe in CLAUDE.md §4” THAT DOES NOT EXIST** — `CLAUDE.md`contains no Linux recipe
  anywhere, and its Python is **3.14.7**, not the 3.14.5 quoted here (numba 0.66.0 was
  right). **The recipe has to be written and measured before this step is actionable**;
  do not cite it as though it were already validated;
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

- **Layer boundaries.**🔴 **The four figures this line carried are refuted.** It said
  “12`utils → ui`, 10`core → workers`, and a cycle`physics ↔ core`(29/22)”. Recounted by
  AST on 2026-08-19 (`CLAUDE.md` §13): **11**`utils → ui`, 10`core → workers`, and the cycle
  is **`physics → core` 23** plus **`core → physics` 29** — the`↔ 29/22`notation was both
  wrong and ambiguous about direction. **Read the count there, not here.** The 3 inversions
  **at module level**are the most harmful: importing a calculation module loads PyQt6.
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

### Lot F — Purge history`.env` — 🔴 **DESCRIBES A HISTORY THAT IS NOT THIS ONE**

📏 **Measured 2026-09-06, and nothing in this lot reproduces:**

```
git ls-files .env                                    ->  0
any file named .env, anywhere, --diff-filter=A, all refs  ->  none
git cat-file -t 35348c0   ->  fatal: Not a valid object name
git cat-file -t 8bb51b2   ->  fatal: Not a valid object name
git rev-list --all --count  ->  610      first commit: 38ffb68, 2026-04-27
```

**No`.env`has ever been tracked in this repository**, at any path, in any of its 610
commits — and neither cited hash exists here. So there is nothing to purge, and
`git filter-repo`is **not** to be run for this reason.

⚠️ **What this does NOT establish.** That a credential was never exposed *somewhere else* —
another snapshot, another remote, a history since re-initialised. This measurement covers
this repository and no other. **Rotating a key one is unsure about costs minutes and closes
the question whichever way it went**; that call belongs to 👤, and it is the only action that
does not depend on trusting a document this audit has just found wrong three times over.

🔑 **The real history problem is a different one, and it is still open**:`CLAUDE.md` §2
records that `f4c05c6` removed personal data from the **working tree only** — a thesis text
and six `.xls` remain readable at `f4c05c6^` on the public remote. That one is real, measured,
and unfixed.

---

##3. What not to do

- **Do not run`ruff --fix`globally.**Some “unused” imports are
  voluntary re-exports.
- **Do not remove the three`certus_*.py`from the root**— these are fronts of
  re-export that tests import by bare name.
- **Do not recreate a session report at the root.**They had been accumulated there, all
  contradictory between them.`git log`is the log. ⚠️ *This line said “58”, `CLAUDE.md`
  interdit n° 10 says **103**. The count is not the point and is not maintained in two
  places — the ban is.*
- **Do not modify`calculate_transmission_single`**to “correct” its deviation with a
  Bare TMM: It deliberately includes backside reflection.
- **Do not trust`.coverage`**: it dates from July 13 and points to another folder.
- **Do not apply an audit finding without having reproduced it.**See §0.3.

---

##4. Verification, every step of the way

🔴 **The three commands here were UNRUNNABLE**: their paths had lost their separating spaces
(`tests/core/tests/unit/tests/oracle/`is one nonexistent path, not three). Repaired and
re-checked on 2026-09-06 — the eleven directories named below all exist.

```bash
# fast, before AND after any change to an optical calculation
C:/envs/certus/Scripts/python.exe -m pytest tests/oracle/ -q --no-cov
```

```bash
# wide, before committing
C:/envs/certus/Scripts/python.exe -m pytest tests/oracle/ tests/unit/ tests/core/ tests/domain/ tests/property/ -q --no-cov
```

```bash
# complete
C:/envs/certus/Scripts/python.exe -m pytest tests/integration/ tests/headless/ tests/ui/ tests/performance/ tests/regression/ tests/utils/ -q --no-cov
```

⚠️ **The “~12 min” this section promised has been removed, not corrected**: a duration without
its machine and its cache state is worthless (`CLAUDE.md` §11-1), and the same suite is known
to run 216 s warm against 784 s cold on the reference i5-8250U. **The criterion is`0 failed`,
never a stopwatch.**

Check what Python actually imports, if in doubt:

```bash
C:/envs/certus/Scripts/python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"
```
