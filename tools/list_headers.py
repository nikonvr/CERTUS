from pathlib import Path

content = Path('certus/core/_certus_physics_impl.py').read_text(encoding='utf-8')
lines = content.splitlines()

for i, line in enumerate(lines):
    if line.startswith('# ===='):
        for j in range(1, 4):
            if i + j < len(lines):
                nl = lines[i+j].strip()
                if nl.startswith('# ') and nl.upper() == nl and len(nl) > 5 and not nl.startswith('# ==='):
                    print(f"Line {i+j+1}: {nl}")
                    break
