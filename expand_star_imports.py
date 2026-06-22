import os
import re
import sys
import importlib
import builtins
import subprocess
from collections import defaultdict

def run_pyflakes(target_path="certus"):
    print(f"Running pyflakes on {target_path}...")
    result = subprocess.run(["python", "-m", "pyflakes", target_path], capture_output=True, text=True)
    return result.stdout + result.stderr

def expand_imports():
    # If a path filter is passed via command-line, use it (e.g. certus/spline)
    filter_path = sys.argv[1] if len(sys.argv) > 1 else None
    if filter_path:
        filter_path = filter_path.replace('/', os.sep).replace('\\', os.sep)
        print(f"Filtering files to modify: only files containing '{filter_path}'")
        
    output = run_pyflakes("certus") # We run pyflakes globally to see everything
    
    # regex to match: certus/spline/certus_corridor_utils.py:1006:15: 'minimize' may be undefined, or defined from star imports: mod1, mod2
    # support optional column number (sometimes pyflakes format varies)
    pattern = re.compile(r"^(.*?):\d+(?::\d+)?: '([^']+)' may be undefined, or defined from star imports: (.*)$")
    
    # map: file_path -> { module_name -> set(var_names) }
    file_to_mod_vars = defaultdict(lambda: defaultdict(set))
    
    # Track missing imports that couldn't be resolved anywhere
    unresolved_errors = defaultdict(list)
    
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            file_path = match.group(1).replace('/', os.sep).replace('\\', os.sep)
            
            # Apply path filter if specified
            if filter_path and filter_path not in file_path:
                continue
                
            var_name = match.group(2)
            mods_str = match.group(3)
            modules = [m.strip() for m in mods_str.split(',')]
            
            if hasattr(builtins, var_name):
                continue
                
            found = False
            for mod_name in modules:
                try:
                    mod = importlib.import_module(mod_name)
                    if hasattr(mod, var_name):
                        file_to_mod_vars[file_path][mod_name].add(var_name)
                        found = True
                        break
                except Exception as e:
                    pass
            
            if not found:
                unresolved_errors[file_path].append((var_name, modules))
                
    # Now, we rewrite the files!
    for file_path, mod_vars in file_to_mod_vars.items():
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        new_lines = []
        for line in lines:
            import_star_match = re.match(r"^(\s*)from\s+([A-Za-z0-9_.]+)\s+import\s+\*(\s*(?:#.*)?)$", line)
            if import_star_match:
                indent = import_star_match.group(1)
                mod_name = import_star_match.group(2)
                comment = import_star_match.group(3)
                
                if mod_name in mod_vars and len(mod_vars[mod_name]) > 0:
                    vars_str = ", ".join(sorted(mod_vars[mod_name]))
                    new_line = f"{indent}from {mod_name} import {vars_str}{comment}\n"
                    # If it's too long, split it, but python allows long lines, or we can use parenthesis
                    if len(new_line) > 100:
                        new_line = f"{indent}from {mod_name} import (\n"
                        for v in sorted(mod_vars[mod_name]):
                            new_line += f"{indent}    {v},\n"
                        new_line += f"{indent}){comment}\n"
                    new_lines.append(new_line)
                else:
                    # No variables were actually used from this star import! We can comment it out.
                    new_lines.append(f"{indent}# from {mod_name} import *  # Unused\n")
            else:
                new_lines.append(line)
                
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
    print("Star imports expanded successfully.")
    
    if unresolved_errors:
        print("\n--- UNRESOLVED ERRORS (These are TRUE missing imports / crashes) ---")
        for fpath, errs in unresolved_errors.items():
            print(f"File: {fpath}")
            for vname, mods in errs:
                print(f"  - Missing: {vname}")
        
if __name__ == "__main__":
    expand_imports()
