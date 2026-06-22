import ast

source_file = "certus/workers/certus_strat_workers.py"
with open(source_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

with open(source_file, "r", encoding="utf-8") as f:
    source_code = f.read()

tree = ast.parse(source_code)

targets = {
    "_execute_nominal_analysis": "    def _execute_nominal_analysis(self) -> None:\n        NominalAnalysisStrategy().execute(self)\n\n",
    "_execute_strategy_search": "    def _execute_strategy_search(self) -> None:\n        StrategySearchStrategy().execute(self)\n\n",
    "_execute_robustness_evaluation": "    def _execute_robustness_evaluation(self) -> None:\n        RobustnessEvaluationStrategy().execute(self)\n\n",
    "_execute_full_pipeline": "    def _execute_full_pipeline(self) -> None:\n        FullPipelineStrategy().execute(self)\n\n",
    "_execute_external_evaluation": "    def _execute_external_evaluation(self) -> None:\n        ExternalEvaluationStrategy().execute(self)\n\n"
}

replacements = []

for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "WorkerThread":
        for body_node in node.body:
            if isinstance(body_node, ast.FunctionDef) and body_node.name in targets:
                start_line = body_node.lineno - 1 # 0-indexed
                end_line = body_node.end_lineno # exclusive
                replacements.append((start_line, end_line, targets[body_node.name]))

# Sort in reverse order to not mess up line numbers when replacing!
replacements.sort(key=lambda x: x[0], reverse=True)

for start_line, end_line, text in replacements:
    del lines[start_line:end_line]
    lines.insert(start_line, text)

# Also add imports
import_code = """from certus.workers.certus_strat_workers_nominal import NominalAnalysisStrategy
from certus.workers.certus_strat_workers_search import StrategySearchStrategy
from certus.workers.certus_strat_workers_robustness import RobustnessEvaluationStrategy
from certus.workers.certus_strat_workers_pipeline import FullPipelineStrategy
from certus.workers.certus_strat_workers_external import ExternalEvaluationStrategy
"""

for i, line in enumerate(lines):
    if line.startswith("# === WORKER SIGNALS ==="):
        lines.insert(i, import_code + "\n")
        break

with open(source_file, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("AST based replacement successful!")
