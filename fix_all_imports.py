"""
Iterative import fixer: runs pytest --collect-only, parses errors, patches files, repeats until 0 errors.
"""
import re, ast, os, sys, subprocess, tempfile

ROOT = os.path.abspath('.')
sys.path.insert(0, ROOT)

def build_symbol_index():
    symbol_location = {}
    for dirpath, _, filenames in os.walk('certus'):
        for fname in filenames:
            if not fname.endswith('.py'): continue
            fpath = os.path.join(dirpath, fname)
            mod = fpath.replace(os.sep, '.')[:-3]
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    nm = None
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        nm = node.name
                    elif isinstance(node, ast.Assign):
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                symbol_location.setdefault(t.id, []).append(mod)
                        continue
                    if nm:
                        symbol_location.setdefault(nm, []).append(mod)
            except Exception:
                pass
    return symbol_location

def remove_sym_from_import(src, sym, bad_mod):
    pat = re.compile(r'(from\s+' + re.escape(bad_mod) + r'\s+import\s*\()([^)]*)\)', re.DOTALL)
    def repl(m):
        names = [n.strip().rstrip(',') for n in m.group(2).split('\n')]
        names = [n for n in names if n and not n.startswith('#') and n != sym]
        if not names: return ''
        return m.group(1) + '\n    ' + ',\n    '.join(names) + ',\n)'
    src2 = pat.sub(repl, src)
    pat2 = re.compile(r'from\s+' + re.escape(bad_mod) + r'\s+import\s+([^\n]+)')
    def repl2(m):
        names = [n.strip() for n in m.group(1).split(',')]
        names = [n for n in names if n and n != sym]
        if not names: return ''
        return 'from ' + bad_mod + ' import ' + ', '.join(names)
    return pat2.sub(repl2, src2)

def apply_fixes(log_content, symbol_location):
    pattern = r"ImportError: cannot import name '([^']+)' from '([^']+)'"
    errors = list(dict.fromkeys(re.findall(pattern, log_content)))
    if not errors:
        print("No import errors found!")
        return 0

    print(f"Found {len(errors)} distinct import errors: {[e[0] for e in errors]}")
    fixes = 0

    for sym, bad_mod in errors:
        locs = symbol_location.get(sym, [])
        if not locs:
            print(f"  NOT FOUND IN CODEBASE: {sym}")
            continue
        bad_parts = bad_mod.split('.')
        good_mod = sorted(set(locs), key=lambda l: -sum(1 for a, b in zip(bad_parts, l.split('.')) if a == b))[0]
        print(f"  FIX {sym}: {bad_mod} -> {good_mod}")

        for dirpath, _, fnames in os.walk('.'):
            for fn in fnames:
                if not fn.endswith('.py'): continue
                fp = os.path.join(dirpath, fn)
                try:
                    with open(fp, 'r', encoding='utf-8') as f: src = f.read()
                except Exception:
                    continue
                if ('from ' + bad_mod + ' import') not in src or sym not in src: continue

                src2 = remove_sym_from_import(src, sym, bad_mod)
                new_import = 'from ' + good_mod + ' import ' + sym
                if new_import not in src2:
                    if 'from __future__' in src2:
                        src2 = re.sub(r'(from __future__[^\n]+\n)', r'\1' + new_import + '\n', src2, count=1)
                    else:
                        src2 = new_import + '\n' + src2

                with open(fp, 'w', encoding='utf-8') as f: f.write(src2)
                print(f"    Patched: {fp}")
                fixes += 1
    return fixes

print("Building symbol index...")
symbol_location = build_symbol_index()
print(f"Indexed {len(symbol_location)} symbols.\n")

MAX_ITERATIONS = 10
for iteration in range(MAX_ITERATIONS):
    print(f"\n{'='*60}")
    print(f"ITERATION {iteration + 1}: running pytest --collect-only")
    print('='*60)

    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only', '-q'],
        capture_output=True, text=True, cwd=ROOT
    )
    output = result.stdout + result.stderr

    # Count errors
    import_errors = re.findall(r"ImportError: cannot import name '([^']+)' from '([^']+)'", output)
    module_errors = re.findall(r"ModuleNotFoundError: No module named '([^']+)'", output)
    syntax_errors = re.findall(r"SyntaxError: (.+)", output)

    n_collection_errors = len(re.findall(r'ERROR collecting', output))
    print(f"Collection errors: {n_collection_errors}")
    print(f"ImportErrors: {len(import_errors)}, ModuleErrors: {len(module_errors)}, SyntaxErrors: {len(syntax_errors)}")

    if n_collection_errors == 0:
        print("\n✅ ALL CLEAR - 0 collection errors!")
        # Print test count
        m = re.search(r'(\d+) tests collected', output)
        if m: print(f"Tests collected: {m.group(1)}")
        break

    if syntax_errors:
        print("SYNTAX ERRORS found - cannot auto-fix:")
        for e in syntax_errors: print(f"  {e}")
        # Save log for manual inspection
        with open('pytest_collect_errors.txt', 'w') as f: f.write(output)
        sys.exit(1)

    if module_errors:
        print("ModuleNotFoundErrors (not auto-fixable):")
        for e in set(module_errors): print(f"  {e}")

    fixes = apply_fixes(output, symbol_location)
    if fixes == 0:
        print("\nNo fixes applied - errors may need manual intervention.")
        with open('pytest_collect_errors.txt', 'w') as f: f.write(output)
        break
else:
    print(f"\nMax iterations ({MAX_ITERATIONS}) reached.")

print("\nFinal output snippet:")
print(output[-2000:])
