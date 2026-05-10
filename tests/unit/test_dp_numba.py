import time
import numpy as np
from numba import njit
import heapq
import random


# ==============================================================================
# ORIGINAL PYTHON DP
# ==============================================================================
def _find_k_best_groupings_dp_sequential(
    cost_map: dict[int, dict[float, float]],
    n_blocks: int,
    num_layers: int,
    top_k: int = 100,
    timeout: float = 120.0,
    start_time: float = None,
    force_monolayer: bool = False,
    nucleation_wl: float = None,
    nucleation_size: int = 0,
):
    if start_time is None:
        start_time = time.time()

    if nucleation_wl:
        if 0 in cost_map:
            list(cost_map[0].keys())

    block_costs = {}
    check_counter = 0
    layer_data = {}
    for layer_idx, layer_dict in cost_map.items():
        if not layer_dict:
            continue
        wls = list(layer_dict.keys())
        costs = [layer_dict[w] for w in wls]
        index = {w: pos for pos, w in enumerate(wls)}
        layer_data[layer_idx] = (wls, costs, index)

    count_valid_blocks = 0
    for i in range(num_layers):
        if i not in layer_data:
            continue
        for j in range(i + 1, num_layers + 1):
            check_counter += 1
            if (time.time() - start_time) > timeout:
                return []
            if force_monolayer and i == 0 and j == 1:
                continue

            layers_in_block = []
            for k in range(i, j):
                if k in layer_data:
                    layers_in_block.append(k)
            if len(layers_in_block) != (j - i):
                continue

            layers_in_block_sorted = sorted(
                layers_in_block, key=lambda l: len(layer_data[l][0])
            )
            base_layer = layers_in_block_sorted[0]
            base_wls, base_costs, base_index = layer_data[base_layer]

            valid_candidates_for_block = []
            for idx_base, wl in enumerate(base_wls):
                if nucleation_wl and i == 0 and j <= nucleation_size:
                    if abs(wl - nucleation_wl) > 1.0:
                        continue
                current_block_cost = base_costs[idx_base]
                is_valid = True
                for other_layer in layers_in_block_sorted[1:]:
                    _, costs_other, index_other = layer_data[other_layer]
                    pos = index_other.get(wl, -1)
                    if pos == -1:
                        is_valid = False
                        break
                    current_block_cost += costs_other[pos]
                if is_valid:
                    valid_candidates_for_block.append((current_block_cost, wl))

            smart_nucl_active = nucleation_wl is not None
            if (
                force_monolayer
                and i == 0
                and j == 2
                and not valid_candidates_for_block
                and not smart_nucl_active
            ):
                l2_wls, l2_costs, _ = layer_data[1]
                l1_vals = layer_data[0][1]
                if len(l1_vals) > 0:
                    dynamic_penalty = (sum(l1_vals) / len(l1_vals)) * 2.0
                else:
                    dynamic_penalty = 1.0
                best_clues = sorted(range(len(l2_costs)), key=lambda k: l2_costs[k])[
                    :10
                ]
                for idx in best_clues:
                    wl = l2_wls[idx]
                    cost_l2 = l2_costs[idx]
                    valid_candidates_for_block.append((cost_l2 + dynamic_penalty, wl))

            if valid_candidates_for_block:
                valid_candidates_for_block.sort(key=lambda x: x[0])
                block_costs[(i, j)] = valid_candidates_for_block[:top_k]
                count_valid_blocks += 1

    if count_valid_blocks == 0:
        return []

    dp = [[[] for _ in range(num_layers + 1)] for _ in range(n_blocks + 1)]
    dp[0][0] = [(0.0, [])]
    check_counter = 0

    for k in range(1, n_blocks + 1):
        for i in range(k, num_layers + 1):
            check_counter += 1
            if check_counter % 200 == 0:
                if (time.time() - start_time) > timeout:
                    return []
            candidates_heap = []
            for j in range(k - 1, i):
                if not dp[k - 1][j]:
                    continue
                if (j, i) not in block_costs:
                    continue
                potential_blocks = block_costs[(j, i)]
                previous_solutions = dp[k - 1][j]
                for prev_cost, prev_path in previous_solutions:
                    for blk_cost, wl in potential_blocks[:10]:
                        total_cost = prev_cost + blk_cost
                        new_path = prev_path + [(j, i, wl)]
                        heapq.heappush(candidates_heap, (total_cost, new_path))
            if candidates_heap:
                dp[k][i] = heapq.nsmallest(
                    top_k * 2, candidates_heap, key=lambda x: x[0]
                )

    final_candidates = dp[n_blocks][num_layers]
    if not final_candidates:
        return []

    solutions = []
    for total_cost, blocks_info in final_candidates:
        assignments = {}
        for start, end, wl in blocks_info:
            for l in range(start, end):
                assignments[l] = wl
        solutions.append(
            {
                "cost": float(total_cost),
                "assignments": assignments,
                "blocks_info": blocks_info,
            }
        )
    return solutions


