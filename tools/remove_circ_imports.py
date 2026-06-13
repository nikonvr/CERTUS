from pathlib import Path

modules = ['certus_optical_models.py', 'certus_tmm_core.py', 'certus_opt_kernels.py', 'certus_colorimetry.py', 'certus_material_db.py', 'certus_optimizers.py', 'certus_strat_kernels.py']

for mod in modules:
    path = Path('certus/physics/') / mod
    content = path.read_text(encoding='utf-8')
    content = content.replace('from certus.core._certus_physics_impl import *\n', '')
    path.write_text(content, encoding='utf-8')
    
print("Removed circular imports")
