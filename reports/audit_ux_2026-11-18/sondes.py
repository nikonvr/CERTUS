import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from openpyxl import Workbook

sys.path.insert(0, os.getcwd())
out = Path(sys.argv[1])
from certus.ui import certus_strat_ui_export as export
from CERTUS_HUB import CertusHub

hub = Mock()
hub._dropped_paths.return_value = ['first.xlsx', 'second.xlsx']
hub._module_for_dropped_file.return_value = 'CERTUS_INDEX.py'
event = Mock()
CertusHub.dropEvent(hub, event)
print('accepted:', event.acceptProposedAction.called, 'launch:', hub.launch_module.call_args)
with tempfile.TemporaryDirectory(dir=out) as tmp:
    win = Mock()
    win._last_config_file = None
    win.validation_status = 'OK'
    win.opti_results = {}
    win._export_summary_facts.return_value = {'layers': 1}
    win.validation_warnings = []
    stream = io.BytesIO()
    Workbook().save(stream)
    with patch.object(export, 'get_resource_path', return_value=tmp), patch.object(export, 'IndexFitService') as svc, patch.object(export, 'get_missing_manifest_fields', return_value=[]), patch.object(export, 'generate_html_report', return_value=False) as html:
        svc.return_value.fit.return_value.manifest.to_dict.return_value = {'module':'STRAT'}
        export.CertusStratExportMixin.on_excel_ready(win, stream, {'rmse':1.0,'params':{}})
        print('html attempted:', html.called, 'files:', sorted(p.suffix for p in Path(tmp).iterdir()), 'status:', win.status_label.setText.call_args)


