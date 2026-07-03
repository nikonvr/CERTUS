import re
import sys
from pathlib import Path

def deduplicate_file(filepath: Path, anchor_def: str):
    print(f"Processing {filepath.name}...")
    content = filepath.read_text(encoding="utf-8")
    lines = content.split('\n')
    
    # Find all occurrences of the anchor def
    anchor_regex = re.compile(f"^def {anchor_def}\(")
    occurrences = []
    for i, line in enumerate(lines):
        if anchor_regex.match(line):
            occurrences.append(i)
            
    if not occurrences:
        print(f"  Anchor '{anchor_def}' not found. Skipping.")
        return False
        
    if len(occurrences) == 1:
        print(f"  Only 1 occurrence found. No duplication. Skipping.")
        return False
        
    print(f"  Found {len(occurrences)} occurrences at lines: {occurrences}")
    
    first_idx = occurrences[0]
    header_end = first_idx
    while header_end > 0 and (lines[header_end - 1].startswith('@') or lines[header_end - 1].strip() == '' or lines[header_end - 1].startswith('#')):
        header_end -= 1
        
    header_lines = lines[:header_end]
    
    last_idx = occurrences[-1]
    block_start = last_idx
    while block_start > 0 and (lines[block_start - 1].startswith('@') or lines[block_start - 1].strip() == '' or lines[block_start - 1].startswith('#')):
        block_start -= 1
        
    last_block_lines = lines[block_start:]
    
    new_content = '\n'.join(header_lines + last_block_lines)
    
    # Check if there are still duplicate defs in the new content
    def_counts = {}
    for line in new_content.split('\n'):
        if line.startswith('def '):
            def_name = line.split('(')[0][4:]
            def_counts[def_name] = def_counts.get(def_name, 0) + 1
            
    duplicates = {k: v for k, v in def_counts.items() if v > 1}
    if duplicates:
        print(f"  WARNING: Still found duplicate definitions in the merged file: {duplicates}")
    else:
        print(f"  SUCCESS: No duplicate definitions in the merged file.")
        
    print(f"  Original lines: {len(lines)}")
    print(f"  New lines: {len(new_content.split('\n'))}")
    
    filepath.write_text(new_content, encoding="utf-8")
    return True

if __name__ == "__main__":
    base_dir = Path("certus/physics")
    
    targets = [
        ("certus_tmm_matrix.py", "calculate_bare_substrate_R"),
        ("certus_tmm_oblique.py", "calculate_bare_substrate_R"),
        ("certus_tmm_single_layer.py", "calculate_bare_substrate_R"),
        ("certus_tmm_hl.py", "calculate_bare_substrate_R"),
        ("certus_tmm_backside.py", "calculate_bare_substrate_R")
    ]
    
    for filename, anchor in targets:
        filepath = base_dir / filename
        if filepath.exists():
            deduplicate_file(filepath, anchor)
        else:
            print(f"File {filepath} not found.")
