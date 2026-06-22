import glob

for f in glob.glob('certus/workers/certus_strat_workers_*.py'):
    if "dto" in f:
        continue
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    
    content = content.replace(
        "from certus.utils.certus_utils import get_export_config, get_resource_path, certus_timestamp_file",
        "from certus.core.certus_core import get_export_config, get_resource_path, certus_timestamp_file"
    )
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)
        
print("Core imports fixed!")
