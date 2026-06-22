import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from certus.workers.certus_re_workers import REWorker
from certus.core.certus_re_config import REWorkerRequest

@pytest.fixture
def mock_re_worker():
    req = MagicMock(spec=REWorkerRequest)
    req.cfg = {
        're_phase1_trf_restarts': 1,
        're_phase2_top_k': 1,
        're_phase3_shake_rounds': 0,
        're_qwot_alpha': 1.0,
        're_spline_n_knots': 5,
        're_phase4_scan_points': 5,
        're_phase4_beam_ap_bounds_deg': (0, 10),
    }
    worker = REWorker(req)
    worker.signals = MagicMock()
    return worker

class TestREWorkersPhases:
    @patch('certus.core.certus_re_solvers.re_execute_phase1')
    def test_execute_phase1(self, mock_p1, mock_re_worker):
        mock_p1.return_value = [{'rmse': 1.0}]
        res = mock_re_worker._execute_phase1()
        assert res == [{'rmse': 1.0}]
        mock_p1.assert_called_once_with(mock_re_worker)

    @patch('certus.core.certus_re_solvers.re_execute_phase1_p4_scan')
    def test_execute_phase1_p4_scan(self, mock_p1_scan, mock_re_worker):
        mock_p1_scan.return_value = None
        mock_re_worker._execute_phase1_p4_scan()
        mock_p1_scan.assert_called_once_with(mock_re_worker)

    @patch('certus.core.certus_re_solvers.re_execute_phase2_splines')
    def test_execute_phase2(self, mock_p2, mock_re_worker):
        mock_p2.return_value = None
        mock_re_worker._execute_phase2_splines()
        mock_p2.assert_called_once_with(mock_re_worker)

    @patch('certus.workers.certus_re_workers_phase3.REPhase3Strategy._execute_phase3_shakes')
    def test_execute_phase3(self, mock_p3, mock_re_worker):
        mock_p3.return_value = None
        mock_re_worker._execute_phase3_shakes()
        mock_p3.assert_called_once_with(None, mock_re_worker)

    @patch('certus.workers.certus_re_workers_phase4.REPhase4Strategy._execute_phase4_beam')
    def test_execute_phase4(self, mock_p4, mock_re_worker):
        mock_p4.return_value = None
        mock_re_worker._execute_phase4_beam()
        mock_p4.assert_called_once_with(None, mock_re_worker)

    def test_request_stop(self, mock_re_worker):
        assert mock_re_worker._stop is False
        mock_re_worker.request_stop()
        assert mock_re_worker._stop is True

    @patch('certus.workers.certus_re_workers.REWorker._build_re_run_context')
    @patch('certus.workers.certus_re_workers.REPhasesService.execute_all')
    @patch('certus.workers.certus_re_workers.REWorker._finalize_from_context')
    def test_run_full_pipeline(self, mock_fin, mock_exec_all, mock_ctx, mock_re_worker):
        mock_ctx.return_value = MagicMock()
        mock_re_worker._run_re_workflow()
        assert mock_ctx.called
        assert mock_exec_all.called
        assert mock_fin.called
