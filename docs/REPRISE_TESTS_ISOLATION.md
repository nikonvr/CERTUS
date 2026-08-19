# RESUME — state leaks between tests (isolation)

**Session of 2026-08-02.**During:`docs/REPRISE_PERF.md`(performance).
This document covers**test isolation**, not performance.

> ✅**This work solves two rows of the “What is already red” table of
> `docs/REPRISE_PERF.md`**(`TestREAppSkeletonLoaders`and the 4 failures of
> `tests/unit/test_certus_ui.py`). This table has been updated accordingly.

---

## 0. State when resuming

✅**The fix is ​​applied and committed**to`refactor-corridors-mixins`
(2**test**files only, no production code):
`tests/ui/test_ui_module_imports.py`and`tests/unit/test_manual_rmse_grid_integration.py`.
**Nothing to apply**— directly attack the “remaining to be done” in §2.

To check that everything is in place:

```bash
C:\envs\certus\Scripts\python.exe -m pytest tests/ -q --no-cov -k "re_or reverse or objectives" -p no:cacheprovider
```

Expected:**637 passed, 4 skipped**.

The worktree`.claude/worktrees/admiring-proskuriakova-b242cf`was used for this work; he is
remained on`f6f9102`and**no longer needed**— can be deleted
(`git worktree remove --force .claude/worktrees/admiring-proskuriakova-b242cf`).

---

## 1. What is done

### 1.1 The main state leak

`tests/unit/test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`
was failing with`ValueError: not enough values ​​to unpack (expected 2, got 0)`in selection
wide, and passed singly.

**Guilty:**`tests/ui/test_ui_module_imports.py::test_ui_module_importable[certus.ui.certus_re_state_mixin]`

**Complete mechanism:**

1. `tests/headless/test_re.py`imports`CERTUS_RE`.`CertusREApp`inherits the defined mixin
   in module-object**M1**of`certus.ui.certus_re_state_mixin`; SO
   `CertusREApp._remove_re_skeletons.__globals__`**is**`M1.__dict__`.
2. `test_ui_module_importable`did`sys.modules.pop(name)`then re-imported, to
   force a fresh execution of the module. Result: a**second**module-object**M2**
   replaces M1 in`sys.modules`, and was never restored.
3. The RE test is done
   `monkeypatch.setattr("certus.ui.certus_re_state_mixin.remove_skeleton_loader", mock)`
   → it patches**M2**, while the living method reads in**M1**.
4. The real`remove_skeleton_loader`therefore runs on a`MagicMock`.
   `getattr(mock, "_certus_skeleton", None)`returns a MagicMock (non-`None`), and
   `loader, filt = data`unpacks a MagicMock whose`__iter__`is empty →`ValueError`.

This is also the cause of**4 failures of`tests/unit/test_certus_ui.py`**: same pattern of
`monkeypatch.setattr("<module>.<name>", …)`on an orphaned module.

Minimum repro (failed before, passes after):

```bash
C:\envs\certus\Scripts\python.exe -m pytest tests/headless/test_re.py "tests/ui/test_ui_module_imports.py::test_ui_module_importable[certus.ui.certus_re_state_mixin]" "tests/unit/test_certus_re.py::TestREAppSkeletonLoaders" -q --no-cov -p no:cacheprovider
```

**Fix**—`tests/ui/test_ui_module_imports.py`: function`_restore_module()`+ block
`finally`which puts the original module-object back into`sys.modules`**and**reassigns the attribute
on the parent package (`import_module`also rebinds it). If the module was not yet
imported, nothing is restored — the fresh import is then the normal state. The test keeps everything
his detection power (he performs the module well); no order dependencies added.

### 1.2 Second bug, independent, corrected in passing

`tests/unit/test_manual_rmse_grid_integration.py`→
`AttributeError: 'function' object has no attribute 'get_call_template'`.

The test set`NUMBA_DISABLE_JIT=1`**after**the import of the modules. The kernels already
decorated remain`Dispatcher`: the variable does not “de-jit” them, it does not apply
than the**following**compilations — including those that Numba triggers internally to
its own`@overload`(`np.empty_like`). On**cold**Numba cache,`clip_to_bounds`must
still be compiled and the overhead falls on a bare Python function → crash.

Masked by a hot`__pycache__`, therefore invisible on a well-established machine and fatal on a
new machine or CI. Reproducible at will:

```bash
NUMBA_CACHE_DIR="$(mktemp -d)" C:/envs/certus/Scripts/python.exe -m pytest tests/unit/test_manual_rmse_grid_integration.py -q --no-cov -p no:cacheprovider
```

