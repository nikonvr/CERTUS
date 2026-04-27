
import sys

def normalize_indentation(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        lstripped = line.lstrip()
        if not lstripped:
            new_lines.append(line)
            continue
        indent = len(line) - len(lstripped)
        # Normalize to 4-space multiples
        new_indent = (indent // 4) * 4
        # Handle case where it's not a multiple (e.g. 1 or 2 spaces)
        if indent % 4 >= 2:
             new_indent += 4
        new_lines.append(' ' * new_indent + lstripped)
        
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    normalize_indentation('CERTUS_STRAT.py')
