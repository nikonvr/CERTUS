import re

filepath = r'certus\core\certus_substrate_index.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove _p_from_q and _q_from_p inside fit_sellmeier_global_8p
# They are exactly bounded by `def _p_from_q` and `bounds_q, _p_from_q`
pattern1 = r'^[ \t]+def _p_from_q\(q: np\.ndarray\) -> np\.ndarray:\n(?:[ \t]+.*?\n)*?(?=[ \t]+bounds_q, _p_from_q)'
content = re.sub(pattern1, '', content, flags=re.MULTILINE)

# 2. Inside fit_sellmeier_global_8p, the _residuals_polish_q and _jac_polish_q are defined right before `polish_res = scipy.optimize.least_squares`
# Let's remove them and use the factory:
# Wait! Instead of redefining them, let's look at how they are defined.
# I will just write a specific script to patch this accurately after I check it.

with open(r'patch_step1_wip.py', 'w', encoding='utf-8') as f:
    f.write('wip')
