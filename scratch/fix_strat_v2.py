
import os

def fix_strat():
    with open('CERTUS_STRAT.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        # Fix the specific messed up blocks from the global search/replace
        stripped = line.strip()
        lstripped = line.lstrip()
        indent = len(line) - len(lstripped)
        
        # If it's over-indented by more than 16 spaces, it's likely a mess up
        if indent > 12:
            # Shift it back if it's too much
            # This is risky but we can try to bound it.
            pass

        # Specific fix for the blocks I saw
        if 'ext_counts.append' in line and indent > 24:
             new_lines.append(' ' * 24 + lstripped)
        elif 'except (TypeError, ValueError):' in line and indent > 20:
             new_lines.append(' ' * 20 + lstripped)
        elif 'continue' in line and indent > 24 and 'except' in lines[i-2]:
             new_lines.append(' ' * 24 + lstripped)
        else:
             new_lines.append(line)
             
    with open('CERTUS_STRAT.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    fix_strat()