# ==============================================================================
# NUMBA DP
# ==============================================================================


@njit(cache=False, fastmath=True)
def _compute_valid_blocks_kernel(
    layer_wls: np.ndarray,  # (num_layers, max_W)
    layer_costs: np.ndarray,  # (num_layers, max_W)
    valid_mask: np.ndarray,  # (num_layers, max_W)
    num_layers: int,
    top_k: int,
    max_W: int,
):
    """
    Computes valid blocks and their costs.
    Returns block_costs matrix (num_layers, num_layers, top_k) -> cost values
    Returns block_wls matrix (num_layers, num_layers, top_k) -> wl values
    Returns block_counts (num_layers, num_layers) -> valid elements
    """
    block_costs = np.full(
        (num_layers + 1, num_layers + 1, top_k), np.inf, dtype=np.float64
    )
    block_wls = np.full((num_layers + 1, num_layers + 1, top_k), -1.0, dtype=np.float64)
    block_counts = np.zeros((num_layers + 1, num_layers + 1), dtype=np.int32)

    # Pre-compute unique wavelengths to allow fast O(1) intersection conceptually,
    # but since numpy is fast we can use a small boolean grid or just binary search...
    # Wavelengths might not be exactly integers, but they are often decimals.
    # To keep it completely generic with arrays:

    for i in range(num_layers):
        for j in range(i + 1, num_layers + 1):

            # Check if all layers i..j-1 have valid masks (meaning they are in layer_data)
            # Actually valid_mask indicates which clues are valid for a layer
            bl_ok = True
            for l in range(i, j):
                # if layer has no valid candidates, block is invalid
                has_any = False
                for w in range(max_W):
                    if valid_mask[l, w]:
                        has_any = True
                        break
                if not has_any:
                    bl_ok = False
                    break

            if not bl_ok:
                continue

            # Find base layer (smallest valid_mask count)
            min_count = 999999
            base_l = i
            for l in range(i, j):
                c = 0
                for w in range(max_W):
                    if valid_mask[l, w]:
                        c += 1
                if c < min_count:
                    min_count = c
                    base_l = l

            # Temporarily store all candidates
            temp_costs = np.zeros(max_W, dtype=np.float64)
            temp_wls = np.zeros(max_W, dtype=np.float64)
            temp_count = 0

            for base_w_idx in range(max_W):
                if not valid_mask[base_l, base_w_idx]:
                    continue

                wl = layer_wls[base_l, base_w_idx]
                total_cost = layer_costs[base_l, base_w_idx]

                is_valid = True
                for l in range(i, j):
                    if l == base_l:
                        continue

                    # Find wl in layer l
                    found = False
                    for w in range(max_W):
                        if valid_mask[l, w] and abs(layer_wls[l, w] - wl) < 1e-5:
                            total_cost += layer_costs[l, w]
                            found = True
                            break
                    if not found:
                        is_valid = False
                        break

                if is_valid:
                    temp_costs[temp_count] = total_cost
                    temp_wls[temp_count] = wl
                    temp_count += 1

            if temp_count > 0:
                # Sort temp arrays (Bubble sort is extremely fast for small arrays or we use an insertion sort)
                for x in range(temp_count):
                    for y in range(x + 1, temp_count):
                        if temp_costs[y] < temp_costs[x]:
                            tc = temp_costs[x]
                            temp_costs[x] = temp_costs[y]
                            temp_costs[y] = tc
                            tw = temp_wls[x]
                            temp_wls[x] = temp_wls[y]
                            temp_wls[y] = tw

                take = min(temp_count, top_k)
                for k in range(take):
                    block_costs[i, j, k] = temp_costs[k]
                    block_wls[i, j, k] = temp_wls[k]
                block_counts[i, j] = take

    return block_costs, block_wls, block_counts


