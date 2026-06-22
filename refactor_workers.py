import re
import os

source_file = "certus/workers/certus_strat_workers.py"
with open(source_file, "r", encoding="utf-8") as f:
    content = f.read()

# Define boundaries for methods
methods_to_extract = {
    "NominalAnalysisStrategy": "_execute_nominal_analysis",
    "StrategySearchStrategy": "_execute_strategy_search",
    "RobustnessEvaluationStrategy": "_execute_robustness_evaluation",
    "FullPipelineStrategy": "_execute_full_pipeline",
    "ExternalEvaluationStrategy": "_execute_external_evaluation",
}

# Find the start and end of each method
extracted = {}
for class_name, method_name in methods_to_extract.items():
    pattern = rf"    def {method_name}\(self\) -> None:(.*?)(?=    def _execute_|    def stop_check|    def _run_segment)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        body = match.group(1)
        # Rename self to worker
        # But only self. or self, not words containing self
        body = re.sub(r'\bself\b', 'worker', body)
        
        # Replace the method signature
        new_code = f"""
from typing import TYPE_CHECKING, Any
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, APP_CONTEXT
from certus.utils.certus_strat_context import StratContext
from certus.workers.certus_strat_workers_dto import WorkerThreadResult
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_strat_service import calculate_nominal_properties, extract_best_rmse, select_best_strat_result
import traceback
import time

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class {class_name}:
    def execute(self, worker: "WorkerThread") -> None:{body}
"""
        extracted[class_name] = new_code
    else:
        print(f"Method {method_name} not found!")

# Write to files
filenames = {
    "NominalAnalysisStrategy": "certus_strat_workers_nominal.py",
    "StrategySearchStrategy": "certus_strat_workers_search.py",
    "RobustnessEvaluationStrategy": "certus_strat_workers_robustness.py",
    "FullPipelineStrategy": "certus_strat_workers_pipeline.py",
    "ExternalEvaluationStrategy": "certus_strat_workers_external.py",
}

for class_name, code in extracted.items():
    with open("certus/workers/" + filenames[class_name], "w", encoding="utf-8") as f:
        f.write(code)

print("Extraction script done!")
