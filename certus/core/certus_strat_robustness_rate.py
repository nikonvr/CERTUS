"""CERTUS STRAT ROBUSTNESS - the deposition-rate variants of a strategy (moved out of certus_strat_robustness.py, S5.2)."""

import itertools
import logging
import time
import numpy as np
from typing import Any

from certus.core.certus_strat_robustness_wrappers import _IdxWrapper


#: 🔴 RAISED FROM 3 TO 40 ON 2026-08-22, together with `RATE_VARIANT_TOP_N_DEFAUT`. The two go
#: TOGETHER: 40 variants on 50 parents cost 2 000 evaluations, against 12 923 for 3 variants
#: on all of them. The search goes thirteen times deeper for one sixth of the cost.
RATE_MAX_VARIANTS_PER_STRATEGY: int = 40


#: How many strategies, among the best ranked, receive Rate variants.
#: `0` = all of them, the behaviour before 2026-08-22.
RATE_VARIANT_TOP_N_DEFAUT: int = 50


#: Below this many layers per block, a "block boundary" says nothing -- every layer is
#: one. See the measurement in `_rate_candidate_layers`.
RATE_MIN_LAYERS_PER_BLOCK: float = 3.0


#: Below this growth-time swing (T_max - T_min while the layer is deposited), a layer's
#: own optical signal is judged too poor to trigger a stop precisely -- the SAME physical
#: quantity `dynamics_threshold` gates in Phase A (`calculate_dynamics_ULTIMATE`), not the
#: end-state curvature `_calculate_strategy_spectral_resolution` uses for the slit. Kept as
#: its own name because CLAUDE.md §22 already calls it that: "swing < SWING_MIN".
RATE_SWING_MIN_DEFAULT: float = 0.025


#: 👤 2026-08-19: "rate is forbidden on the first 2 layers! but absolutely not on the
#: last one". Both bounds of the code were WRONG, in opposite directions.
#:
#: 🔑 THE LOWER BOUND HAS A PHYSICAL REASON, and it gives exactly 2. The rate factor is
#: computed on the layers of the SAME PARITY deposited BEFORE layer i
#: (`certus_strat_growth.py`, `range(i_layer-2, -1, -2)`). For i = 0 and i = 1 that loop is
#: empty: `n_ref = 0`, the machine has deposited nothing it could derive a rate from.
#:
#: 🔴 AND THE KERNEL DID NOT REFUSE IT -- it fell back SILENTLY on POEM (guard `n_ref > 0`).
#: A variant labelled `RATE_L1` therefore simulated pure POEM. 📏 Measured on 2026-08-19 over
#: 24 581 placements: layer 1 was indeed proposed twice. Two results carried a label that
#: lied about what had run. It is now refused upstream.
RATE_MIN_LAYER: int = 2


def _wl_de_la_couche(strategy: dict[str, Any], layer: int) -> float | None:
    """The wavelength the strategy monitors for this layer, or None outside any block."""
    for blk in strategy.get("blocks") or []:
        if int(blk.get("start", 0)) <= layer < int(blk.get("end", 0)):
            wl = blk.get("wavelength")
            return float(wl) if wl is not None else None
    return None


def _rate_swing_candidates(strategy: dict[str, Any], num_layers: int,
                           swing_ctx: _RateSwingContext) -> list[int]:
    """Layers where a Rate is NEEDED: the growth-time swing is below `dynamics_threshold`.

    🔑 2026-08-19, docs/archives/CHANTIER_RATE.md contradiction C: `_rate_swing_candidates` and
    `_rate_candidate_layers` answer two DIFFERENT questions on purpose --  where a Rate
    costs nothing (block boundary) versus where it is needed (poor optical signal). Kept
    SEPARATE, ADDITIVE: this function never removes what the boundary criterion already
    offers, only widens the pool the cap is applied to afterward.

    ⚠️ Deliberately bypasses `RATE_MIN_LAYERS_PER_BLOCK`. That guard exists because a
    "boundary" is meaningless once every layer is one (48-block degenerate case,
    §24-45's sixfold-cost measurement) -- a property of BLOCK STRUCTURE. Swing is a
    property of the LAYER'S OWN SIGNAL, independent of block structure, so the guard that
    protects one criterion does not apply to the other. This is what closes contradiction
    B of the audit: strategies with fine blocks had ZERO Rate candidates of any kind.
    """
    layer_to_wl: dict[int, float] = {}
    for blk in strategy.get("blocks") or []:
        wl = blk.get("wavelength")
        if wl is None:
            continue
        for layer in range(int(blk.get("start", 0)), int(blk.get("end", 0))):
            layer_to_wl[layer] = float(wl)

    out: list[int] = []
    # 👤 2026-08-19: the last layer is NO LONGER excluded (it was, "same final-layer
    # exclusion as A24"), and the first two now are, explicitly.
    for layer in range(RATE_MIN_LAYER, num_layers):
        wl = layer_to_wl.get(layer)
        if wl is None:
            continue
        swing = swing_ctx.swing_at(layer, wl)
        if swing < swing_ctx.threshold:
            out.append(layer)
    return out


