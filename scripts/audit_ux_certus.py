"""CERTUS UX audit harness.

Measures every GUI module against the ergonomics criteria used by the
2026-09-03 audit: horizontal split ratio, keyboard coverage, table usability,
tooltip coverage and click-target sizes.

CRITICAL - one process per application.
Running several CERTUS apps inside a single interpreter produces WRONG split
ratios: the lazy re-export machinery in ``certus.ui.certus_ui`` makes the
measured widths depend on module import order. Measured on 2026-09-03, the same
script gave CERTUS-DESIGN 71.9 % then 60.1 %. This harness therefore re-executes
itself once per module, which is also how the suite really runs.

Usage
-----
    python scripts\\audit_ux_certus.py                 # every module, table output
    python scripts\\audit_ux_certus.py --json          # machine-readable
    python scripts\\audit_ux_certus.py --only CERTUS_FIELD
    python scripts\\audit_ux_certus.py --worker CERTUS_RE   # internal
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name -> (module, class)
MODULES: dict[str, tuple[str, str]] = {
    "CERTUS_HUB": ("CERTUS_HUB", "CertusHub"),
    "CERTUS_DESIGN": ("certus.ui.certus_design_ui", "CertusDesignApp"),
    "CERTUS_STRAT": ("certus.ui.certus_strat_ui", "CertusStratApp"),
    "CERTUS_RE": ("CERTUS_RE", "CertusREApp"),
    "CERTUS_INDEX": ("certus.ui.certus_index_ui", "CertusIndexApp"),
    "CERTUS_INDEX_SPLINE": ("certus.ui.certus_index_spline_ui", "CertusIndexSplineApp"),
    "CERTUS_FIELD": ("certus.ui.certus_field_ui", "CertusFieldApp"),
    "CERTUS_SMOOTHER": ("certus.utils.certus_curve_smoother", "CurveSmootherGUI"),
    "CERTUS_SUBSTRATE_INDEX": ("certus.ui.certus_substrate_ui", "SubstrateIndexGUI"),
    "CERTUS_METAL_SINGLE": ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
    "CERTUS_METAL_BILAYER": ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
}

# Acceptance thresholds - see docs/GEMINI_UX_TOP1_2026-09-04.md
PLOT_PCT_MIN = 65.0
PLOT_PCT_MAX = 80.0
BUTTON_MIN_W = 60  # px, for a button carrying a text label
BUTTON_MIN_H = 24  # px, click-target floor
LABEL_MAX_CHARS = 32  # beyond this a control label belongs in a tooltip
VITAL_KEYS = ("F5", "Esc", "Ctrl+S", "Ctrl+O", "F1")

MARKER = "__CERTUS_AUDIT_JSON__"


def _isolate_qsettings() -> str:
    """Redirect every QSettings("CERTUS", ...) to a throw-away INI file.

    ``QSettings.setDefaultFormat(IniFormat)`` is NOT enough on Windows: the
    two-string constructor still resolved to
    ``HKEY_CURRENT_USER\\Software\\CERTUS\\...``. The audit was therefore reading
    whatever a previous session (or the pytest suite) had left in the registry,
    which is what made the measured split ratios wander - CERTUS-DESIGN read
    71.9 % on one run and 60.1 % on the next.

    The class is swapped BEFORE any certus module is imported, because those
    modules do ``from PyQt6.QtCore import QSettings`` and capture the symbol.
    """
    import PyQt6.QtCore as qtcore

    tmp = tempfile.mkdtemp(prefix="certus_audit_qs_")
    original = qtcore.QSettings

    class _IsolatedQSettings(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            if len(args) == 2 and all(isinstance(a, str) for a in args):
                path = os.path.join(tmp, f"{args[0]}__{args[1]}.ini")
                super().__init__(path, original.Format.IniFormat)
            else:
                super().__init__(*args, **kwargs)

    qtcore.QSettings = _IsolatedQSettings
    return tmp


#: Widgets that come and go on their own. A toast auto-closes after 2.8 s and is
#: raised when the Numba warmup ends, so whether its close button is on screen
#: depends on the JIT cache being warm - not on the interface. Recording it in the
#: skeleton made three modules fail reproducibly for a reason unrelated to the UI.
TRANSIENT_OBJECT_NAMES = ("toast", "CertusToastStack")


def _is_transient(widget) -> bool:
    """True when the widget, or an ancestor, is a self-dismissing notification."""
    node = widget
    while node is not None:
        name = node.objectName() or ""
        if any(name.startswith(p) for p in TRANSIENT_OBJECT_NAMES):
            return True
        node = node.parentWidget()
    return False


def skeleton(win) -> list[str]:
    """One line per interactive control, in traversal order.

    A QTabWidget contributes its tab titles, so losing or renaming a tab shows up
    here too. Measured 2026-09-04 on three modules, two consecutive runs each:
    identical every time (DESIGN 118 controls, FIELD 52, METAL_SINGLE 33).

    Transient notifications are skipped - see TRANSIENT_OBJECT_NAMES.
    """
    from PyQt6.QtWidgets import (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QLineEdit,
        QPushButton,
        QRadioButton,
        QTabWidget,
        QToolButton,
    )

    out = []
    for w in win.findChildren(
        (
            QPushButton,
            QToolButton,
            QCheckBox,
            QRadioButton,
            QComboBox,
            QLineEdit,
            QAbstractSpinBox,
            QTabWidget,
        )
    ):
        if not w.isVisible() or _is_transient(w):
            continue
        if isinstance(w, QTabWidget):
            # ONE ENTRY PER TAB, not one joined signature. The joined form made
            # ADDING a tab look like a removal - the baseline string simply no
            # longer existed - which contradicts this guard's own contract that
            # additions are allowed. Measured 2026-09-04: wiring the Help menu
            # into RE reported its whole tab widget as "missing". Per-tab entries
            # still catch a lost or renamed tab, and they name which one.
            for i in range(w.count()):
                tab = w.tabText(i).replace("&", "").strip()
                out.append(f"{type(w).__name__}|{tab[:48]}")
            continue
        label = (w.text() if hasattr(w, "text") else "") or ""
        out.append(f"{type(w).__name__}|{(label or w.objectName())[:48]}")
    return out


def _measure(tag: str, modname: str, clsname: str, width: int = 1920, height: int = 1080) -> dict:
    """Instantiate one app and collect every metric. Runs in a dedicated process."""
    # The offscreen plugin resolves NO font unless QT_QPA_FONTDIR points at a font
    # directory: every glyph then renders as the missing-glyph box, whose advance
    # width is not a real one. Measured 2026-09-04 on "Enable QWOT penalty":
    #   offscreen bare            228 px
    #   offscreen + FONTDIR       78 px  (default family, still wrong)
    #   offscreen + FONTDIR + pinned Segoe UI 9pt   114 px
    #   real windows platform                       115 px
    # Pinning the family is what makes the measurement both headless and true.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

    _isolate_qsettings()

    from PyQt6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QShortcut
    from PyQt6.QtWidgets import (
        QAbstractSpinBox,
        QApplication,
        QCheckBox,
        QComboBox,
        QHeaderView,
        QLineEdit,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSplitter,
        QTabWidget,
        QTableView,
        QTableWidget,
        QToolButton,
    )

    app = QApplication.instance() or QApplication(sys.argv[:1])
    _PINNED_FAMILY = "Segoe UI"
    if _PINNED_FAMILY not in QFontDatabase.families():
        raise SystemExit(
            f"AUDIT ABORTED: font '{_PINNED_FAMILY}' did not resolve. "
            "Every width would be measured on a machine that does not exist."
        )
    app.setFont(QFont(_PINNED_FAMILY, 10))

    from certus.ui.certus_theme import CertusTheme

    CertusTheme.configure("light")

    cls = getattr(__import__(modname, fromlist=[clsname]), clsname)

    # CertusTheme.configure("light") above fixes the COLOURS, but the theme
    # toggle and the OS frame call load_theme_config() directly, and that reads a
    # config FILE which _isolate_qsettings does not cover. Measured 2026-09-04:
    # the persisted preference here is "dark", so the toggle recorded itself as
    # 'CertusThemeToggle|◑' - on a machine set to light it would be '◐', and the
    # skeleton baseline would then fail for a reason absent from the code.
    # Every importer captured the symbol with `from ... import`, so patch them all.
    for _mod in list(sys.modules.values()):
        if getattr(_mod, "load_theme_config", None) is not None:
            try:
                _mod.load_theme_config = lambda: "light"
            except (AttributeError, TypeError):  # C extensions and frozen modules
                pass

    win = cls()
    app.setFont(QFont(_PINNED_FAMILY, 10))
    win.setFont(QFont(_PINNED_FAMILY, 10))
    win.resize(width, height)
    win.show()

    # Drain the deferred timers before measuring. Several modules re-lay out from
    # QTimer.singleShot(0 / 100 / 600) - warmup, apply_default_layout, onboarding.
    # Measuring after two bare processEvents() gave CERTUS-INDEX 58.0 % on one run
    # and 77.9 % on the next: the ratio depended on which timers had fired.
    #
    # A fixed delay is not enough either: under the load of a full pytest run the
    # same modules had not finished building, and CERTUS-DESIGN reported a missing
    # tab that is present when the test runs alone. So wait for the control count
    # to STOP CHANGING - the interface itself says when it is done.
    _started = time.monotonic()
    _minimum = _started + 1.5
    _budget = 12.0
    _limit = _started + _budget
    _previous, _stable = -1, 0
    _settled = False
    while time.monotonic() < _limit:
        app.processEvents()
        time.sleep(0.05)
        count = len(skeleton(win))
        _stable = _stable + 1 if count == _previous else 0
        _previous = count
        # Three identical readings in a row, and never before the fixed floor
        # that lets the 600 ms onboarding timer fire.
        if _stable >= 3 and time.monotonic() >= _minimum:
            _settled = True
            break
    app.processEvents()

    # An unchanging count is NOT proof that the window finished building. Three
    # identical readings span 150 ms, while the startup timers deferred in this
    # suite reach 600 ms (1200 ms for the HUB splash) - and a window blocked in a
    # Numba compilation reports a perfectly constant count for as long as it is
    # blocked. Measured 2026-09-04 on CERTUS_DESIGN: the first worker of a cold
    # series returns 84 controls with stable=True and settle=1.53 s; warm, the
    # same code returns 86. So re-read the count after a pause that outlasts
    # those timers, and treat any movement as "was still building".
    _CONFIRM_S = 1.5
    _count_at_settle = _previous
    _confirm_until = time.monotonic() + _CONFIRM_S
    while time.monotonic() < _confirm_until:
        app.processEvents()
        time.sleep(0.05)
    app.processEvents()
    _count_confirmed = len(skeleton(win))

    out: dict = {"app": tag}
    out["skeleton_stable"] = _settled and _count_confirmed == _count_at_settle
    out["skeleton_settle_s"] = round(time.monotonic() - _started, 2)
    out["skeleton_confirm_delta"] = _count_confirmed - _count_at_settle
    if not _settled:
        out["ERROR"] = f"skeleton never settled within {_budget:.1f} s (still {_previous} controls and changing)"
    elif _count_confirmed != _count_at_settle:
        # _run_worker retries three times, and the retry runs warm: this turns a
        # silent half-built measurement into a self-healing one.
        out["ERROR"] = (
            f"skeleton was still building: {_count_at_settle} controls when it looked settled, "
            f"{_count_confirmed} after {_CONFIRM_S:.1f} s more"
        )
    out["window"] = f"{width}x{height}"
    out["qpa_platform"] = os.environ.get("QT_QPA_PLATFORM", "default")
    out["font_family"] = QApplication.font().family()
    out["font_point"] = QApplication.font().pointSizeF()
    out["font_resolved"] = QApplication.font().family() in QFontDatabase.families()

    # --- horizontal split -----------------------------------------------------
    split = win.centralWidget()
    if not isinstance(split, QSplitter):
        split = next(
            (s for s in win.findChildren(QSplitter) if s.orientation().name == "Horizontal" and s.count() >= 2),
            None,
        )
    if split is not None and sum(split.sizes()):
        sizes = split.sizes()
        left = split.widget(0)
        out["left_px"] = sizes[0]
        out["plot_pct"] = round(100.0 * sizes[-1] / sum(sizes), 1)
        out["left_min_px"] = left.minimumSizeHint().width() if left is not None else None
    else:
        out["left_px"] = out["plot_pct"] = out["left_min_px"] = None

    # A vertical scrollbar in a control panel is normal. A HORIZONTAL one means part
    # of the interface is simply unreachable without scrolling sideways.
    # left.minimumSizeHint() cannot see this: the QScrollArea absorbs its content's
    # width. Measured 2026-09-04, CERTUS_STRAT: minimumSizeHint says 446 px while the
    # scroll area's content demands 886 px in a 556 px viewport.
    out["panel_hscroll_px"] = 0
    if split is not None and split.widget(0) is not None:
        for area in split.widget(0).findChildren(QScrollArea):
            # A page never shown keeps Qt's default 640x480 geometry and reports
            # an overflow it does not have (that false positive credited
            # INDEX_SPLINE with 143 px on 2026-09-04).
            if not area.isVisible():
                continue
            bar = area.horizontalScrollBar()
            # Content can be unreachable two ways: a visible scrollbar, or
            # ScrollBarAlwaysOff with content wider than the viewport. Testing
            # isVisible() alone missed the second, which is the worse of the two:
            # nothing on screen says the content is there. Measured 2026-09-04 at
            # 1366x768: METAL_SINGLE 143 px, METAL_BILAYER 24 px, both reported 0.
            if bar is not None and bar.maximum() > 0:
                out["panel_hscroll_px"] = max(out["panel_hscroll_px"], int(bar.maximum()))

    # --- tabs -----------------------------------------------------------------
    titles = [tw.tabText(i).replace("&", "").strip() for tw in win.findChildren(QTabWidget) for i in range(tw.count())]
    joined = " | ".join(t.lower() for t in titles)
    # The ORDERED list, because nothing else records it: the skeleton used to
    # carry tab order by accident, in the joined signature that has just been
    # split per tab. Order is a real requirement (the promotional tab must not
    # sit before the synthesis tab), so it gets recorded on purpose instead.
    out["tab_titles"] = titles
    out["n_tabs"] = len(titles)
    out["has_synthesis"] = any(k in joined for k in ("synthesis", "overview", "synth"))
    out["marketing_tabs"] = sum(1 for t in titles if any(k in t.lower() for k in ("why certus", "about")))

    # --- click targets --------------------------------------------------------
    buttons = [b for b in win.findChildren((QPushButton, QToolButton)) if b.isVisible()]
    out["n_buttons"] = len(buttons)
    # Only buttons carrying a real caption. A 28 px "+" or "-" stepper is a
    # legitimate icon button, not a cramped label.
    out["btn_narrow"] = sum(1 for b in buttons if len(b.text().strip()) >= 3 and b.width() < BUTTON_MIN_W)
    out["btn_short"] = sum(1 for b in buttons if b.height() < BUTTON_MIN_H)
    out["btn_no_tooltip"] = sum(1 for b in buttons if not b.toolTip().strip())

    # --- inputs ---------------------------------------------------------------
    inputs = [w for w in win.findChildren((QLineEdit, QComboBox, QAbstractSpinBox, QCheckBox)) if w.isVisible()]
    out["n_inputs"] = len(inputs)
    out["input_no_tooltip"] = sum(1 for w in inputs if not w.toolTip().strip())

    # --- tables ---------------------------------------------------------------
    # QTableWidget IS-A QTableView: findChildren(QTableView) already returns every
    # QTableWidget. Adding the two lists counted every table twice, which is why the
    # suite was reported as having 32 tables when it has 16.
    tables = win.findChildren(QTableView)
    out["n_tables"] = len(tables)
    out["tables_sortable"] = sum(1 for t in tables if getattr(t, "isSortingEnabled", lambda: False)())
    resizable = 0
    for t in tables:
        header = t.horizontalHeader()
        if (
            header is not None
            and header.count() > 0
            and header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
        ):
            resizable += 1
    out["tables_resizable"] = resizable

    # --- keyboard -------------------------------------------------------------
    seqs = {QKeySequence(sc.key()).toString() for sc in win.findChildren(QShortcut)}
    for act in win.findChildren(QAction):
        for ks in act.shortcuts():
            seqs.add(QKeySequence(ks).toString())
    seqs.discard("")
    out["n_shortcuts"] = len(seqs)
    out["missing_vital_keys"] = [k for k in VITAL_KEYS if k not in seqs]
    out["has_undo_key"] = "Ctrl+Z" in seqs
    out["has_undo_stack"] = hasattr(win, "undo_stack")

    # --- long control labels (they dictate panel width) -----------------------
    long_labels: list[str] = []
    if split is not None and split.widget(0) is not None:
        for c in split.widget(0).findChildren((QCheckBox, QPushButton, QRadioButton)):
            text = (c.text() or "").strip()
            if len(text) > LABEL_MAX_CHARS:
                long_labels.append(text)
    out["long_labels"] = long_labels
    out["n_long_labels"] = len(long_labels)

    # --- misc -----------------------------------------------------------------
    out["has_kpi_banner"] = hasattr(win, "kpi_banner")
    out["accepts_drops"] = bool(win.acceptDrops())
    out["persists_tables"] = hasattr(win, "_qs_save_table_headers")
    out["skeleton"] = skeleton(win)

    win.close()
    return out


def _verdicts(row: dict) -> list[str]:
    """Human-readable failures for one module."""
    bad: list[str] = []
    pct = row.get("plot_pct")
    if pct is not None and pct < PLOT_PCT_MIN:
        bad.append(f"plot area {pct} % < {PLOT_PCT_MIN} %")
    lmin, lpx = row.get("left_min_px"), row.get("left_px")
    if lmin and lpx and lmin > lpx:
        bad.append(f"control panel overflows ({lmin} px needed, {lpx} px given)")
    if row.get("panel_hscroll_px"):
        bad.append(f"control panel hides {row['panel_hscroll_px']} px behind a horizontal scrollbar")
    if row.get("n_tables") and not row.get("tables_sortable"):
        bad.append(f"{row['n_tables']} tables, none sortable")
    # A table set to Stretch fills the width on purpose; only flag a module where
    # no table is either sortable or resizable.
    if row.get("n_tables") and not row.get("tables_resizable") and not row.get("tables_sortable"):
        bad.append(f"{row['n_tables']} tables, neither sortable nor resizable")
    if row.get("missing_vital_keys"):
        bad.append("missing keys: " + ", ".join(row["missing_vital_keys"]))
    if row.get("btn_narrow"):
        bad.append(f"{row['btn_narrow']} buttons < {BUTTON_MIN_W} px wide")
    if row.get("btn_short"):
        bad.append(f"{row['btn_short']} buttons < {BUTTON_MIN_H} px high")
    if row.get("n_long_labels"):
        bad.append(f"{row['n_long_labels']} control labels > {LABEL_MAX_CHARS} chars")
    if row.get("has_undo_stack") and not row.get("has_undo_key"):
        bad.append("undo_stack present but no Ctrl+Z")
    if row.get("marketing_tabs"):
        bad.append(f"{row['marketing_tabs']} marketing tab(s) in the plot area")
    if row.get("input_no_tooltip"):
        bad.append(f"{row['input_no_tooltip']} inputs without a tooltip")
    if row.get("btn_no_tooltip"):
        bad.append(f"{row['btn_no_tooltip']} buttons without a tooltip")
    # A permanent KPI strip answers the same need as a synthesis tab - CERTUS-STRAT
    # uses one because its plot area is a QStackedWidget, not a QTabWidget.
    if not row.get("has_synthesis") and not row.get("has_kpi_banner"):
        bad.append("no synthesis view (neither tab nor KPI banner)")
    return bad


def _run_worker(tag: str, width: int = 1920, height: int = 1080) -> dict:
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        QT_QPA_PLATFORM="offscreen",
        QT_QPA_FONTDIR=r"C:\Windows\Fonts",
    )
    # Three retries: instantiating a full Qt app occasionally fails on a cold
    # offscreen platform, and a spurious ERROR row would look like a regression.
    # If all 3 fail, exit with explicit error code and message.
    row: dict = {"app": tag, "ERROR": "not run"}
    for _ in range(3):
        row = _run_worker_once(tag, env, width, height)
        if "ERROR" not in row:
            return row
    sys.exit(f"AUDIT CRITICAL: {tag} worker failed 3 times: {row.get('ERROR')}")


def _run_worker_once(tag: str, env: dict, width: int = 1920, height: int = 1080) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            os.path.abspath(__file__),
            "--worker",
            tag,
            "--width",
            str(width),
            "--height",
            str(height),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    for line in (proc.stdout or "").splitlines():
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER) :])
    return {"app": tag, "ERROR": (proc.stderr or "no output")[-400:]}


def _audit_pass(names: list[str], width: int, height: int) -> tuple[list[dict], int]:
    rows = [_run_worker(n, width, height) for n in names]
    print(f"\n--- RESOLUTION: {width}x{height} ---")
    print(f"{'MODULE':<21}{'plot%':>7}{'panel':>7}{'min':>6}{'keys':>6}{'tables':>8}  ISSUES")
    print("-" * 100)
    failures = 0
    for row in rows:
        if "ERROR" in row:
            print(f"{row['app']:<21}  ERROR {row['ERROR'][:60]}")
            failures += 1
            continue
        bad = _verdicts(row)
        failures += bool(bad)
        pct = "n/a" if row["plot_pct"] is None else f"{row['plot_pct']}"
        tables = f"{row['tables_sortable']}/{row['n_tables']}"
        print(
            f"{row['app']:<21}{pct:>7}{str(row['left_px']):>7}"
            f"{str(row['left_min_px']):>6}{row['n_shortcuts']:>6}{tables:>8}  "
            f"{('OK' if not bad else bad[0])}"
        )
        for extra in bad[1:]:
            print(f"{'':<55}  {extra}")
    print("-" * 100)
    print(f"modules with at least one issue: {failures}/{len(rows)}")
    return rows, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="CERTUS UX audit")
    parser.add_argument("--worker", metavar="APP", help=argparse.SUPPRESS)
    parser.add_argument("--width", type=int, default=1920, help="window width (default 1920)")
    parser.add_argument("--height", type=int, default=1080, help="window height (default 1080)")
    parser.add_argument("--both", action="store_true", help="run audit at 1920x1080 and 1366x768")
    parser.add_argument("--only", metavar="APP", help="audit a single module")
    parser.add_argument("--json", action="store_true", help="raw JSON output")
    args = parser.parse_args()

    if args.worker:
        modname, clsname = MODULES[args.worker]
        sys.path.insert(0, REPO_ROOT)
        print(MARKER + json.dumps(_measure(args.worker, modname, clsname, args.width, args.height), ensure_ascii=False))
        return 0

    names = [args.only] if args.only else list(MODULES)

    if args.both:
        if args.json:
            r1 = [_run_worker(n, 1920, 1080) for n in names]
            r2 = [_run_worker(n, 1366, 768) for n in names]
            print(json.dumps({"1920x1080": r1, "1366x768": r2}, indent=2, ensure_ascii=False))
            f1 = sum(1 for r in r1 if "ERROR" in r or _verdicts(r))
            f2 = sum(1 for r in r2 if "ERROR" in r or _verdicts(r))
            return 1 if (f1 or f2) else 0
        _, f1 = _audit_pass(names, 1920, 1080)
        _, f2 = _audit_pass(names, 1366, 768)
        return 1 if (f1 or f2) else 0

    if args.json:
        rows = [_run_worker(n, args.width, args.height) for n in names]
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        failures = sum(1 for r in rows if "ERROR" in r or _verdicts(r))
        return 1 if failures else 0

    _, failures = _audit_pass(names, args.width, args.height)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
