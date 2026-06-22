import re

with open('compute_extracted.py', 'r', encoding='utf-8') as f:
    compute_src = f.read()

with open('certus/ui/certus_substrate_presenter.py', 'r', encoding='utf-8') as f:
    presenter_src = f.read()

presenter_src = re.sub(
    r'_compute_sellmeier_index,\s*_compute_analytical_index,\s*_auto_fit_sellmeier,\s*_safe_sellmeier_residual,',
    '_model_selection_score, _rank_models_by_selection_score, _fit_summary_line,',
    presenter_src
)

start_idx = presenter_src.find('    def _compute_n_results(')
compute_indented = '    ' + compute_src.replace('\n', '\n    ')
get_clean_code = """
    def _get_clean_fraction_column(self, x, c):
        y_raw = self.df[c].values
        y_clean = IndexCore.apply_dynamic_filtering(x, y_raw, 15, 2, False)
        y_clean = np.asarray(y_clean, dtype=np.float64)
        if y_clean.ndim > 1: y_clean = np.squeeze(y_clean)
        return IndexCore.to_fraction(y_clean)
"""

presenter_src = presenter_src[:start_idx] + compute_indented + '\n\n' + get_clean_code

with open('certus/ui/certus_substrate_presenter.py', 'w', encoding='utf-8') as f:
    f.write(presenter_src)