**Fix:**removed the 4 lines`monkeypatch.*env("NUMBA_DISABLE_*")`, replaced
with a comment explaining why they should not be returned. Checked in cold cache
**and**hot.

### 1.3 Past verifications

| Verification | Result |
|---|---|
|`pytest tests/ -k "re_or reverse or objectives"`(official command) |**637 passed, 4 skipped**✅ |
| Target test in isolation | ✅ |
|`tests/ui/test_ui_module_imports.py`(108 tests) | ✅ |
|`test_ui_module_imports + test_certus_ui + test_certus_re`|**245 passed**✅ |
| Full suite`pytest tests/ -q --no-cov`**with**patch | 2774 passed, 8 skipped,**1 failed**(→ §2.1) |

---

##2. Still to be done

### 2.1 [P1]`test_spline_basis_cache_eviction_and_lock`— outdated test

`tests/unit/test_metal_optimizations.py:201`—**only remaining failure**of the full suite.

```
assert len(SplineBasisCache._cache) < 500
AssertionError: assert 510 < 500
```

**This is not an order leak: it fails deterministically, even in isolation.**
The test is behind a voluntary refactor of the production code:

- `certus/physics/certus_optical_models.py:371`→`_MAX_ENTRIES = 512`
- `certus/physics/certus_optical_models.py:485`→ true LRU:
  `while len(cls._cache) > cls._MAX_ENTRIES: cls._cache.popitem(last=False)`
- Comment line 476 explicitly documents the abandonment of the old guardrail
  `if len(_cache) > 500:_cache.clear()`.

The test inserts 510 unique keys after`clear()`. With a ceiling of 512, no eviction
does not take place and the final size is 510: the assertion encodes the**old**behavior.

Proposed correction, to be validated:

```python
# The cache is limited by an LRU, it is no longer completely emptied.
assert len(SplineBasisCache._cache) <= SplineBasisCache._MAX_ENTRIES
```

And to really test the eviction, loop over`_MAX_ENTRIES + 50`keys (510 < 512 does not
never triggers`popitem`), then check that the oldest key is gone.
**Open question: should this test check the LRU eviction, or only the boundary?**

### 2.2 [P2] Audit other manipulations of`sys.modules`

Same class of bug, untreated:

- `tests/unit/test_pure_imports.py:19-21`and`:43-45`—`del sys.modules[mod]`for everything
  module containing`"certus_core"`,**without restoration**. Harmless today
  (this file goes after its potential victims in alphabetical order), but everything
  File renaming can reverse the order. → same pattern`_restore_module()`.
- `tests/unit/test_materials_data.py:39,56`—`importlib.reload(md)`without restoring.
- `tests/unit/test_certus_core_coverage_boost.py:372-379`— replaces
  `sys.modules["PyQt6.QtSvgWidgets"]`by`None`; the restoration exists, to be rechecked.

Consider a shared fixture in`tests/conftest.py`(`sys_modules_sandbox`) rather than
to duplicate`_restore_module`in each file.

### 2.3 [P3] Anti-regression safeguard

Nothing prevents a leak from being reintroduced. Track: fixture`autouse`comparing identity
(`id()`) of`certus.*`module objects before/after each test module, and failing if
an object has been replaced. Weigh: execution time cost vs benefit.

### 2.4 [P4] Intermittent native crash — watch only

Duringafullsuiterun:`Windowsfatalexception:accessviolation`ina
thread`_bg_warmup`(`certus/core/_certus_physics_impl.py:1444`), to
`tests/unit/test_certus_metal_single_smoke.py`.**Not reproduced**in the next run (the rest
then went to the end). Likely race between the Numba warmup in the background and Qt.
Only treat if it comes back.

### 2.5 Pending decisions

- **Commit / push?**Nothing is committed. The`origin`remote is
  `https://github.com/nikonvr/CERTUS.git`(**public**) and the auto-push hook is
  disabled — see the`AGENTS.md`warning.
- **Where to apply?**Port the patch to`refactor-corridors-mixins`, or keep one
  dedicated branch?
- The full suite run**without**patch (encrypted reference) was interrupted at
  71 %; the before/after comparison on the entire sequence is therefore not completed. There
  targeted comparison (245 tests) is.

---

## 3. Pitfalls encountered (not to be repeated)

- The worktree created by the tool came from the**very first commit**(`38ffb68`, April),
  or 170 commits late — it didn't even contain the test in question. Check
  `git log --oneline -1`in a worktree before concluding anything.
- The hot Numba cache**hides**compilation bugs. For an honest audit:
  `NUMBA_CACHE_DIR="$(mktemp -d)"`.
- Confirmed: do not run two pytest sessions in parallel on this repository
  (see`docs/REPRISE_PERF.md`).
