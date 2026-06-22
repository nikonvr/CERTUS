import re

source_file = "certus/workers/certus_strat_workers.py"
with open(source_file, "r", encoding="utf-8") as f:
    content = f.read()

# Restore original first
import subprocess
subprocess.run(["git", "checkout", "--", source_file])

with open(source_file, "r", encoding="utf-8") as f:
    content = f.read()

def replacer(match):
    name = match.group(1)
    if name == "nominal_analysis":
        return f"    def _execute_{name}(self) -> None:\n        NominalAnalysisStrategy().execute(self)\n\n"
    elif name == "strategy_search":
        return f"    def _execute_{name}(self) -> None:\n        StrategySearchStrategy().execute(self)\n\n"
    elif name == "robustness_evaluation":
        return f"    def _execute_{name}(self) -> None:\n        RobustnessEvaluationStrategy().execute(self)\n\n"
    elif name == "full_pipeline":
        return f"    def _execute_{name}(self) -> None:\n        FullPipelineStrategy().execute(self)\n\n"
    elif name == "external_evaluation":
        return f"    def _execute_{name}(self) -> None:\n        ExternalEvaluationStrategy().execute(self)\n\n"
    return match.group(0)

# We match from `    def _execute_X(self) -> None:` up to the next `    def `
# Except we need to be careful with nested defs. Nested defs have more spaces!
# A top-level method starts with exactly 4 spaces and "def ".
# So we look ahead for `\n    def `

pattern = r"    def _execute_(nominal_analysis|strategy_search|robustness_evaluation|full_pipeline|external_evaluation)\(self\) -> None:.*?(?=\n    def )"

new_content = re.sub(pattern, replacer, content, flags=re.DOTALL)

with open(source_file, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Replaced!")
