from pathlib import Path

def extract_fitter():
    lines = Path('certus/spline/spline_profile_corridors.py').read_text(encoding='utf-8').splitlines()
    
    funcs_to_extract = ['_fit_local_quadratic_rmse_profile', '_fit_nodes_at_fixed_d']
    
    extracted_code = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        target = None
        start = i
        
        if line.startswith('def '):
            name = line.split('def ')[1].split('(')[0].strip()
            if name in funcs_to_extract:
                target = name
                
        if target:
            # find end
            j = start + 1
            while j < len(lines):
                nl = lines[j]
                if nl.strip() and not nl.startswith(' ') and not nl.startswith('\t') and not nl.startswith('#') and not nl.startswith('@'):
                    # end of function
                    break
                j += 1
            
            # keep block
            extracted_code.extend(lines[start:j])
            # erase from original
            for k in range(start, j):
                lines[k] = ''
            i = j - 1
            
        i += 1
        
    # Write fitter file
    imports = "from typing import *\nimport numpy as np\nfrom scipy.optimize import minimize\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\nfrom certus.spline.spline_objective import *\nfrom certus.spline.certus_corridor_config import *\nimport logging\nlog = logging.getLogger('CERTUS')\n\n"
    new_code = imports + "\n".join(e for e in extracted_code)
    Path('certus/spline/certus_corridor_fitter.py').write_text(new_code, encoding='utf-8')
    
    # Write original file
    for idx, l in enumerate(lines):
        if l.startswith('from certus.spline.certus_corridor_config import *'):
            lines.insert(idx + 1, "from certus.spline.certus_corridor_fitter import *")
            break
            
    # filter empty lines where we erased
    new_lines = []
    erased_streak = False
    for l in lines:
        if l == '':
            if not erased_streak:
                new_lines.append(l)
                erased_streak = True
        else:
            new_lines.append(l)
            erased_streak = False
            
    Path('certus/spline/spline_profile_corridors.py').write_text("\n".join(new_lines), encoding='utf-8')
    
if __name__ == '__main__':
    extract_fitter()
