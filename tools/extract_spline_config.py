import sys
from pathlib import Path

def extract_configs():
    lines = Path('certus/spline/spline_profile_corridors.py').read_text(encoding='utf-8').splitlines()
    
    classes_to_extract = ['ProfileCorridorConfig', 'RegularGridProfileContext', 'CorridorContextBuilder', 'CorridorWalkSideContext', 'CorridorLiveStreamer']
    
    extracted_code = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        is_dataclass = line.startswith('@dataclass')
        is_class = line.startswith('class ')
        
        target = None
        start = i
        
        if is_class:
            name = line.split('class ')[1].split('(')[0].split(':')[0].strip()
            if name in classes_to_extract:
                target = name
        elif is_dataclass and i + 1 < len(lines) and lines[i+1].startswith('class '):
            name = lines[i+1].split('class ')[1].split('(')[0].split(':')[0].strip()
            if name in classes_to_extract:
                target = name
                
        if target:
            # find end
            j = start + 1
            if is_dataclass: j += 1
            while j < len(lines):
                nl = lines[j]
                if nl.strip() and not nl.startswith(' ') and not nl.startswith('\t') and not nl.startswith('#') and not nl.startswith('@'):
                    # end of class
                    break
                j += 1
            
            # keep block
            extracted_code.extend(lines[start:j])
            # erase from original
            for k in range(start, j):
                lines[k] = ''
            i = j - 1
            
        i += 1
        
    # Write config file
    imports = "from dataclasses import dataclass, field\nfrom typing import *\nimport numpy as np\nfrom certus.core.certus_core import *\nfrom certus.spline.certus_index_spline_core import *\n\n"
    new_code = imports + "\n".join(e for e in extracted_code)
    Path('certus/spline/certus_corridor_config.py').write_text(new_code, encoding='utf-8')
    
    # Write original file
    # We should add the import at the top
    # let's find the end of imports
    for idx, l in enumerate(lines):
        if l.startswith('log = logging.getLogger'):
            lines.insert(idx, "from certus.spline.certus_corridor_config import *")
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
    extract_configs()
