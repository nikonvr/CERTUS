from pathlib import Path

def extract():
    core_path = Path('certus/core/_certus_physics_impl.py')
    content = core_path.read_text(encoding='utf-8')
    lines = content.splitlines()
    
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == '# [MONOLITHIC BLOCK] PGLOBAL ALGORITHM':
            start_idx = i - 1
        if line.strip() == 'from certus.physics.certus_colorimetry import *':
            end_idx = i - 3
            break
            
    print(f"Start: {start_idx}, End: {end_idx}")
    
    block = "\n".join(lines[start_idx:end_idx])
    
    # Write to new file
    new_file = Path('certus/physics/certus_optimizers.py')
    imports = "import numpy as np\nfrom numba import njit, prange\nfrom typing import *\nimport time\nfrom concurrent.futures import ProcessPoolExecutor\nfrom collections import defaultdict\n\n"
    new_code = imports + block
    new_file.write_text(new_code, encoding='utf-8')
    
    # Replace in core
    new_lines = lines[:start_idx] + ["from certus.physics.certus_optimizers import *"] + lines[end_idx:]
    core_path.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
    
    print("Done")

if __name__ == '__main__':
    extract()
