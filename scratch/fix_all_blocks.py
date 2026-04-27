
import sys

def fix_all_empty_blocks(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
            
        if i > 0:
            prev_line = None
            prev_idx = i - 1
            while prev_idx >= 0 and not lines[prev_idx].strip():
                prev_idx -= 1
            if prev_idx >= 0:
                prev_line = lines[prev_idx]
                
            if prev_line and prev_line.strip().endswith(':'):
                parent_indent = len(prev_line) - len(prev_line.lstrip())
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= parent_indent:
                    # Fix indentation of this line and all following lines until next dedent
                    diff = (parent_indent + 4) - current_indent
                    # Just fix this line for now, the script will be run iteratively or we can fix the block
                    new_lines.append(' ' * (parent_indent + 4) + line.lstrip())
                    continue
        new_lines.append(line)
        
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    fix_all_empty_blocks('CERTUS_STRAT.py')
