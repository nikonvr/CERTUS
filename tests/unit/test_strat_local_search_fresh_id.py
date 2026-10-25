"""The refined plan of the local search, its id and the uniqueness check (`strat_local_search_fresh_id`, off by default).

Measured 2026-10-22 (reports/ANALYSE_claude_2026-10-22): the LOCAL_SEARCH row carried its parent's id on 8 accepted benches
of 8, outside `validate_unique_strategy_ids`, which withholds a table with a duplicate id.
"""

import pytest

from certus.core.certus_strat_ranking import next_refinement_strategy_id
from certus.workers.certus_strat_workers_local_search import rank_refined_first


def _row(sid, n_blocks=2):
    return {"strategy": {"strategy_id": sid, "blocks": [{"start": k, "end": k + 1, "wavelength": 600.0} for k in range(n_blocks)]}}


def test_off_the_refined_row_keeps_the_historical_order_even_with_a_duplicate_id():
    parent, other, refined = _row(5), _row(6), _row(5)
    assert rank_refined_first(refined, [parent, other, refined], lambda rows: rows) == [refined, parent, other]


def test_on_a_duplicate_id_is_refused():
    parent, refined = _row(5), _row(5)
    with pytest.raises(ValueError, match="duplicate strategy_id"):
        rank_refined_first(refined, [parent, refined], lambda rows: rows, check_ids=True)


def test_a_fresh_id_is_unique_and_passes_the_check():
    rows = [_row(sid) for sid in (5, 6, 7)]
    refined = _row(next_refinement_strategy_id(rows, 2))
    assert refined["strategy"]["strategy_id"] not in {5, 6, 7}
    assert rank_refined_first(refined, [*rows, refined], lambda r: r, check_ids=True)[0] is refined
