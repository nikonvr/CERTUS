"""D86: a tabulated index asked outside its table holds the edge value; it must say so, once."""

import logging

import numpy as np

from certus.utils.certus_re_helpers import TabularMaterial


def test_extrapolation_is_announced_once_and_values_are_unchanged(caplog):
    mat = TabularMaterial(np.array([500.0, 600.0]), np.array([1.5, 1.6]))
    with caplog.at_level(logging.WARNING, logger="CERTUS"):
        inside = mat.get_nk(np.array([550.0]))
        assert not caplog.records
        out = mat.get_nk(np.array([450.0, 700.0]))
        mat.get_nk(np.array([400.0]))
    assert len(caplog.records) == 1
    assert "held constant" in caplog.records[0].getMessage()
    assert out.real.tolist() == [1.5, 1.6]
    assert inside.real[0] == 1.55
