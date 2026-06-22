import glob

for f in glob.glob('certus/workers/certus_strat_workers_*.py'):
    if "dto" in f:
        continue
    with open(f, "r", encoding="utf-8") as file:
        content = file.read()
    
    content = content.replace(
        "from certus.workers.certus_strat_workers_excel import generate_excel_report",
        "from certus.core.certus_strat_core import generate_excel_report"
    )
    
    with open(f, "w", encoding="utf-8") as file:
        file.write(content)
        
print("Excel imports fixed!")
