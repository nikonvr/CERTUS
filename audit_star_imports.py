import sys
import re
import importlib
import builtins

def audit():
    try:
        lines = open("pyflakes_output.txt", "r", encoding="utf-16le").readlines()
    except Exception as e:
        print("Could not read pyflakes_output.txt:", e)
        return

    pattern = re.compile(r"^(.*?):\d+:\d+: '([^']+)' may be undefined, or defined from star imports: (.*)$")
    
    true_errors = set()
    
    for line in lines:
        match = pattern.match(line.strip())
        if match:
            file_path = match.group(1)
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
                        found = True
                        break
                except Exception as e:
                    pass
            
            if not found:
                true_errors.add(f"[ERREUR ABSOLUE] {file_path} utilise '{var_name}', mais il est introuvable dans les imports étoiles : {mods_str}")

    for err in sorted(true_errors):
        print(err)

if __name__ == "__main__":
    audit()