@njit(cache=False, fastmath=True)
def _dp_kernel(
    block_costs: np.ndarray,
    block_wls: np.ndarray,
    block_counts: np.ndarray,
    n_blocks: int,
    num_layers: int,
    top_k: int,
):
    # Instead of allocating (top_k*2 + top_k*10), we allocate precisely what is needed locally
    # dp_costs: (n_blocks+1, num_layers+1, 2*top_k)
    dp_costs = np.full(
        (n_blocks + 1, num_layers + 1, top_k * 2), np.inf, dtype=np.float64
    )
    # dp_paths_start: (n_blocks+1, num_layers+1, 2*top_k, n_blocks)
    dp_paths_start = np.full(
        (n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32
    )
    dp_paths_end = np.full(
        (n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32
    )
    dp_paths_wl = np.full(
        (n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1.0, dtype=np.float64
    )

    dp_counts = np.zeros((n_blocks + 1, num_layers + 1), dtype=np.int32)

    dp_costs[0, 0, 0] = 0.0
    dp_counts[0, 0] = 1

    # buffer to sort candidates locally
    # We never generate more than (dp_counts * min(10, bl_count))
    # For a given cell (k, i), we process at most (i-k+1) previous j's.
    max_cands = top_k * 2
    temp_size = max_cands + 500  # Safe bounding
    temp_costs = np.zeros(temp_size, dtype=np.float64)
    temp_paths_start = np.full((temp_size, n_blocks), -1, dtype=np.int32)
    temp_paths_end = np.full((temp_size, n_blocks), -1, dtype=np.int32)
    temp_paths_wl = np.full((temp_size, n_blocks), -1.0, dtype=np.float64)

    for k in range(1, n_blocks + 1):
        for i in range(k, num_layers + 1):

            c_count = 0

            for j in range(k - 1, i):
                prev_count = dp_counts[k - 1, j]
                if prev_count == 0:
                    continue

                bl_count = block_counts[j, i]
                if bl_count == 0:
                    continue

                for p in range(prev_count):
                    prev_cost = dp_costs[k - 1, j, p]

                    for b in range(min(10, bl_count)):
                        total_cost = prev_cost + block_costs[j, i, b]
                        wl = block_wls[j, i, b]

                        # Bounds guard: Break if temp arrays are saturated
                        if c_count >= temp_size:
                            break

                        temp_costs[c_count] = total_cost

                        # Copy old path
                        for old_h in range(k - 1):
                            temp_paths_start[c_count, old_h] = dp_paths_start[
                                k - 1, j, p, old_h
                            ]
                            temp_paths_end[c_count, old_h] = dp_paths_end[
                                k - 1, j, p, old_h
                            ]
                            temp_paths_wl[c_count, old_h] = dp_paths_wl[
                                k - 1, j, p, old_h
                            ]

                        # Append new step
                        temp_paths_start[c_count, k - 1] = j
                        temp_paths_end[c_count, k - 1] = i
                        temp_paths_wl[c_count, k - 1] = wl

                        c_count += 1

            if c_count > 0:
                # Sort and keep top_k*2
                # Standard insertion sort
                for x in range(1, c_count):
                    key_cost = temp_costs[x]

                    key_st = np.empty(n_blocks, dtype=np.int32)
                    key_en = np.empty(n_blocks, dtype=np.int32)
                    key_wl = np.empty(n_blocks, dtype=np.float64)

                    for _b in range(n_blocks):
                        key_st[_b] = temp_paths_start[x, _b]
                        key_en[_b] = temp_paths_end[x, _b]
                        key_wl[_b] = temp_paths_wl[x, _b]

                    y = x - 1
                    while y >= 0 and temp_costs[y] > key_cost:
                        temp_costs[y + 1] = temp_costs[y]
                        # copy array manually because njit
                        for _b in range(n_blocks):
                            temp_paths_start[y + 1, _b] = temp_paths_start[y, _b]
                            temp_paths_end[y + 1, _b] = temp_paths_end[y, _b]
                            temp_paths_wl[y + 1, _b] = temp_paths_wl[y, _b]
                        y -= 1
                    temp_costs[y + 1] = key_cost
                    for _b in range(n_blocks):
                        temp_paths_start[y + 1, _b] = key_st[_b]
                        temp_paths_end[y + 1, _b] = key_en[_b]
                        temp_paths_wl[y + 1, _b] = key_wl[_b]

                take = min(c_count, max_cands)
                for t in range(take):
                    dp_costs[k, i, t] = temp_costs[t]
                    for _b in range(n_blocks):
                        dp_paths_start[k, i, t, _b] = temp_paths_start[t, _b]
                        dp_paths_end[k, i, t, _b] = temp_paths_end[t, _b]
                        dp_paths_wl[k, i, t, _b] = temp_paths_wl[t, _b]
                dp_counts[k, i] = take

    return dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts


def _find_k_best_groupings_dp_numba(
    cost_map: dict[int, dict[float, float]],
    n_blocks: int,
    num_layers: int,
    top_k: int = 100,
    force_monolayer: bool = False,
    nucleation_wl: float = None,
    nucleation_size: int = 0,
):
    # 1. Prepare dense matrices
    max_W = max((len(v) for v in cost_map.values() if v), default=0)
    layer_wls = np.full((num_layers, max_W), -1.0, dtype=np.float64)
    layer_costs = np.full((num_layers, max_W), np.inf, dtype=np.float64)
    valid_mask = np.zeros((num_layers, max_W), dtype=np.bool_)

    for layer_idx, layer_dict in cost_map.items():
        if layer_idx >= num_layers or not layer_dict:
            continue
        wls = list(layer_dict.keys())
        for w_idx, w in enumerate(wls):
            layer_wls[layer_idx, w_idx] = float(w)
            layer_costs[layer_idx, w_idx] = float(layer_dict[w])
            valid_mask[layer_idx, w_idx] = True

    # Compile execution
    block_costs, block_wls, block_counts = _compute_valid_blocks_kernel(
        layer_wls, layer_costs, valid_mask, num_layers, top_k, max_W
    )

    # Python-side force_monolayer and nucleation constraint injection
    if nucleation_wl and num_layers >= nucleation_size:
        # Erase invalid nucleation blocks
        for j in range(1, nucleation_size + 1):
            if block_counts[0, j] > 0:
                filtered_c = 0
                for b in range(block_counts[0, j]):
                    if abs(block_wls[0, j, b] - nucleation_wl) <= 1.0:
                        block_costs[0, j, filtered_c] = block_costs[0, j, b]
                        block_wls[0, j, filtered_c] = block_wls[0, j, b]
                        filtered_c += 1
                block_counts[0, j] = filtered_c

    if force_monolayer and block_counts[0, 1] > 0:
        # Disable 0..1 block if forced monolayer? Wait, original code says:
        # if force_monolayer and i == 0 and j == 1: continue (skip computing it)
        block_counts[0, 1] = 0

        # force_monolayer rule for i=0, j=2
        smart_nucl_active = nucleation_wl is not None
        if not smart_nucl_active and block_counts[0, 2] == 0:
            # We inject a simulated block
            l2_mask = valid_mask[1]
            l1_mask = valid_mask[0]

            l1_costs = layer_costs[0][l1_mask]
            dynamic_penalty = np.mean(l1_costs) * 2.0 if len(l1_costs) > 0 else 1.0

            l2_valid_idx = np.where(l2_mask)[0]
            if len(l2_valid_idx) > 0:
                l2_costs = layer_costs[1][l2_valid_idx]
                best_clues = np.argsort(l2_costs)[:10]

                cpt = 0
                for idx in best_clues:
                    wl = layer_wls[1, l2_valid_idx[idx]]
                    cost_l2 = l2_costs[idx]

                    block_costs[0, 2, cpt] = cost_l2 + dynamic_penalty
                    block_wls[0, 2, cpt] = wl
                    cpt += 1
                block_counts[0, 2] = cpt
                # Sort them
                sort_idx = np.argsort(block_costs[0, 2, :cpt])
                block_costs[0, 2, :cpt] = block_costs[0, 2, :cpt][sort_idx]
                block_wls[0, 2, :cpt] = block_wls[0, 2, :cpt][sort_idx]

    dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts = _dp_kernel(
        block_costs, block_wls, block_counts, n_blocks, num_layers, top_k
    )

    final_count = dp_counts[n_blocks, num_layers]
    if final_count == 0:
        return []

    solutions = []
    for t in range(final_count):
        total_cost = dp_costs[n_blocks, num_layers, t]
        blocks_info = []
        for b in range(n_blocks):
            st = dp_paths_start[n_blocks, num_layers, t, b]
            en = dp_paths_end[n_blocks, num_layers, t, b]
            wl = dp_paths_wl[n_blocks, num_layers, t, b]
            if st != -1:
                blocks_info.append((int(st), int(en), float(wl)))

        assignments = {}
        for start, end, wl in blocks_info:
            for l in range(start, end):
                assignments[l] = wl
        solutions.append(
            {
                "cost": float(total_cost),
                "assignments": assignments,
                "blocks_info": blocks_info,
            }
        )

    return solutions


# ==============================================================================
# TEST & BENCHMARK
# ==============================================================================
if __name__ == "__main__":
    print("Generating Mock Data (Num Layers = 20, Max candidates = 800)...")
    num_layers = 20
    n_blocks = 4

    # 800 wavelengths per layer, mostly overlapping
    base_wls = np.linspace(400, 800, 800)

    cost_map = {}
    for i in range(num_layers):
        # 90% overlap
        wls = [w for w in base_wls if random.random() < 0.9]
        cost_map[i] = {w: random.uniform(0.1, 5.0) for w in wls}

    print(f"Generated data for {num_layers} layers.")

    # Warmup Numba
    print("Warming up Numba JIT...")
    _ = _find_k_best_groupings_dp_numba(
        {0: {400: 1.0, 500: 2.0}, 1: {400: 2.0, 500: 1.0}}, 1, 2
    )

    # Profile Original
    print("Running Original DP...")
    t0 = time.time()
    res_orig = _find_k_best_groupings_dp_sequential(cost_map, n_blocks, num_layers)
    t1 = time.time()

    # Profile Numba
    print("Running Numba DP...")
    t2 = time.time()
    res_numba = _find_k_best_groupings_dp_numba(cost_map, n_blocks, num_layers)
    t3 = time.time()

    print(f"Original: {t1 - t0:.4f}s")
    print(f"Numba   : {t3 - t2:.4f}s")
    print(f"Speedup : {(t1 - t0) / (t3 - t2):.2f}x")

    print(f"Results Original: {len(res_orig)} solutions")
    print(f"Results Numba   : {len(res_numba)} solutions")

    if len(res_orig) > 0 and len(res_numba) > 0:
        print("Best Original Cost:", res_orig[0]["cost"], res_orig[0]["blocks_info"])
        print("Best Numba Cost   :", res_numba[0]["cost"], res_numba[0]["blocks_info"])
