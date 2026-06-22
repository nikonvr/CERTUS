import ast

source_file = "certus/workers/certus_strat_workers.py"
with open(source_file, "r", encoding="utf-8") as f:
    source_code = f.read()

tree = ast.parse(source_code)
lines = source_code.split('\n')

targets = {
    "_execute_nominal_analysis": "NominalAnalysisStrategy",
    "_execute_strategy_search": "StrategySearchStrategy",
    "_execute_robustness_evaluation": "RobustnessEvaluationStrategy",
    "_execute_full_pipeline": "FullPipelineStrategy",
    "_execute_external_evaluation": "ExternalEvaluationStrategy"
}

for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "WorkerThread":
        for body_node in node.body:
            if isinstance(body_node, ast.FunctionDef) and body_node.name in targets:
                start_line = body_node.lineno - 1
                end_line = body_node.end_lineno
                
                method_lines = lines[start_line:end_line]
                
                # Replace self with worker
                import re
                new_method_lines = []
                for line in method_lines:
                    line = re.sub(r'\bself\b', 'worker', line)
                    new_method_lines.append(line)
                
                body = "\n".join(new_method_lines[1:]) # Skip the def _execute_X line
                
                class_name = targets[body_node.name]
                new_code = f"""
from typing import TYPE_CHECKING, Any
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS, APP_CONTEXT
from certus.utils.certus_strat_context import StratContext
from certus.workers.certus_strat_workers_dto import WorkerThreadResult
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_strat_service import calculate_nominal_properties, extract_best_rmse, select_best_strat_result
from certus.workers.certus_strat_workers_excel import generate_excel_report
from certus.utils.certus_utils import get_export_config, get_resource_path, certus_timestamp_file
from pathlib import Path
from certus.core.certus_core import SUBSTRATE_MAPPING
import certus.utils.certus_strat_service as _strat_service_module
import traceback
import time

if TYPE_CHECKING:
    from certus.workers.certus_strat_workers import WorkerThread

class {class_name}:
    def execute(self, worker: "WorkerThread") -> None:
{body}
"""
                filename = {
                    "NominalAnalysisStrategy": "certus_strat_workers_nominal.py",
                    "StrategySearchStrategy": "certus_strat_workers_search.py",
                    "RobustnessEvaluationStrategy": "certus_strat_workers_robustness.py",
                    "FullPipelineStrategy": "certus_strat_workers_pipeline.py",
                    "ExternalEvaluationStrategy": "certus_strat_workers_external.py",
                }[class_name]
                
                with open("certus/workers/" + filename, "w", encoding="utf-8") as out_f:
                    out_f.write(new_code)
                
                print(f"Extracted {class_name}")

print("AST Extraction successful!")
