"""
Bulk-fix: scan certus_re_helpers import blocks across all files,
move any symbol that belongs to certus_re_config to the correct module,
all in a single pass (no iteration needed).
"""
import ast, os, re, sys

sys.path.insert(0, os.path.abspath('.'))

# Load actual exports of both modules
import importlib

def get_exports(mod_path):
    try:
        mod = importlib.import_module(mod_path)
        return set(dir(mod))
    except Exception as e:
        print(f"Could not import {mod_path}: {e}")
        return set()

helpers_exports = get_exports('certus.utils.certus_re_helpers')
config_exports  = get_exports('certus.utils.certus_re_config')

print(f"certus_re_helpers exports: {len(helpers_exports)}")
print(f"certus_re_config exports:  {len(config_exports)}")

# Symbols that files incorrectly import from helpers but are really in config
config_only = config_exports - helpers_exports

print(f"\nSymbols in config but NOT in helpers: {len(config_only)}")

BAD_MOD  = 'certus.utils.certus_re_helpers'
GOOD_MOD = 'certus.utils.certus_re_config'

files_patched = []

for dirpath, _, fnames in os.walk('.'):
    for fn in fnames:
        if not fn.endswith('.py'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                src = f.read()
        except:
            continue
        if 'from ' + BAD_MOD + ' import' not in src:
            continue

        # Parse the file and find all names imported from BAD_MOD
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        to_move = []  # names that should come from GOOD_MOD
        to_keep = []  # names that legitimately stay in helpers

        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != BAD_MOD:
                continue
            for alias in node.names:
                name = alias.name
                if name in config_only:
                    to_move.append(name)
                else:
                    to_keep.append(name)

        if not to_move:
            continue  # nothing to fix in this file

        print(f"\nPatching {fp}:")
        print(f"  Moving to config: {to_move}")

        # Remove to_move names from the helpers import block(s)
        # Strategy: regex replace each 'from BAD_MOD import (...)' block
        def strip_names(src, bad_mod, names_to_remove):
            # multi-line: from X import (\n...\n)
            pat = re.compile(
                r'(from\s+' + re.escape(bad_mod) + r'\s+import\s*\()([^)]*)\)',
                re.DOTALL
            )
            def repl(m):
                lines = m.group(2).split('\n')
                kept = []
                for line in lines:
                    stripped = line.strip().rstrip(',')
                    if stripped and not stripped.startswith('#') and stripped not in names_to_remove:
                        kept.append(line)
                if not kept:
                    return ''  # entire block removed
                return m.group(1) + '\n'.join(kept) + '\n)'
            src2 = pat.sub(repl, src)

            # single-line
            pat2 = re.compile(r'from\s+' + re.escape(bad_mod) + r'\s+import\s+([^\n(\\][^\n]*)')
            def repl2(m):
                names = [n.strip() for n in m.group(1).split(',')]
                names = [n for n in names if n and n not in names_to_remove]
                if not names:
                    return ''
                return 'from ' + bad_mod + ' import ' + ', '.join(names)
            return pat2.sub(repl2, src2)

        src2 = strip_names(src, BAD_MOD, set(to_move))

        # Add the new import from GOOD_MOD
        new_import = f'from {GOOD_MOD} import (\n    ' + ',\n    '.join(sorted(to_move)) + ',\n)'

        # Check if already importing from GOOD_MOD — if so, extend; else add new block
        if f'from {GOOD_MOD} import' in src2:
            # Append names to existing block
            existing_pat = re.compile(
                r'(from\s+' + re.escape(GOOD_MOD) + r'\s+import\s*\()([^)]*)\)',
                re.DOTALL
            )
            def extend_repl(m):
                existing_names = [n.strip().rstrip(',') for n in m.group(2).split('\n')]
                existing_names = [n for n in existing_names if n and not n.startswith('#')]
                all_names = sorted(set(existing_names + to_move))
                return m.group(1) + '\n    ' + ',\n    '.join(all_names) + ',\n)'
            src2 = existing_pat.sub(extend_repl, src2, count=1)
        else:
            # Insert after last 'from certus...' import or at top
            if 'from __future__' in src2:
                src2 = re.sub(r'(from __future__[^\n]+\n)', r'\1' + new_import + '\n', src2, count=1)
            else:
                # Insert before the first import from BAD_MOD or at very top
                insert_pos = src2.find('from ' + BAD_MOD)
                if insert_pos == -1:
                    src2 = new_import + '\n' + src2
                else:
                    src2 = src2[:insert_pos] + new_import + '\n' + src2[insert_pos:]

        with open(fp, 'w', encoding='utf-8') as f:
            f.write(src2)
        files_patched.append(fp)

print(f"\nTotal files patched: {len(files_patched)}")
print("Done — all config constants migrated from helpers import blocks.")
