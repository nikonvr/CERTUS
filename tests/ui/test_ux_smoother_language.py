"""SMOOTHER must not mix two languages on screen (plan UX, 4.4).

The suite's interface is in English, but the smoothing module offered its
filtering levels in French - "Filtering Mode: Moyen" - and echoed the choice
back as "[ Niveau: ... ]". Two languages in one window is a defect of
consistency, not of translation: the operator cannot tell whether the French
words are a different setting.

⚠️ The value is NOT only a label: it is handed to ``smooth_spectrum_auto`` as
``level=``. Renaming it blindly would have changed which smoothing parameters
the engine picks. Measured first: ``_choose_params`` already accepts both
spellings ({"moyen", "medium"}, ...), so the rename is behaviour-preserving -
and the test below proves it rather than assuming it.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

FRENCH_ON_SCREEN = ("Faible", "Moyen", "Fort", "Niveau")


@pytest.fixture(scope="module")
def smoother(qapp):
    from PyQt6.QtCore import Qt

    from certus.utils.certus_curve_smoother import CurveSmootherGUI

    win = CurveSmootherGUI()
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    try:
        yield win
    finally:
        win.close()


def _visible_texts(win) -> list[str]:
    from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton

    texts = []
    for w in win.findChildren((QLabel, QPushButton, QCheckBox)):
        texts.append(w.text())
    for c in win.findChildren(QComboBox):
        texts.extend(c.itemText(i) for i in range(c.count()))
    return [t for t in texts if t]


def test_there_is_text_to_inspect(smoother):
    """Contrôle négatif : no text would make the guard pass on anything."""
    assert len(_visible_texts(smoother)) >= 10, "almost no label found - has the window changed?"


@pytest.mark.parametrize("word", FRENCH_ON_SCREEN)
def test_no_french_word_reaches_the_screen(smoother, word: str):
    found = [t for t in _visible_texts(smoother) if word in t]
    assert not found, f"French in an English window: {found}"


@pytest.mark.parametrize(
    "french,english",
    [("faible", "low"), ("moyen", "medium"), ("fort", "high")],
)
def test_renaming_a_level_does_not_change_the_smoothing(french: str, english: str):
    """The engine must treat the English name exactly like the French one.

    This is what makes the rename safe: same parameters, same result.
    """
    from certus.utils.certus_spectral_preproc import _choose_params

    kwargs = dict(period_k=0.02, noise=1e-3, span_k=2.0, n_points=500, fringe_count=8, fringe_jitter=0.1)
    assert _choose_params(level=french, **kwargs) == _choose_params(level=english, **kwargs), (
        f"'{english}' does not select the same smoothing as '{french}': the rename would silently change the result"
    )


def test_the_offered_levels_are_understood_by_the_engine(smoother):
    """Whatever the combo offers must be a level the engine knows."""
    from certus.utils.certus_spectral_preproc import _choose_params

    combo = smoother.combo_mode
    kwargs = dict(period_k=0.02, noise=1e-3, span_k=2.0, n_points=500)
    known = {_choose_params(level=name, **kwargs) for name in ("low", "medium", "high")}
    for i in range(combo.count()):
        offered = combo.itemText(i)
        assert _choose_params(level=offered, **kwargs) in known, (
            f"the combo offers {offered!r}, which the engine does not recognise - "
            "it would fall back to its default smoothing"
        )
