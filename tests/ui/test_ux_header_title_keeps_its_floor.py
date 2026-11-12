"""A header title never shrinks under its floor (U9).

Measured on 2026-11-13: METAL's header title and subtitle painted at 6.0 and 5.2 pt. The floors were 9 and 8 px,
already under the smallest size of the scale, and the shrinking loop stopped one pixel UNDER its floor when no size
fitted.
"""

from __future__ import annotations


def test_the_label_stops_at_its_floor_when_nothing_fits(qapp) -> None:
    from certus.ui.certus_ui_widgets_utils import AutoShrinkTitleLabel

    label = AutoShrinkTitleLabel("Metal Single Layer (Transparent substrate) " * 3, default_size=16, min_size=12)
    label.resize(60, 12)
    label.show()
    qapp.processEvents()

    assert label._current_rendered_size == 12


def test_the_header_floors_are_on_the_scale(qapp) -> None:
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_ui_widgets_factory import create_header_logo_widget
    from certus.ui.certus_ui_widgets_utils import AutoShrinkTitleLabel

    header = create_header_logo_widget("METAL", "Metal Single Layer (Transparent substrate)", module_name="CERTUS_METAL")
    host = QWidget()
    header.setParent(host)
    header.resize(200, 60)
    host.show()
    qapp.processEvents()

    floors = sorted(label._min_size for label in header.findChildren(AutoShrinkTitleLabel))
    assert floors == [11, 12]  # 8 pt (Typography.CAPTION) and 9 pt, in px
