
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # SYM Numba V2 Specification

## Objective

Define a high-performance and numerically stable V2 for SYM strategy mining with strict contractual block compliance.

## Current limits observed

- Block validity kernel scales poorly on large stacks (nested loops + repeated scans).
- Floating-point wavelength matching is inconsistent across modules.
- Post-DP Python scoring adds overhead and duplicates work.

## V2 design goals

- Keep current strategy semantics and contractual `n_blocks` invariants.
- Move as much SYM scoring as possible into compiled kernels.
- Use integer wavelength indexing to eliminate float-key drift.
- Preserve deterministic behavior for robust ranking.

## Proposed architecture

1. **Wavelength indexing layer**
   - Build a global sorted wavelength list per run.
   - Convert each layer candidate map from `wl -> cost` to `wl_idx -> cost`.
   - Keep a reverse `wl_idx -> wl` map for reporting only.

2. **Dense/compact candidate tensors**
   - Store per-layer candidate costs in dense or CSR-like arrays.
   - Store SYM bonus and layer importance in aligned arrays by `wl_idx`.

3. **Kernel-side SYM scoring**
   - DP transition includes:
     - base block cost
     - local SYM contribution
     - continuity reward when `wl_idx` unchanged across adjacent blocks
   - Scoring modes:
     - `pre`
     - `post`
     - `hybrid`
   - Keep mode parity with current Python path.

4. **Compact DP path reconstruction**
   - Replace full path copies per candidate with parent pointers:
     - previous split index
     - previous candidate rank
     - selected `wl_idx`
   - Reconstruct only top paths at the end.

5. **Deterministic ranking mode**
   - Deterministic tie resolution:
     - absolute + relative epsilon
     - secondary key on `origin` and `strategy_id`
   - Optional strict deterministic mode for CI.

## Contract and validation invariants

- `len(blocks) == n_blocks`
- contiguous coverage from layer `0` to `num_layers`
- `num_layers == end - start` per block
- all block boundaries in `[0, num_layers]`

## Migration plan

### Phase 1 (safe bridge)
- Keep existing Python implementation as reference backend.
- Add `wl_idx` preprocessing and shadow-compare outputs.
- Introduce benchmarks and equivalence tests.

### Phase 2 (kernel adoption)
- Enable V2 kernels behind feature flag:
  - `sym_numba_v2_enable`
- Compare rank stability and wall-clock performance.

### Phase 3 (default switch)
- Promote V2 as default once:
  - output equivalence validated
  - performance gain proven
  - deterministic mode stable in CI

## Acceptance criteria

- Same or better best-strategy robustness score distribution.
- No contract violations in generated strategies.
- Reduced runtime on representative large stacks.
- Stable results with fixed seeds in sequential and parallel execution.


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.