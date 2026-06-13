import ast
from pathlib import Path

def analyze(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    funcs = []
    classes = []
    
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            funcs.append((node.name, node.end_lineno - node.lineno))
        elif isinstance(node, ast.ClassDef):
            classes.append((node.name, node.end_lineno - node.lineno))
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    funcs.append((f"{node.name}.{sub.name}", sub.end_lineno - sub.lineno))
                    
    funcs.sort(key=lambda x: x[1], reverse=True)
    classes.sort(key=lambda x: x[1], reverse=True)
    
    print("Top 5 largest functions:")
    for f, lines in funcs[:5]:
        print(f"  {f}: {lines} lines")
        
    print("\nTop 5 largest classes:")
    for c, lines in classes[:5]:
        print(f"  {c}: {lines} lines")

if __name__ == '__main__':
    analyze('certus/spline/spline_profile_corridors.py')