def _rate_candidate_layers(strategy: dict[str, Any], num_layers: int,
                           cap: int | None = None,
                           swing_ctx: _RateSwingContext | None = None) -> list[int]:
    """Layers where a Rate is CHEAPEST: the last layer of each block.

    👤 2026-08-11: *"test the rate on layers i whose control wavelength changes at layer
    i+1, because there will be no POEM on the next layer anyway"*. Verified in the
    kernel and it is exact -- `block_start[i+1] = i+1` at a wavelength change, so
    `n_hist = 0` and the next layer starts with no inherited anchors whatever layer i
    did. 14-10 lists three costs for a Rate layer and a block boundary already pays two
    of them: the lost anchors, and the turning-point count that restarts anyway.

    🔴 THE FINAL-LAYER EXCLUSION IS GONE -- 👤 2026-08-19: *"rate is forbidden on the first 2
    layers! but absolutely not on the last one"*. It had been excluded on the grounds
    that "the two pull opposite ways", which was never a reason to forbid, only a reason to
    measure. 📏 And the measurement now says the exclusion was removing the BEST candidate:
    across 24 581 observed placements the final layer appeared **0 times** while the
    next-to-last was the single most chosen position (2 530). The mechanism established the
    same day says why -- a Rate layer removes its own crash but hands its open-loop error to
    everything DOWNSTREAM; the final layer has no downstream, so it is the cheapest Rate
    placement in the whole stack.

    ⚠️ Layers 0 and 1 are now refused HERE instead of degrading silently in the kernel --
    see `RATE_MIN_LAYER`.

    🟠 C1, MEASURED THE SAME DAY -- and the warning was too strong. The pool does change: on
    r75x2 the native placements go 291 -> 314 and layer 74 goes 0 -> 112, displacing 71. But
    a full replay of the tail sweep gives a MAXIMUM deviation of 0.03 % over five cuts, and
    the cliff does not move. Earlier tail campaigns stay readable. See
    docs/archives/CHANTIER_RATE.md §9 -- and note that the 0.03 % is the ROUNDING order, which is the
    only residual the arithmetic allows.

    🔑 `swing_ctx`, added 2026-08-19: when given, NEEDED layers (poor growth-time swing)
    are added to the pool alongside CHEAP layers (block boundaries), before the cap is
    applied. `None` by default -- the golden rule holds bit for bit at the default.
    """
    blocks = strategy.get("blocks") or []
    out: list[int] = []
    # 🔴 A "block boundary" only carries information when blocks ARE blocks. Measured
    # 2026-08-11: on a 48-block strategy -- one wavelength per layer -- EVERY layer is a
    # boundary, and the placement degenerates into the exhaustive sweep this was chosen
    # to avoid: 47 variants from a single strategy, 1122 over the reference ranking, a
    # sixfold Monte-Carlo cost. Below this many layers per block the insight is vacuous.
    if blocks and num_layers / len(blocks) >= RATE_MIN_LAYERS_PER_BLOCK:
        for blk in blocks:
            end = int(blk.get("end", 0))
            last = end - 1                       # last layer of this block
            # 👤 2026-08-19, ENGRAVED: forbidden on the first 2 layers, allowed everywhere
            # else -- the last one INCLUDED. The former bound `< num_layers - 1` excluded the
            # last layer and let layers 0 and 1 through.
            if RATE_MIN_LAYER <= last < num_layers:
                out.append(last)
    # 🔴 THE TWO CRITERIA SHARE THE CAP, THEY DO NOT EVICT EACH OTHER. Measured on
    # 2026-08-19: sorting the whole pool by depth and then cutting at `cap` let low-swing,
    # deeper layers evict ALL the block boundaries (candidates [31,32,33] instead of
    # [13,21,29]). That was not the intent -- the NEED criterion must add to the COST one,
    # not replace it. Each therefore keeps half of the cap, the remainder going to the
    # other if it has no use for it.
    if swing_ctx is not None:
        besoin = [x for x in _rate_swing_candidates(strategy, num_layers, swing_ctx)
                  if x not in out]
        if besoin:
            budget = RATE_MAX_VARIANTS_PER_STRATEGY if cap is None else cap
            besoin.sort(reverse=True)
            out.sort(reverse=True)
            part = max(1, budget // 2)
            garde_cout = out[: budget - min(len(besoin), part)]
            garde_besoin = besoin[: budget - len(garde_cout)]
            out = garde_cout + garde_besoin
    if not out:
        return []
    # Deepest first: A24 measured that a Rate layer inherits an error falling as
    # 1/sqrt(n) with the number of reference layers of its material, so it is at its
    # most accurate late in the stack -- which is also where 17-36 measured that every
    # crash happens. The cap therefore keeps the boundaries that matter most.
    #
    # 🔴 A MARGIN-ORDERED KEY WAS TRIED ON 2026-08-12 AND REVERTED THE SAME DAY. Keep
    # this record: the hypothesis is attractive and will be proposed again.
    #
    # 📏 What was measured. Pairing each Rate variant with the parent it came from, on
    # the two N=300 references, gain against the parent split by the parent's margin:
    #
    #     parent margin SMALL  +0.7 % / +0.2 %      parent margin LARGE  -0.9 % / -0.1 %
    #     deep layer  +0.6 % / -0.0 %               early layer  +0.5 % / +0.2 %
    #
    # Depth carries no signal; the margin does, and it flips sign on both stacks. The
    # inference drawn from it was to place the Rate layer at the LOWEST-MARGIN block
    # boundary. 📏 A validation run said the opposite: median gain -1.13 % against
    # -0.3 %, 5 variants improving against 9 degrading (was 14 against 13).
    #
    # 🔑 THE ERROR, AND IT IS A METHOD ERROR, NOT AN ARITHMETIC ONE. The quantity
    # measured was `critical_layer.margin_in_A` -- a property of the WHOLE STRATEGY,
    # one number per candidate. The rule written from it ordered LAYERS WITHIN a
    # strategy. Those are different quantities, and the measurement never spoke about
    # the second. What the data actually supports is "a Rate layer helps strategies
    # whose critical layer is close to giving way", which is a rule about WHICH
    # STRATEGIES to expand, not about WHERE to put the layer. That hypothesis is still
    # open and needs its own experiment -- do not implement it from these numbers
    # either.
    out.sort(reverse=True)
    # `cap=None` keeps the historical truncation, word for word. An explicit cap is only
    # passed by the multi-layer path below, which needs the FULL candidate list before it
    # can build combinations from it.
    return out[:RATE_MAX_VARIANTS_PER_STRATEGY if cap is None else cap]


class _RateSwingContext:
    """Bundles what `calculate_dynamics_ULTIMATE` needs to re-evaluate the growth-time
    swing of ONE layer at the wavelength a strategy already chose for it.

    🔒 Calls the SAME canonical function Phase A uses (interdit 7) -- restricted to a
    single wavelength instead of the whole scan grid, and memoized per (layer, wl)
    because the same block wavelength recurs across the many Rate-boundary candidates of
    a strategy, and across strategies that share a parent.
    """

    __slots__ = ("_cache", "all_wls", "clues_at_wl", "n_absents", "n_calls", "nominal_matrix_cache",
                 "p_thick_nominal", "threshold")

    def __init__(self, p_thick_nominal: Any, clues_at_wl: Any, nominal_matrix_cache: Any, all_wls: Any,
                threshold: float) -> None:
        self.p_thick_nominal = p_thick_nominal
        self.clues_at_wl = clues_at_wl
        self.nominal_matrix_cache = nominal_matrix_cache
        self.all_wls = all_wls
        self.threshold = threshold
        self._cache: dict[tuple[int, float], float] = {}
        self.n_calls = 0
        self.n_absents = 0

    def swing_at(self, layer: int, wl: float) -> float:
        from certus.utils.certus_strat_service import calculate_dynamics_ULTIMATE
        key = (layer, round(wl, 6))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        self.n_calls += 1
        # 🔑 A ONE-ENTRY DICTIONARY IS ENOUGH, and that is what cleanly avoids the trap
        # that killed a run on 2026-08-19. `calculate_dynamics_ULTIMATE` only looks at the
        # wavelengths present in its `wls_array` -- a single one here. It is therefore given a
        # real dict built by indexed access, which the pipeline's shared-memory object supports
        # just as well as a native dict. No need to require `.items()` on the source any more.
        # 🔴 AND THE DIAGNOSTIC OF `calculate_dynamics_ULTIMATE` IS MUTED DURING THE CALL.
        # It warns when `nanstd(dyn_vals)` is zero, which detects a genuinely flat layer when
        # it is given the WHOLE wavelength grid. Here it is given only ONE: the standard
        # deviation of a single value is 0 by construction, so the warning fires on EVERY call
        # and teaches nothing. 📏 Measured on 2026-08-19: two WARNING lines per call, i.e. tens
        # of thousands on a real run -- an unusable log and a non-zero writing cost. The level
        # is restored afterwards.
        # 🔴 ACCESS GOES THROUGH `_IdxWrapper`, defined IN THIS FILE. `clues_at_wl` is not
        # necessarily a dict indexable by float -- it may arrive as a shared-memory object or an
        # indexed sequence. The wrapper absorbs both, and returns None instead of raising. I
        # wrote a direct access twice before noticing, and both times a full run died midway.
        try:
            clue = _IdxWrapper(self.clues_at_wl)[float(wl)]
        except (KeyError, TypeError, IndexError):
            clue = None
        if clue is None:
            # 🔑 SAFE DEGRADATION: without indices, the layer is declared WELL SEEN (infinite
            # swing), so it stays optical. The criterion loses reach, it does not fabricate a
            # false Rate layer -- and the counter below makes it visible in the log.
            self.n_absents += 1
            self._cache[key] = float("inf")
            return float("inf")
        # 🔴 AND THE DIAGNOSTIC OF `calculate_dynamics_ULTIMATE` IS MUTED DURING THE CALL.
        # It warns when `nanstd(dyn_vals)` is zero, which detects a genuinely flat layer when
        # it is given the WHOLE wavelength grid. Here it is given only ONE: the standard
        # deviation of a single value is 0 by construction, so the warning fires on EVERY call
        # and teaches nothing. 📏 Measured on 2026-08-19: two WARNING lines per call, i.e. tens
        # of thousands on a real run.
        _log_tf = logging.getLogger("ThinFilm")
        _niveau = _log_tf.level
        _log_tf.setLevel(logging.ERROR)
        try:
            dyn = calculate_dynamics_ULTIMATE(
                np.array([wl], dtype=np.float64), layer, float(self.p_thick_nominal[layer]),
                {float(wl): clue}, self.nominal_matrix_cache, self.all_wls,
            )
        except Exception:                                   # noqa: BLE001
            # Same rule: degrade, count, do not kill a 25-minute run.
            self.n_absents += 1
            self._cache[key] = float("inf")
            return float("inf")
        finally:
            _log_tf.setLevel(_niveau)
        val = float(dyn[0]["dynamics"]) if dyn else float("inf")
        self._cache[key] = val
        return val


def _optical_prefix_variants(strategies: list[dict[str, Any]], params: Any,
                             num_layers: int, logger: Any) -> list[dict[str, Any]]:
    """`n` optical layers, the rest at PERFECT thickness -- the SEEL(n) curve of 👤.

    👤 2026-08-19: *"20 optical layers plus the rest with PERFECT thicknesses, we compute
    SEEL20; then 21; likewise up to SEEL75. We look at the curve SEEL = f(n) and deduce
    from it where the optical monitoring becomes a problem."* Then: *"careful, the curve
    is not necessarily monotonic, it must be plotted ENTIRELY."*

    🔑 WHAT MAKES THIS MEASUREMENT DIFFERENT FROM EVERYTHING ELSE: it is a DECOMPOSITION,
    not a search. Each `n` is ONE measurement, never a maximum over candidates -- the
    winner's curse (+12.9 % measured on 08-15, and it COMPOUNDS in a greedy search) does
    not apply.

    🟢 AND THE KERNEL NEEDS NOTHING. `_build_layer_wavelengths_from_strategy` initialises
    `layer_wavelengths` to ZERO and fills only the layers covered by a block; the kernel
    then takes the `if wl < 0.1` branch (`certus_strat_growth.py`) and returns EXACTLY the
    nominal thickness, margins at 1e18 so a crash is impossible. Truncating the blocks to
    `n` is enough.

    ⚠️ "PERFECT" IS NOT "RATE". A Rate layer inherits the factor A; a perfect layer
    inherits nothing. SEEL(n) is therefore a LOWER BOUND, not the prediction of the real
    strategy. 🔴 And the difference between the two does NOT cleanly ISOLATE the cost of
    Rate, contrary to what I had written: `A` is estimated on the optical layers of the
    prefix, so a degraded prefix gives a degraded `A`. The two costs are COUPLED, not
    additive.

    🔑 The two curves share the work, and this is structural:
        crash(n)  MONOTONIC by construction -- growth is causal, so layers 0..n-1 behave
                  identically whether layer n is optical or perfect, and adding an
                  optical layer can only add an opportunity to crash. The cliff is
                  therefore UNAMBIGUOUS there.
        SEEL(n)   NOT monotonic: POEM re-anchors and CORRECTS the upstream error
                  (protection x34.8, §24-17), so one more optical layer can LOWER the
                  error. The LOCAL RISES designate the layers where optics does harm.
    """
    from certus.core.certus_strat_ranking import STRATEGY_ID_RATE_BASE
    sweep = sorted({int(x) for x in (params.get("optical_prefix_sweep") or [])})
    if not sweep:
        return []
    # ⚠️ NOT ALL PARENTS ARE SWEPT. The curve is CONDITIONAL on the monitoring plan, so it
    # only makes sense on a given plan -- and the only defensible one on r75x2 is LAYER-BY-
    # LAYER monitoring: measured on 2026-08-19, the 224 block strategies ALL crash at 100 %,
    # and the only survivor is the 75-block one. Sweeping 74 values of n over 110 parents
    # would moreover return 8 000 strategies for nothing.
    # 🔴 `n_blocks` IS OFTEN MISSING FROM THE STRATEGY DICTIONARY, and reading it with a
    # default of 0 made the test fail for ALL strategies -- hence zero prefixes, silently.
    # 📏 It cost 100 minutes of computation on 2026-08-19: the probe ran, returned 682
    # strategies, and an EMPTY curve. The proof was in plain sight -- `probe_blocs_vs_plantage.py`
    # reads `st.get("n_blocks", len(blocks))`, which says exactly that the key is often missing.
    #
    # ⚠️ AND MY UNIT TEST SET THE KEY BY HAND (`par_couche["n_blocks"] = 48`), so it validated
    # my hypothesis instead of the data. A test written from the same belief as the code
    # tests nothing. It now uses a strategy dictionary as it actually arrives.
    def _n_blocs(s: dict[str, Any]) -> int:
        n = s.get("n_blocks")
        return int(n) if n is not None else len(s.get("blocks") or [])

    meres = [s for s in strategies if _n_blocs(s) >= num_layers]
    if not meres:
        logger.warning(
            "[PREFIX] no strategy monitors layer by layer: the optical prefix sweep is "
            "NOT APPLICABLE to this population, it is skipped."
        )
        return []
    out: list[dict[str, Any]] = []
    next_id = STRATEGY_ID_RATE_BASE
    for strat in meres:
        for n_opt in sweep:
            if not (RATE_MIN_LAYER <= n_opt <= num_layers):
                continue
            tronques = []
            for blk in strat.get("blocks") or []:
                d, f = int(blk.get("start", 0)), int(blk.get("end", 0))
                if d >= n_opt:
                    continue
                tronques.append({**blk, "start": d, "end": min(f, n_opt)})
            v = dict(strat)
            v["blocks"] = tronques
            v["n_blocks"] = len(tronques)
            # 🔴 No Rate layer: layers >= n_opt are PERFECT, not Rate.
            # Confusing the two would measure the cost of Rate instead of isolating it.
            v["rate_layers"] = []
            v["strategy_id"] = _variant_id(strat.get("strategy_id"), next_id)
            v["origin"] = f"OPT_PREFIX{n_opt}(from {strat.get('strategy_id', '?')})"
            next_id += 1
            out.append(v)
    logger.info(
        f"[PREFIX] {len(out)} optical prefixes injected on {len(meres)} layer-by-layer "
        f"strategy(ies), n from {min(sweep)} to {max(sweep)}."
    )
    return out


def _expand_with_rate_variants(
    strategies: list[dict[str, Any]],
    params: dict[str, Any],
    num_layers: int,
    logger: logging.Logger,
    p_thick_nominal: Any = None,
    nominal_matrix_cache: Any = None,
    all_wls: Any = None,
    clues_at_wl: Any = None,
) -> list[dict[str, Any]]:
    """Add Rate variants of each strategy, so the ranking can compare them side by side.

    👤 *"The user must be able, in the final table, to allow or refuse the rate. Then the
    best strategies appear."* So Rate is not a hidden fallback: it produces ADDITIONAL
    candidates that stand or fall on the same statistics as everything else.

    🔴 ON BY DEFAULT since 2026-08-12 — 👤 *"add that rate is always allowed, it is the
    general case"*. This BREAKS C1 deliberately, and for the same reason the slit bias
    does: the machine offers Rate, so a default that hides it describes an instrument that
    does not exist. The historical path remains reachable with `allow_rate: false`, and
    any measurement made before this date was taken without Rate variants.

    ⚠️ ONE Rate layer per variant BY DEFAULT, deliberately. Two Rate layers interact -- the
    second inherits an estimate the first already froze -- and 12.3's lesson is that two
    things changed at once cannot be attributed. Combinations come after single layers are
    understood, not before.

    🔑 SINCE 2026-08-18 THAT DEFAULT IS LIFTABLE, and the reason is that the objection above
    is about ATTRIBUTION, not about physics. 👤: *"I remain convinced that rate is
    under-used"*, and the question asked is one of EXISTENCE -- is a much lower SEEL hiding
    behind a strategy with several Rate layers? Attribution is not required to answer it.

        rate_max_layers_per_variant     default 1  -- historical path, bit for bit
        rate_max_variants_per_strategy  default 40 -- RATE_MAX_VARIANTS_PER_STRATEGY

    At `rate_max_layers_per_variant = 1` this function walks exactly the same singletons, in
    the same order, with the same ids and the same `origin` strings as before.

    🔴 AND THE FULL COMBINATION IS ALWAYS APPENDED when the multi-layer path is active, cap or
    no cap. It is the cheapest probe of "what if we rate every boundary we may", and it costs
    one variant per strategy.

    ⚠️ SO THE CAP IS EXCEEDED BY EXACTLY ONE on the multi-layer path -- measured 2026-08-19:
    cap 12 gives 13, cap 24 gives 25, cap 64 gives 65. Deliberate, bounded, and stated here
    rather than left to be discovered while reading a strategy count that does not add up.

    🔑 `rate_by_swing`, added 2026-08-19, default `False`: places candidates by NEED (growth-
    time swing below `dynamics_threshold`) in addition to by COST (block boundary), instead
    of by cost alone. docs/archives/CHANTIER_RATE.md contradiction C. Requires
    `p_thick_nominal` / `nominal_matrix_cache` / `all_wls` / `clues_at_wl`, threaded in by
    `_prepare_robustness_inputs` from `opti_results` -- nothing new computed, only reaches a
    function that did not have them before.
    """
    from certus.core.certus_strat_ranking import STRATEGY_ID_RATE_BASE
    # 🔴 THE OPTICAL PREFIX SWEEP IS HOISTED ABOVE THE `allow_rate` GUARD, AND THAT IS THE
    # WHOLE POINT. It is NOT a Rate feature: it measures the cost of OPTICAL monitoring alone,
    # leaving the tail at PERFECT thickness. The probe therefore needs `allow_rate = False` --
    # otherwise Rate variants would mix into the population and both costs would be measured
    # at once. Placed under the guard, the injection returned ZERO variants silently: the
    # probe would have run for two hours for an empty curve.
    prefixes = _optical_prefix_variants(strategies, params, num_layers, logger)
    if not bool(params.get("allow_rate", True)):
        # ⚠️ Golden rule: without `optical_prefix_sweep`, `prefixes` is empty and the
        # `strategies` object ITSELF is returned, exactly as before. The default path does not move.
        return (list(strategies) + prefixes) if prefixes else strategies
    max_layers = max(1, int(params.get("rate_max_layers_per_variant", 1) or 1))
    cap = max(1, int(params.get("rate_max_variants_per_strategy",
                                RATE_MAX_VARIANTS_PER_STRATEGY)
                     or RATE_MAX_VARIANTS_PER_STRATEGY))
    # 🔴 CONTRADICTION A OF THE AUDIT, REPAIRED ON 2026-08-22. The cap quoted "the trial on
    # the 10 best" and in fact extended ALL strategies to 3 variants -- so neither the
    # instruction nor its opposite.
    #
    # 📏 Measured cost of that compromise: 12 923 Rate variants for 20 depositable ones. The
    # dossier had already costed the repair: "a cap of 40 on the 50 best would cost 2 000
    # variants instead of 12 923, and would explore each parent THIRTEEN TIMES more
    # deeply". Cheaper AND deeper -- that is what makes room for the swing criterion without
    # evicting the block boundaries.
    #
    # 🔒 `0` restores the former behaviour: all strategies are extended.
    top_n = int(params.get("rate_variant_top_n", RATE_VARIANT_TOP_N_DEFAUT) or 0)
    if top_n > 0 and len(strategies) > top_n:
        # The strategies already arrive sorted by increasing score from the screening.
        eligibles = set(id(x) for x in list(strategies)[:top_n])
        logger.info(
            f"[RATE] expansion limited to the {top_n} best of {len(strategies)} "
            f"(cap {cap} per strategy)."
        )
    else:
        eligibles = None
    # 🔴 `rate_by_swing`, added 2026-08-19 -- INACTIVE by default, golden rule: at
    # `False` `swing_ctx` stays `None` and `_rate_candidate_layers` runs its historical
    # boundary-only path, bit for bit. docs/archives/CHANTIER_RATE.md action 1.
    #
    # Placing the Rate where it is NEEDED (poor growth-time swing) rather than only where
    # it is CHEAPEST (a block boundary) -- contradiction C of the audit. Requires the
    # arrays Phase A already computed, threaded in by `_prepare_robustness_inputs`.
    # 🟢 ARMED BY DEFAULT SINCE 2026-08-22, at the request of 👤: "I am trying to make a
    # finished version that is not afraid of introducing rate and its subtleties".
    #
    # 🔑 WHAT MAKES THIS DEFAULT SAFE: a Rate variant enters as a COST, never as a
    # CUT-OFF (§22, §24-28). It is ADDED to a ranking that already contains the pure-optical
    # strategies; it therefore cannot degrade the final choice. The only channel through
    # which it could is the SHARED CAP -- and that is why contradiction A is repaired in the
    # same commit: without it, the "need" candidates would evict the "cost" candidates.
    #
    # 🔑 AND THIS REPAIRS CONTRADICTION B AS A SIDE EFFECT: the boundary criterion is
    # guarded by `RATE_MIN_LAYERS_PER_BLOCK`, the swing criterion IS NOT. A strategy that
    # monitors layer by layer -- the regime §24-40 measures as WINNING on 2 seeds out of
    # 5 -- therefore finally receives Rate candidates.
    swing_ctx: _RateSwingContext | None = None
    if bool(params.get("rate_by_swing", True)):
        # 🔴 `clues_at_wl` IS NOT ALWAYS A DICTIONARY, and a full run died of that
        # assumption on 2026-08-19. In the pipeline it arrives as a shared-memory object
        # (`SharedIndicesWorker`): `calculate_dynamics_ULTIMATE` calls `.items()` on it, raises
        # an `AttributeError` drowned in 3900 log lines, and the run ends on a "No strategies
        # found" that does not say why.
        #
        # 🔑 Yet the same file showed the remedy six hundred lines higher:
        # `_prepare_robustness_nominal_optics` wraps the same value in `_IdxWrapper` instead of
        # treating it as a dict. A REAL mapping is therefore required here, and otherwise the
        # code falls back NOISILY on the block boundaries -- an inert criterion must report
        # itself, never return a plausible result.
        _pret = (p_thick_nominal is not None and nominal_matrix_cache is not None
                 and all_wls is not None and clues_at_wl is not None
                 and hasattr(all_wls, "astype"))
        if _pret:
            threshold = float(params.get("dynamics_threshold", RATE_SWING_MIN_DEFAULT))
            swing_ctx = _RateSwingContext(p_thick_nominal, clues_at_wl,
                                          nominal_matrix_cache, all_wls, threshold)
            # 🔑 SELF-TEST BEFORE THE LOOP: a single evaluation, on the first layer of the
            # first strategy. If the wiring is broken, it is known within a second and SAID,
            # instead of killing a 25-minute run halfway -- which happened three times on
            # 2026-08-19, for three different causes.
            _wl0 = next((_wl_de_la_couche(s, 0) for s in strategies
                         if _wl_de_la_couche(s, 0) is not None), None)
            if _wl0 is None or swing_ctx.n_absents or swing_ctx.swing_at(0, _wl0) == float("inf"):
                logger.warning(
                    "[RATE] rate_by_swing DISABLED: the swing evaluation self-test "
                    "failed (probe wavelength %s, %d missed accesses). The criterion will "
                    "fabricate no Rate layer.", _wl0, swing_ctx.n_absents,
                )
                swing_ctx = None
        else:
            logger.warning(
                "[RATE] rate_by_swing=true INACTIVE: nominal arrays missing, or "
                "`clues_at_wl` (%s) / `all_wls` (%s) are not of the expected type. Falling "
                "back on block boundaries only.",
                type(clues_at_wl).__name__, type(all_wls).__name__,
            )

    # 🔑 TAIL SWEEP -- 👤 2026-08-19: "before layer i, the most perfect filter possible
    # fully optical, then layers i+1 to N in rate". INACTIVE by default (empty list), so the
    # golden rule holds.
    #
    # 🔴 THIS SHAPE IS OUT OF THE GENERATOR'S REACH. The dossier usually rules out forcing
    # mechanisms -- "useless, a run already generates hundreds of strategies" -- but the
    # search places 1 to 3 Rate layers at BLOCK BOUNDARIES, never 40 in the tail. Only
    # injection can test the shape, and it is the only measured case where it is justified.
    #
    # 📏 WHAT FIXES THE CUT RANGE, measured on 2026-08-19 over the 10 runs of x2: the
    # dominant critical layer is 32 at 2 nm and 35 everywhere else, and 59 to 74 % of the
    # critical layers are BEFORE layer 40. A tail starting at 40 would therefore leave the
    # dominant crash in the optical part -- hence a sweep starting at 28.
    #
    # 📏 AND THE CAUSE IS UNEQUIVOCAL: 100 % of the crashes of layers 32/35/39 are
    # "stop level out of reach", zero "turning-point count". It is the ACCUMULATED DRIFT,
    # not the layer's own signal. Crossing the zone in open loop avoids looking there for a
    # level that has become unreachable -- that is the mechanism tested here.
    tail_cuts = params.get("rate_tail_sweep") or []
    # 🔑 SURGICAL RATE -- 👤 2026-08-19: "if at j+1 we go back to optical and there are
    # several extrema, POEM is effective, isn't it?". VERIFIED in the kernel, and the answer
    # is yes: `n_hist = (i_layer - block_start) * NPTS_PREV` only serves to BORROW extrema
    # from the previous layers of the block. A layer that has its own two turning points
    # does not need them -- and POEM reads its anchors on the REAL signal, so it compensates
    # the upstream drift by change of variable ("we thus stop exactly at the desired
    # thickness").
    #
    # 🔴 CONSEQUENCE, AND IT INVALIDATES THE MONOLITHIC TAIL AS THE ONLY SHAPE. If optics
    # fully restarts after a Rate layer, nothing forces 23 layers into open loop: it is
    # enough to CROSS the ones that fail. The cost of Rate growing with the number of layers
    # involved (+1 % at 35 layers, +22 % at 75), 3 layers should cost far less than 23.
    #
    # 📏 The targets are not chosen: they are MEASURED. On x2 at 2 nm, three layers hold
    # 73 % of the critical layers -- 32 (47 %), 39 (16 %), 35 (10 %) -- and 100 % of these
    # failures are "stop level out of reach", hence drift, not signal.
    #
    # ⚠️ AND IT IS ITERATIVE BY NATURE. Crossing layer 32 will move the breaking point
    # elsewhere; the critical layers will have to be remeasured and the process repeated.
    # That is the recurrence 👤 described from the start.
    layer_sets = params.get("rate_layer_sets") or []
    keep_optical = int(params.get("rate_tail_keep_optical", 0) or 0)

    # 🔑 OPTICAL PREFIX SWEEP -- 👤 2026-08-19:
    #
    #   "20 optical layers plus the rest with PERFECT thicknesses, we compute SEEL20;
    #     then 21; ... up to SEEL75. We look at the curve SEEL = f(n) and deduce from it
    #     where the optical monitoring becomes a problem."
    #   "careful, the curve is not necessarily monotonic, it must be plotted ENTIRELY
    #     to decide when rate is necessary."
    #
    # 🔑 WHAT MAKES THIS MEASUREMENT DIFFERENT FROM EVERYTHING ELSE: it is a DECOMPOSITION,
    # not a search. Each `n` is ONE measurement, never a maximum over candidates -- so no
    # winner's curse, the one that cost +12.9 % on 08-15 and that COMPOUNDS in a greedy
    # search.
    #
    # 🟢 AND NO NEW KERNEL CODE IS NEEDED. `_build_layer_wavelengths_from_strategy`
    # initialises `layer_wavelengths` to ZERO and fills only the layers covered by a
    # block; the kernel then takes the `if wl < 0.1` branch (certus_strat_growth.py) and
    # returns EXACTLY the nominal thickness, margins at 1e18 so a crash is impossible.
    # Truncating the blocks to `n` is enough: layers >= n are perfect, through a path
    # already written and tested.
    #
    # ⚠️ "PERFECT" IS NOT "RATE", and the two must not be confused. A Rate layer inherits
    # the factor A; a perfect layer inherits nothing. SEEL(n) is therefore a LOWER BOUND,
    # not the prediction of the real strategy. That is precisely the point: the difference
    # between the two ISOLATES the proper cost of the Rate tail.
    #
    # 🔑 The two curves share the work, and this is structural:
    #     crash(n)  is MONOTONIC by construction -- adding an optical layer can only add
    #               an opportunity to crash. The cliff is therefore unambiguous there.
    #     SEEL(n)   is NOT monotonic, because POEM re-anchors and CORRECTS the upstream
    #               error (protection x34.8 measured, §24-17). One more optical layer can
    #               LOWER the error. The local RISES designate the layers where optical
    #               monitoring does harm.
    # 🔴 The optical prefixes have already consumed identifiers starting from
    # STRATEGY_ID_RATE_BASE: without this offset, a Rate variant would carry the same id as a
    # prefix and the child/parent pairing would become impossible to untangle.
    variants: list[dict[str, Any]] = list(prefixes)
    skipped = 0
    next_id = STRATEGY_ID_RATE_BASE + len(prefixes)
    _t0 = time.perf_counter()
    if layer_sets:
        for strat in strategies:
            for jeu in layer_sets:
                couches = sorted({int(x) for x in jeu if 0 <= int(x) < num_layers})
                if not couches:
                    continue
                v = dict(strat)
                v["blocks"] = list(strat.get("blocks") or [])
                v["rate_layers"] = couches
                v["strategy_id"] = _variant_id(strat.get("strategy_id"), next_id)
                v["origin"] = (f"RATE_SET{'_'.join(str(x) for x in couches)}"
                               f"(from {strat.get('strategy_id', '?')})")
                next_id += 1
                variants.append(v)
        logger.info(
            f"[RATE-SET] {len(variants)} surgical variants on {len(strategies)} "
            f"strategies, {len(layer_sets)} layer sets."
        )
    if tail_cuts:
        for strat in strategies:
            for cut in tail_cuts:
                c = int(cut)
                if not (0 < c < num_layers):
                    continue
                v = dict(strat)
                v["blocks"] = list(strat.get("blocks") or [])
                queue = list(range(c, num_layers))
                # 🔑 THE EXCEPTION RULE OF 👤: "except the layers [with a good signal] that stay
                # optical". It requires a DISCRIMINATING criterion -- 📏 the ">= 2 turning points"
                # proposed at first is met by 32 tail layers out of 35, it would have selected
                # nothing. The `keep` layers with the STRONGEST swing are therefore kept, which
                # selects by construction.
                if keep_optical and swing_ctx is not None:
                    note = []
                    for lay in queue:
                        wl = _wl_de_la_couche(strat, lay)
                        note.append((swing_ctx.swing_at(lay, wl) if wl else -1.0, lay))
                    note.sort(reverse=True)
                    gardees = {lay for _, lay in note[:keep_optical]}
                    queue = [lay for lay in queue if lay not in gardees]
                v["rate_layers"] = queue
                v["strategy_id"] = _variant_id(strat.get("strategy_id"), next_id)
                v["origin"] = (f"RATE_TAIL{c}"
                               + (f"K{keep_optical}" if keep_optical else "")
                               + f"(from {strat.get('strategy_id', '?')})")
                next_id += 1
                variants.append(v)
        logger.info(
            f"[RATE-TAIL] {len(variants)} tail variants injected on "
            f"{len(strategies)} strategies, cuts {sorted(int(c) for c in tail_cuts)}."
        )
    for strat in strategies:
        # 🔴 CONTRADICTION A: the best ones are extended DEEPLY, instead of extending
        # all of them FLATLY. `eligibles` is None when `rate_variant_top_n = 0`, and the
        # former path then comes back bit for bit.
        if eligibles is not None and id(strat) not in eligibles:
            continue
        # The historical path caps the CANDIDATES at 3; the multi-layer path needs them all
        # before it can combine them, and caps the resulting VARIANTS instead.
        cands = _rate_candidate_layers(strat, num_layers,
                                       cap=None if max_layers == 1 else 64,
                                       swing_ctx=swing_ctx)
        if not cands:
            skipped += 1
            continue
        if max_layers == 1:
            combos: list[tuple[int, ...]] = [(x,) for x in cands[:cap]]
        else:
            combos = []
            for taille in range(1, min(max_layers, len(cands)) + 1):
                combos.extend(itertools.combinations(cands, taille))
            combos = combos[:cap]
            entier = tuple(cands)
            if len(cands) > 1 and entier not in combos:
                combos.append(entier)
        for combo in combos:
            v = dict(strat)
            v["blocks"] = list(strat.get("blocks") or [])
            v["rate_layers"] = list(combo)
            v["strategy_id"] = _variant_id(strat.get("strategy_id"), next_id)
            etiquette = "_".join(str(x) for x in combo)
            v["origin"] = f"RATE_L{etiquette}(from {strat.get('strategy_id', '?')})"
            next_id += 1
            variants.append(v)
    if variants or skipped:
        _dt = time.perf_counter() - _t0
        _extra = ""
        if swing_ctx is not None:
            _extra = (f" [SWING] seuil {swing_ctx.threshold:g}, {swing_ctx.n_calls} "
                     f"evaluations TMM a lambda fixe, {_dt:.1f} s au total pour cette "
                     f"expansion.")
        logger.info(
            f"[RATE] {len(variants)} variants on {len(strategies)} strategies, "
            f"{cap} at most each, DEEPEST boundaries first. "
            f"{skipped} strategy(ies) skipped: no block boundary and no low-swing "
            f"layer.{_extra}"
        )
    return strategies + variants


def _variant_id(parent_id: object, serial: int) -> object:
    """Identifier of a generated variant, IN THE PARENT'S TYPE.

    🔴 Not cosmetic. The ranking breaks ties by sorting on `strategy_id`, and
    `sorted()` RAISES on a list mixing `int` and `str`. Handing an int id to the variant
    of a string-id parent therefore turns a deterministic tie-break into a TypeError --
    latent for as long as every design happens to use integer ids, and fatal the day one
    does not. Found 2026-08-12 when Rate and the slit search became active by default and
    started generating variants on every run.
    """
    return f"{parent_id}#{serial}" if isinstance(parent_id, str) else serial
