"""Integration-style checks for METAL progress payloads and UI shaping."""

from __future__ import annotations

from types import SimpleNamespace

from certus.metal.certus_metal_common import (
    METAL_GLOBAL_STATUS,
    build_metal_progress_event,
)


class _DummyProgressWidget:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def update(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _DummyLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, msg: str) -> None:
        self.messages.append(msg)


class _DummyApp:
    def __init__(self) -> None:
        self.logger = _DummyLogger()
        self.progress_widget = _DummyProgressWidget()
        self.widgets = {
            "live_eM_label": SimpleNamespace(setText=lambda *_: None),
            "live_eL_label": SimpleNamespace(setText=lambda *_: None),
            "live_n_infini_label": SimpleNamespace(setText=lambda *_: None),
            "live_A_diel_label": SimpleNamespace(setText=lambda *_: None),
            "live_mse_label": SimpleNamespace(setText=lambda *_: None),
        }
        self._last_worker_params = {
            "num_knots": 5,
            "target_lambda": __import__("numpy").array([400.0, 500.0, 600.0]),
        }
        self.mse_data = {"iterations": [], "errors": []}
        self.mse_curve = SimpleNamespace(setData=lambda *_: None)

    def _on_optim_progress(self, data):
        iteration = data.get("iteration", 0)
        mse = data.get("mse", 0)
        rmse = mse ** 0.5 if mse > 0 else 0
        progress_pct = data.get("progress_pct", None)
        mode = data.get("mode", "DE")
        best_cost = float(data.get("best_cost", mse))
        evals = int(data.get("evaluation_count", 0))
        elapsed_s = float(data.get("elapsed_s", 0.0))
        max_iter = int(data.get("max_iteration", 0))
        self.logger.info(
            f"{mode} | Gen {iteration}/{max_iter} | Evals {evals} | Best {best_cost:.6e} | dM 0.00 nm"
        )
        self.progress_widget.update(
            iteration=iteration,
            max_iter=max_iter,
            evals=evals,
            phase=mode,
            extra_info=f"RMSE: {rmse:.6f} | Best: {best_cost:.6f} | {elapsed_s:.0f}s" if rmse > 0 else f"Best: {best_cost:.6f} | {elapsed_s:.0f}s",
            progress_pct=progress_pct,
        )


def test_metal_progress_event_looks_like_pglobal_progress() -> None:
    event = build_metal_progress_event(
        phase="global_opt",
        progress_pct=42,
        message="PGLOBAL | Gen 7/50",
        iteration=7,
        max_iteration=50,
        evaluation_count=1234,
        best_cost=0.00123,
        elapsed_s=12.5,
        mode=METAL_GLOBAL_STATUS,
    )

    app = _DummyApp()
    app._on_optim_progress(
        {
            "iteration": event.iteration,
            "mse": event.best_cost,
            "params": [1.0, 2.0, 3.0, 4.0],
            "progress_pct": event.progress_pct,
            "mode": event.mode,
            "best_cost": event.best_cost,
            "evaluation_count": event.evaluation_count,
            "elapsed_s": event.elapsed_s,
            "max_iteration": event.max_iteration,
        }
    )

    assert app.progress_widget.calls, "Progress widget should receive one update"
    call = app.progress_widget.calls[-1]
    assert call["iteration"] == 7
    assert call["max_iter"] == 50
    assert call["evals"] == 1234
    assert call["phase"] == METAL_GLOBAL_STATUS
    assert "Best:" in call["extra_info"]
    assert call["progress_pct"] == 42


def test_metal_progress_event_preserves_fallbacks() -> None:
    event = build_metal_progress_event(phase="local_opt", progress_pct=-20, message="Local", best_cost=1.0)
    assert event.progress_pct == 0
    assert event.mode == METAL_GLOBAL_STATUS
