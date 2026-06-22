import glob

for f in glob.glob('certus/workers/certus_strat_workers_*.py'):
    if "dto" in f:
        continue
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    
    content = content.replace(
        "from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, APP_CONTEXT",
        "from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS\nfrom certus.core.certus_strat_core import APP_CONTEXT"
    )
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)
        
print("Imports fixed!")
