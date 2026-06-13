from pathlib import Path
import re

ui_file = Path('certus/ui/certus_index_spline_ui.py')
source = ui_file.read_text(encoding='utf-8')

# Replace the import
source = source.replace('from certus.ui.certus_index_spline_events_mixin import CertusIndexSplineEventsMixin',
'''from certus.ui.certus_index_spline_smartinit_mixin import CertusIndexSplineSmartInitMixin
from certus.ui.certus_index_spline_manualmesh_mixin import CertusIndexSplineManualMeshMixin
from certus.ui.certus_index_spline_corridorui_mixin import CertusIndexSplineCorridorUIMixin
from certus.ui.certus_index_spline_spectrumui_mixin import CertusIndexSplineSpectrumUIMixin
from certus.ui.certus_index_spline_layoutextras_mixin import CertusIndexSplineLayoutExtrasMixin
from certus.ui.certus_index_spline_eventsextras_mixin import CertusIndexSplineEventsExtrasMixin''')

# Replace the class inheritance
source = source.replace('    CertusIndexSplineEventsMixin,',
'''    CertusIndexSplineSmartInitMixin,
    CertusIndexSplineManualMeshMixin,
    CertusIndexSplineCorridorUIMixin,
    CertusIndexSplineSpectrumUIMixin,
    CertusIndexSplineLayoutExtrasMixin,
    CertusIndexSplineEventsExtrasMixin,''')

ui_file.write_text(source, encoding='utf-8')
print("Updated certus_index_spline_ui.py")
