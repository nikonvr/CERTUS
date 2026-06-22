import re

source_file = "certus/workers/certus_strat_workers.py"
with open(source_file, "r", encoding="utf-8") as f:
    content = f.read()

pattern = r"    def _execute_strategy_search\(self\) -> None:.*?(?=    def stop_check\(\):)"

replacement = """    def _execute_strategy_search(self) -> None:
        StrategySearchStrategy().execute(self)

    def _execute_robustness_evaluation(self) -> None:
        RobustnessEvaluationStrategy().execute(self)

    def _execute_full_pipeline(self) -> None:
        FullPipelineStrategy().execute(self)

    def _execute_external_evaluation(self) -> None:
        ExternalEvaluationStrategy().execute(self)

"""

new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
# And manually replace _execute_nominal_analysis (but NOT auto)
pattern_nom = r"    def _execute_nominal_analysis\(self\) -> None:.*?(?=    def _execute_nominal_analysis_auto)"
repl_nom = """    def _execute_nominal_analysis(self) -> None:
        NominalAnalysisStrategy().execute(self)

"""
new_content, count2 = re.subn(pattern_nom, repl_nom, new_content, flags=re.DOTALL)

if count > 0 and count2 > 0:
    with open(source_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Replaced successfully!")
else:
    print("Pattern not found!")
