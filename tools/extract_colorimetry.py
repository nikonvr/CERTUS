from pathlib import Path

def extract():
    core_path = Path('certus/core/_certus_physics_impl.py')
    content = core_path.read_text(encoding='utf-8')
    lines = content.splitlines()
    
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == '# COLORIMETRY':
            start_idx = i - 1
        if line.strip() == '# [MONOLITHIC BLOCK] MATERIAL DATABASE':
            end_idx = i - 1
            break
            
    print(f"Start: {start_idx}, End: {end_idx}")
    
    block = "\n".join(lines[start_idx:end_idx])
    
    # Write to new file
    new_file = Path('certus/physics/certus_colorimetry.py')
    new_code = "import numpy as np\nfrom numba import njit\nimport math\n\n" + block
    new_file.write_text(new_code, encoding='utf-8')
    
    # Replace in core
    new_lines = lines[:start_idx] + ["from certus.physics.certus_colorimetry import *"] + lines[end_idx:]
    core_path.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
    
    print("Done")

if __name__ == '__main__':
    extract()
