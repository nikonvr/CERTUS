import numpy as np
from numba import njit, prange
import math
from certus.core.certus_core import TWO_PI
from certus.physics.certus_opt_kernels import compute_RT_from_matrix
from certus.physics.certus_tmm_core import compute_TMM_single_point_k0_exact

NON_MONOTONIC_MODE_ATTENUATE = 0
NON_MONOTONIC_MODE_REJECT = 1
K_MAX_LAYER_BACKSIDE: float = 0.001
K_MAX_SUBSTRATE_BACKSIDE: float = 0.00001
from .certus_strat_math import check_extrema_proximity, _calc_T_from_matrix, _calc_T_added_layer


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _compute_valid_blocks_kernel(
    layer_wls: np.ndarray,
    layer_costs: np.ndarray,
    valid_mask: np.ndarray,
    num_layers: int,
    top_k: int,
    max_W: int,
    min_wl_sep: float = 0.0,
):
    """Couts des blocs candidats, avec SEPARATION SPECTRALE MINIMALE.

    `min_wl_sep` <= 0 restitue le comportement historique : les `top_k` longueurs d'onde
    de cout le plus bas, sans autre critere.

    🔴 POURQUOI CE PARAMETRE EXISTE. Mesure du 2026-08-05, pas de balayage porte de 5 a
    2 nm sur la demande du physicien (`scripts/probe_block_wls.py`) :

        pas de balayage        5 nm            2 nm
        etendue des 10 lambda  95 nm mediane   36 nm mediane, 18 nm minimum
        regions a 20 nm        4 (min 3)       2 (min 1)
        candidats disponibles  18 par bloc     40 par bloc
        rejetes par le cap     8 sur 18        30 sur 40

    A 2 nm, 14 % des blocs recevaient dix longueurs d'onde formant UNE SEULE region, par
    exemple [456, 458, 460, 462, 464, 466, 468, 470, 472, 474] : dix points de grille
    CONSECUTIFS. Ce ne sont pas dix strategies, c'est une region echantillonnee a chaque
    pas — et pendant ce temps trente candidats couvrant d'autres regions etaient jetes.
    Le cout etant une fonction lisse de lambda, affiner la grille resserre mecaniquement
    les `top_k` moins chers autour du meme minimum local.

    ⚠️ Deux echelles a ne pas confondre. Le pas de BALAYAGE (2 nm) est la resolution avec
    laquelle on cherche le meilleur point A L'INTERIEUR d'une region ; il doit rester fin.
    La separation minimale est l'echelle a laquelle deux longueurs d'onde constituent des
    choix de monitoring DIFFERENTS ; elle se lit sur la variation du gain de compensation
    (facteur 17 entre 475 et 550 nm) et sur l'espacement des minima locaux du cout, soit
    quelques dizaines de nanometres.

    L'algorithme ne perd AUCUNE arete : une premiere passe prend le moins cher de chaque
    region, une seconde complete avec les moins chers restants. On obtient donc autant de
    candidats qu'avant, mais aussi distincts que possible.
    """
    block_costs = np.full((num_layers + 1, num_layers + 1, top_k), np.inf, dtype=np.float64)
    block_wls = np.full((num_layers + 1, num_layers + 1, top_k), -1.0, dtype=np.float64)
    block_counts = np.zeros((num_layers + 1, num_layers + 1), dtype=np.int32)
    taken = np.zeros(max_W, dtype=np.bool_)
    for i in range(num_layers):
        for j in range(i + 1, num_layers + 1):
            bl_ok = True
            for l in range(i, j):
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
            base_l = i
            min_count = 999999
            for l in range(i, j):
                c = 0
                for w in range(max_W):
                    if valid_mask[l, w]:
                        c += 1
                if c < min_count:
                    min_count = c
                    base_l = l
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
                    found = False
                    for w in range(max_W):
                        if valid_mask[l, w] and abs(layer_wls[l, w] - wl) < 1e-05:
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
                if min_wl_sep <= 0.0:
                    for k in range(take):
                        block_costs[i, j, k] = temp_costs[k]
                        block_wls[i, j, k] = temp_wls[k]
                    block_counts[i, j] = take
                else:
                    for x in range(temp_count):
                        taken[x] = False
                    n_sel = 0
                    # Passe 1 — le moins cher de chaque region. temp_* est trie par
                    # cout croissant, donc le tout premier retenu est bien l'optimum
                    # global du bloc : on ne sacrifie jamais le meilleur a la diversite.
                    for x in range(temp_count):
                        if n_sel >= take:
                            break
                        ok = True
                        for s in range(n_sel):
                            d = block_wls[i, j, s] - temp_wls[x]
                            if d < 0.0:
                                d = -d
                            if d < min_wl_sep:
                                ok = False
                                break
                        if ok:
                            block_costs[i, j, n_sel] = temp_costs[x]
                            block_wls[i, j, n_sel] = temp_wls[x]
                            taken[x] = True
                            n_sel += 1
                    # Passe 2 — completer avec les moins chers restants, pour ne perdre
                    # aucune arete quand la plage utile est trop etroite pour fournir
                    # `take` regions distinctes.
                    for x in range(temp_count):
                        if n_sel >= take:
                            break
                        if not taken[x]:
                            block_costs[i, j, n_sel] = temp_costs[x]
                            block_wls[i, j, n_sel] = temp_wls[x]
                            taken[x] = True
                            n_sel += 1
                    block_counts[i, j] = n_sel
    return (block_costs, block_wls, block_counts)


