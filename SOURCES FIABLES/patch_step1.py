import re

filepath = r'certus\core\certus_substrate_index.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove duplicate `_p_from_q` and `_q_from_p` inside fit_sellmeier_global_8p
pattern1 = r'^[ \t]+def _p_from_q\(q: np\.ndarray\) -> np\.ndarray:\n(?:[ \t]+.*?\n)*?(?=[ \t]+bounds_q, _p_from_q, _q_from_p)'
content = re.sub(pattern1, '', content, flags=re.MULTILINE)

# 2. Remove duplicate `_residuals_polish_q` and `_jac_polish_q` inside fit_sellmeier_global_8p
pattern2 = r'^[ \t]+def _residuals_polish_q\(qv: np\.ndarray\) -> np\.ndarray:\n(?:[ \t]+.*?\n)*?(?=[ \t]+if polish_method ==)'
replacement2 = "            _residuals_polish_q, _jac_polish_q = _sellmeier_polish_helpers(_p_from_q, wl_fit_um, n_fit, w_fit_sell, log_l1l2)\n\n"
content = re.sub(pattern2, replacement2, content, flags=re.MULTILINE)

# 3. Same for _residuals_polish_q inside _sellmeier_global_search? Let's check if there is one there.
pattern3 = r'^[ \t]+def _residuals_polish_q\(qv: np\.ndarray\) -> np\.ndarray:\n(?:[ \t]+.*?\n)*?(?=[ \t]+q_lbfgs_opt =)'
replacement3 = "        _residuals_polish_q, _jac_polish_q = _sellmeier_polish_helpers(_p_from_q, wl_fit_um, n_fit, w_fit_sell, log_l1l2)\n\n"
content = re.sub(pattern3, replacement3, content, flags=re.MULTILINE)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched certus_substrate_index.py")
