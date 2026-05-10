import os
import sys
import time
from pathlib import Path


def _pump_events(app, steps=40, dt_s=0.02):
    for _ in range(steps):
        app.processEvents()
        time.sleep(dt_s)


def _assert_rmse_for_file(win, app, xlsx_path: Path, max_rmse: float) -> None:
    ok = win.load_reverse_engineering_from_path(str(xlsx_path))
    if not ok:
        raise AssertionError(f"RE loading failed:{xlsx_path}")

    _pump_events(app, steps=60, dt_s=0.02)
    rmse = win._compute_re_rmse(0.0, 0.0, 0.0)
    if rmse is None:
        raise AssertionError(f"RMSE None pour {xlsx_path.name}")
    if not (rmse < max_rmse):
        raise AssertionError(f"RMSE too high for{xlsx_path.name}: {rmse} >= {max_rmse}")
    if win.front_table.rowCount() <= 0:
        raise AssertionError(f"No layer in front table after loading:{xlsx_path.name}")

    print(f"{xlsx_path.name}: RMSE={rmse:.6f} < {max_rmse:.3f}")


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    base = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(base))

    from PyQt6.QtWidgets import QApplication, QMessageBox
    from CERTUS_RE import CertusREApp

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.information = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    QMessageBox.critical = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    win = CertusREApp()

    deadline = time.time() + 90.0
    while not getattr(win, "_warmup_done", False) and time.time() < deadline:
        app.processEvents()
        time.sleep(0.05)

    if not getattr(win, "_warmup_done", False):
        raise AssertionError("Warmup CERTUS_RE not completed within the deadline.")

    _assert_rmse_for_file(win, app, base / "example" / "reverse_sample.xlsx", max_rmse=0.05)
    # _assert_rmse_for_file(win, app, base / "reverse_sample0.xlsx", max_rmse=0.05)

    print("Smoke RE reverse samples: OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as exc:
        print(f"Smoke RE reverse samples: FAIL ({exc})")
        raise
