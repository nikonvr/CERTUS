from pathlib import Path

p = Path('_pytest_nodeids.txt')
lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
keep = []
for line in lines:
    s = line.strip()
    if '::' in s and not s.startswith('platform ') and not s.startswith('rootdir') and not s.startswith('configfile') and not s.startswith('plugins') and not s.startswith('testpaths') and not s.startswith('collected ') and not s.startswith('<') and not s.startswith('=') and not s.startswith('================'):
        keep.append(s)
p.write_text('\n'.join(keep) + '\n', encoding='utf-8')
print(len(keep))
