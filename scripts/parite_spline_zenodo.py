"""Function-level comparison of a published copy of the spline package against the current tree.

    python scripts/parite_spline_zenodo.py <published release root> <current root> [certus/spline]

For every module of the package in the release: each function or method (qualified name) is compared, after
removing docstrings and comments (ast.unparse), with the same name in the same module of the current tree; a
function missing from its module is looked up under the same name in all of certus/. Prints counts and lists:
identical, different, moved (identical or not), only in the release, only in the current tree. It says WHERE the
code differs, not whether a difference is an improvement. Used for reports/PARITE_ZENODO_SPLINE_2026-10-05.md.
"""
import ast
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ZEN = Path(sys.argv[1])
CUR = Path(sys.argv[2])
SUB = sys.argv[3] if len(sys.argv) > 3 else "certus/spline"


def functions(path: Path) -> dict[str, str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}
    out = {}

    def strip(node):
        for n in ast.walk(node):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) and n.body:
                first = n.body[0]
                if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str):
                    n.body = n.body[1:] or [ast.Pass()]
        return node

    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + node.name] = ast.unparse(strip(node))
            elif isinstance(node, ast.ClassDef):
                visit(node.body, prefix + node.name + ".")

    visit(tree.body)
    return out


rows = {"identical": [], "different": [], "only_zenodo": [], "only_current": []}
missing_modules = []
for zf in sorted((ZEN / SUB).glob("*.py")):
    cf = CUR / SUB / zf.name
    zfun = functions(zf)
    if not cf.exists():
        missing_modules.append(zf.name)
        rows["only_zenodo"].extend(f"{zf.name}::{n}" for n in zfun)
        continue
    cfun = functions(cf)
    for name, src in zfun.items():
        key = f"{zf.name}::{name}"
        if name not in cfun:
            rows["only_zenodo"].append(key)
        elif cfun[name] == src:
            rows["identical"].append(key)
        else:
            rows["different"].append(key)
    for name in cfun:
        if name not in zfun:
            rows["only_current"].append(f"{zf.name}::{name}")
# functions of the release missing from their module: moved elsewhere in certus/ (same qualified name)?
everywhere = {}
for f in (CUR / "certus").rglob("*.py"):
    if "__pycache__" in f.parts:
        continue
    for name, src in functions(f).items():
        everywhere.setdefault(name, []).append((str(f.relative_to(CUR)).replace("\\", "/"), src))
moved_same, moved_diff, gone = [], [], []
zen_src = {}
for zf in sorted((ZEN / SUB).glob("*.py")):
    for name, src in functions(zf).items():
        zen_src[f"{zf.name}::{name}"] = (name, src)
for key in rows["only_zenodo"]:
    name, src = zen_src[key]
    hits = everywhere.get(name, [])
    if any(s == src for _, s in hits):
        moved_same.append(f"{key} -> {next(h for h, s in hits if s == src)}")
    elif hits:
        moved_diff.append(f"{key} -> {hits[0][0]}")
    else:
        gone.append(key)
rows["only_zenodo"] = gone
rows["moved_identical"] = moved_same
rows["moved_different"] = moved_diff
new_modules = sorted(p.name for p in (CUR / SUB).glob("*.py") if not (ZEN / SUB / p.name).exists())
print(f"modules in the release: {len(list((ZEN / SUB).glob('*.py')))}; missing in certus0310: {missing_modules}")
print(f"modules only in certus0310: {new_modules}")
for k, v in rows.items():
    print(f"{k}: {len(v)}")
for k in ("only_zenodo", "moved_different", "different"):
    print(f"--- {k}")
    for x in v if False else rows[k]:
        print("  ", x)