@njit(cache=True, fastmath=True, nogil=True, error_model="numpy")
def _dp_kernel(
    block_costs: np.ndarray, block_wls: np.ndarray, block_counts: np.ndarray, n_blocks: int, num_layers: int, top_k: int
):
    dp_costs = np.full((n_blocks + 1, num_layers + 1, top_k * 2), np.inf, dtype=np.float64)
    dp_paths_start = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)
    dp_paths_end = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1, dtype=np.int32)
    dp_paths_wl = np.full((n_blocks + 1, num_layers + 1, top_k * 2, n_blocks), -1.0, dtype=np.float64)
    dp_counts = np.zeros((n_blocks + 1, num_layers + 1), dtype=np.int32)
    dp_costs[0, 0, 0] = 0.0
    dp_counts[0, 0] = 1
    max_cands = top_k * 2
    temp_costs = np.zeros(max_cands, dtype=np.float64)
    temp_paths_start = np.full((max_cands, n_blocks), -1, dtype=np.int32)
    temp_paths_end = np.full((max_cands, n_blocks), -1, dtype=np.int32)
    temp_paths_wl = np.full((max_cands, n_blocks), -1.0, dtype=np.float64)
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
                        if c_count == max_cands and total_cost >= temp_costs[max_cands - 1]:
                            continue
                        idx = c_count if c_count < max_cands else max_cands - 1
                        while idx > 0 and temp_costs[idx - 1] > total_cost:
                            if idx < max_cands:
                                temp_costs[idx] = temp_costs[idx - 1]
                                for _b in range(n_blocks):
                                    temp_paths_start[idx, _b] = temp_paths_start[idx - 1, _b]
                                    temp_paths_end[idx, _b] = temp_paths_end[idx - 1, _b]
                                    temp_paths_wl[idx, _b] = temp_paths_wl[idx - 1, _b]
                            idx -= 1
                        temp_costs[idx] = total_cost
                        for old_h in range(k - 1):
                            temp_paths_start[idx, old_h] = dp_paths_start[k - 1, j, p, old_h]
                            temp_paths_end[idx, old_h] = dp_paths_end[k - 1, j, p, old_h]
                            temp_paths_wl[idx, old_h] = dp_paths_wl[k - 1, j, p, old_h]
                        temp_paths_start[idx, k - 1] = j
                        temp_paths_end[idx, k - 1] = i
                        temp_paths_wl[idx, k - 1] = wl
                        if c_count < max_cands:
                            c_count += 1
            if c_count > 0:
                for t in range(c_count):
                    dp_costs[k, i, t] = temp_costs[t]
                    for _b in range(n_blocks):
                        dp_paths_start[k, i, t, _b] = temp_paths_start[t, _b]
                        dp_paths_end[k, i, t, _b] = temp_paths_end[t, _b]
                        dp_paths_wl[k, i, t, _b] = temp_paths_wl[t, _b]
                dp_counts[k, i] = c_count
    return (dp_costs, dp_paths_start, dp_paths_end, dp_paths_wl, dp_counts)
