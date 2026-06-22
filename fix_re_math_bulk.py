"""
Bulk-fix pass 2: certus_re_math -> certus_re_config
Same logic as fix_re_helpers_bulk.py but for symbols incorrectly
imported from certus_re_math that actually live in certus_re_config.
"""
import ast, os, re, sys, importlib

sys.path.insert(0, os.path.abspath('.'))

BAD_MOD  = 'certus.utils.certus_re_math'
GOOD_MOD = 'certus.utils.certus_re_config'

math_exports   = set(dir(importlib.import_module(BAD_MOD)))
config_exports = set(dir(importlib.import_module(GOOD_MOD)))

config_only = config_exports - math_exports
print(f"Symbols in config but NOT in re_math: {len(config_only)}")

def strip_names(src, bad_mod, names_to_remove):
    pat = re.compile(r'(from\s+' + re.escape(bad_mod) + r'\s+import\s*\()([^)]*)\)', re.DOTALL)
    def repl(m):
        lines = m.group(2).split('\n')
        kept = [l for l in lines if l.strip().rstrip(',') and not l.strip().startswith('#') and l.strip().rstrip(',') not in names_to_remove]
        if not kept: return ''
        return m.group(1) + '\n'.join(kept) + '\n)'
    src2 = pat.sub(repl, src)
    pat2 = re.compile(r'from\s+' + re.escape(bad_mod) + r'\s+import\s+([^\n(\\][^\n]*)')
    def repl2(m):
        names = [n.strip() for n in m.group(1).split(',')]
        names = [n for n in names if n and n not in names_to_remove]
        if not names: return ''
        return 'from ' + bad_mod + ' import ' + ', '.join(names)
    return pat2.sub(repl2, src2)

files_patched = []
for dirpath, _, fnames in os.walk('.'):
    for fn in fnames:
        if not fn.endswith('.py'): continue
        fp = os.path.join(dirpath, fn)
        try:
            with open(fp, 'r', encoding='utf-8') as f: src = f.read()
        except: continue
        if 'from ' + BAD_MOD + ' import' not in src: continue

        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        to_move = []
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom): continue
            if node.module != BAD_MOD: continue
            for alias in node.names:
                if alias.name in config_only:
                    to_move.append(alias.name)

        if not to_move: continue

        print(f"\nPatching {fp}: moving {to_move}")
        src2 = strip_names(src, BAD_MOD, set(to_move))

        new_import = f'from {GOOD_MOD} import (\n    ' + ',\n    '.join(sorted(to_move)) + ',\n)'
        if f'from {GOOD_MOD} import' in src2:
            existing_pat = re.compile(r'(from\s+' + re.escape(GOOD_MOD) + r'\s+import\s*\()([^)]*)\)', re.DOTALL)
            def extend_repl(m):
                existing = [n.strip().rstrip(',') for n in m.group(2).split('\n')]
                existing = [n for n in existing if n and not n.startswith('#')]
                all_n = sorted(set(existing + to_move))
                return m.group(1) + '\n    ' + ',\n    '.join(all_n) + ',\n)'
            src2 = existing_pat.sub(extend_repl, src2, count=1)
        else:
            ins = src2.find('from ' + BAD_MOD)
            if ins == -1: src2 = new_import + '\n' + src2
            else: src2 = src2[:ins] + new_import + '\n' + src2[ins:]

        with open(fp, 'w', encoding='utf-8') as f: f.write(src2)
        files_patched.append(fp)

print(f"\nTotal files patched: {len(files_patched)}")
