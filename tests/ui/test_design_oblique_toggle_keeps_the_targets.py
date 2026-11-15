"""Leaving the oblique mode of DESIGN never rewrites a target into another one (audit 2026-11-15, M-L5d).

Unticking "Oblique" turned every oblique target into a normal-incidence T target: an R target at 45 degrees silently
became a T target at 0 degree. The toggle is now refused, with a message, while such a target exists.
"""

from __future__ import annotations

import pytest

from certus_physics import ObliqueTarget


@pytest.fixture(autouse=True)
def _window_ends_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "DESIGN audit guards", main_windows_only=True)


@pytest.fixture
def design(qapp):
    from certus.ui.certus_design_ui import CertusDesignApp

    return CertusDesignApp()


def _oblique(design, targets: list[ObliqueTarget]) -> None:
    design.oblique_check.setChecked(True)
    assert design.oblique_mode is True
    design.oblique_targets = list(targets)
    design._load_targets_to_table()


def test_leaving_the_oblique_mode_is_refused_while_an_r_target_at_45_degrees_exists(design) -> None:
    _oblique(design, [ObliqueTarget(45.0, "s", 500.0, 600.0, 0.9, 1.0, "R")])
    logged: list[str] = []
    original_log = design.log
    design.log = lambda message, level="INFO": (logged.append(f"{level}: {message}"), original_log(message, level))[1]

    design.oblique_check.setChecked(False)

    assert design.oblique_mode is True
    assert design.oblique_check.isChecked() is True
    [kept] = design._get_oblique_tgts()
    assert (kept.angle, kept.target_type, kept.lmin, kept.lmax) == (45.0, "R", 500.0, 600.0)
    assert any(line.startswith("WARNING") and "oblique" in line.lower() for line in logged), logged


def test_t_targets_at_normal_incidence_still_convert(design) -> None:
    _oblique(design, [ObliqueTarget(0.0, "s", 500.0, 600.0, 0.9, 1.0, "T")])

    design.oblique_check.setChecked(False)

    assert design.oblique_mode is False
    [normal] = design._get_tgts()
    assert (normal.lmin, normal.lmax, normal.tmin, normal.tmax) == (500.0, 600.0, 0.9, 1.0)
