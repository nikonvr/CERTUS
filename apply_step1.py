filepath = r'certus\core\certus_substrate_index.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False

i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('        def _p_from_q(q: np.ndarray) -> np.ndarray:') and i > 2000:
        # skip until 'return p' and then blank lines
        while not lines[i].strip() == 'return p':
            i += 1
        i += 1
        while lines[i].strip() == '':
            i += 1
        continue
    
    if line.startswith('        def _q_from_p(p: np.ndarray) -> np.ndarray:') and i > 2000:
        # skip until 'return q' and then blank lines
        while not lines[i].strip() == 'return q':
            i += 1
        i += 1
        while lines[i].strip() == '':
            i += 1
        continue

    if line.startswith('            def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:'):
        # We replace both _residuals_polish_q and _jac_polish_q with the helper call
        new_lines.append('            _residuals_polish_q, _jac_polish_q = _sellmeier_polish_helpers(_p_from_q, wl_fit_um, n_fit, w_fit_sell, log_l1l2)\n')
        # skip until after _jac_polish_q returns
        while 'return np.vstack([J_main, J_sep])' not in lines[i]:
            i += 1
        i += 1
        while lines[i].strip() == '':
            i += 1
        continue
        
    new_lines.append(line)
    i += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("certus_substrate_index.py cleaned")
