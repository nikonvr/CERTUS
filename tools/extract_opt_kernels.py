from pathlib import Path

def extract():
    core_path = Path('certus/core/_certus_physics_impl.py')
    content = core_path.read_text(encoding='utf-8')
    lines = content.splitlines()
    
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == '# [MONOLITHIC BLOCK] TMM & OPTIMIZATION KERNELS':
            start_idx = i - 1
        if line.strip() == '# MATERIAL DATABASE UTILS':
            end_idx = i - 1
            break
            
    print(f"Start: {start_idx}, End: {end_idx}")
    
    if start_idx == -1 or end_idx == -1:
        print("Not found!")
        return
        
    block = "\n".join(lines[start_idx:end_idx])
    
    new_file = Path('certus/physics/certus_opt_kernels.py')
    imports = "import numpy as np\nfrom numba import njit, prange\nimport math\nfrom typing import *\nfrom certus.core._certus_physics_impl import *\n\n"
    new_code = imports + block
    new_file.write_text(new_code, encoding='utf-8')
    
    new_lines = lines[:start_idx] + ["from certus.physics.certus_opt_kernels import *"] + lines[end_idx:]
    core_path.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
    print("Done")

if __name__ == '__main__':
    extract()
