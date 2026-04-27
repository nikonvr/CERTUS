
import sys
import os

def fix_indentation_errors(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    iteration = 0
    while iteration < 500: # Limit iterations
        iteration += 1
        try:
            compile(content, filename, 'exec')
            print("Successfully fixed all IndentationErrors.")
            break
        except IndentationError as e:
            lines = content.splitlines(keepends=True)
            lineno = e.lineno
            # e.msg is something like "expected an indented block"
            
            # Find the parent line (last non-empty line before lineno)
            parent_idx = lineno - 2
            while parent_idx >= 0 and not lines[parent_idx].strip():
                parent_idx -= 1
            
            if parent_idx < 0:
                print("Could not find parent line.")
                break
                
            parent_line = lines[parent_idx]
            parent_indent = len(parent_line) - len(parent_line.lstrip())
            
            # The line at lineno-1 should be indented parent_indent + 4
            # Also fix all subsequent lines with the SAME OR HIGHER indentation as the broken line
            broken_line = lines[lineno-1]
            broken_indent = len(broken_line) - len(broken_line.lstrip())
            
            new_indent = parent_indent + 4
            diff = new_indent - broken_indent
            
            # Fix the broken line
            lines[lineno-1] = ' ' * new_indent + broken_line.lstrip()
            
            # Fix subsequent lines if they belong to the same block
            j = lineno
            while j < len(lines):
                if not lines[j].strip():
                    j += 1
                    continue
                line_indent = len(lines[j]) - len(lines[j].lstrip())
                if line_indent >= broken_indent:
                     lines[j] = ' ' * (line_indent + diff) + lines[j].lstrip()
                     j += 1
                else:
                     break
            
            content = "".join(lines)
        except SyntaxError as e:
            print(f"SyntaxError found (not IndentationError): {e} at line {e.lineno}")
            # If it's a syntax error, we might have over-corrected or it was already there.
            # Try to fix it if it looks like an indentation issue
            if "unexpected indent" in str(e):
                 lines = content.splitlines(keepends=True)
                 lineno = e.lineno
                 line = lines[lineno-1]
                 lines[lineno-1] = line[4:] # Remove 4 spaces
                 content = "".join(lines)
                 continue
            break
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {e}")
            break
            
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    fix_indentation_errors('CERTUS_STRAT.py')
