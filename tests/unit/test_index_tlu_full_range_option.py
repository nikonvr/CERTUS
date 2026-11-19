"""INDEX: the option to fit Tauc-Lorentz-Urbach over the whole band beyond 2200 nm (lot 2d, off by default, C1).

By default, when the band goes past 2500 nm and starts under 2200 nm, INDEX fits the model up to 2200 nm, then freezes
thickness and index before the IR extension; the standalone INDEX application of the deposit database fits the whole
band (example/database_depots/README.md). `tlu_full_range` makes INDEX do the same, for comparison.
"""

from __future__ import annotations

import pandas as pd
import pytest

from certus.core.certus_index_config import TLU_TWO_STAGE_MAX_NM, OptimizationConfig, index_uses_two_stage


@pytest.mark.parametrize(
    ("lmin", "lmax", "expected"),
    [(1000.0, 5200.0, True), (400.0, 2400.0, False), (3500.0, 5200.0, False), (2199.0, 2501.0, True), (2200.0, 5200.0, False)],
)
def test_the_default_keeps_the_two_stage_rule_of_before(lmin, lmax, expected) -> None:
    assert index_uses_two_stage(lmin, lmax) is expected


def test_the_full_range_option_fits_in_one_stage() -> None:
    assert index_uses_two_stage(1000.0, 5200.0, tlu_full_range=True) is False


def test_the_first_stage_ends_at_2200_nm() -> None:
    assert TLU_TWO_STAGE_MAX_NM == 2200.0


def _config(**kwargs) -> OptimizationConfig:
    from certus.core.certus_index_config import DataType

    data = pd.DataFrame({"lambda": [1000.0, 2000.0], "T": [0.9, 0.9]})
    return OptimizationConfig(data, next(iter(DataType)), "Al2O3", 100.0, 3000.0, 1000.0, 5200.0, **kwargs)


def test_the_option_is_off_by_default_and_reaches_the_config() -> None:
    assert _config().tlu_full_range is False
    assert _config(tlu_full_range=True).tlu_full_range is True


def test_the_index_window_reads_the_option_where_it_chooses_the_pipeline() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "certus/ui/certus_index_ui_worker.py").read_text(encoding="utf-8")
    assert "use_two_stage = config.lambda_max > 2500.0" not in source
    assert source.count("index_uses_two_stage(") == 2
    assert 'tlu_full_range=getattr(self, "_tlu_full_range", False)' in source


def test_the_deposit_bench_compares_on_the_band_index_fits() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "bench_base_depots.py"
    spec = importlib.util.spec_from_file_location("bench_base_depots_for_tlu_option", path)
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)

    assert bench.fit_middle_nm(1000.0, 5200.0) == 1600.0
    assert bench.fit_middle_nm(1000.0, 5200.0, tlu_full_range=True) == 3100.0
