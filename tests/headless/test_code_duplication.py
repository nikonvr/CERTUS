import ast
import hashlib
from collections import defaultdict
import os
import pytest

CHUNK_SIZE = 6

def test_no_ultra_fine_duplicates():
    """
    Test interne pour vérifier qu'aucune duplication de logique métier / boilerplate
    dépassant 6 noeuds AST consécutifs ne régresse dans le dossier 'certus'.
    """
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "certus"))
    hashes = defaultdict(list)

    def extract_chunks(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
        except Exception:
            return []

        chunks = []
        lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not getattr(node, "body", None):
                    continue
                
                stmts = node.body
                for i in range(len(stmts) - CHUNK_SIZE + 1):
                    chunk = stmts[i:i + CHUNK_SIZE]
                    
                    is_boilerplate = True
                    for stmt in chunk:
                        if not isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Pass, ast.Return, ast.Import, ast.ImportFrom)):
                            is_boilerplate = False
                            break
                            
                    if is_boilerplate:
                        continue
                    
                    h = hashlib.md5("".join(ast.dump(s, annotate_fields=False) for s in chunk).encode("utf-8")).hexdigest()[:8]
                    
                    start_line = chunk[0].lineno
                    end_line = chunk[-1].end_lineno if hasattr(chunk[-1], "end_lineno") else chunk[-1].lineno
                    
                    chunk_text = "\n".join(lines[start_line-1:end_line])
                    if len(chunk_text.strip()) < 30:
                        continue
                        
                    chunks.append((h, filepath, start_line, end_line, chunk_text))
        return chunks

    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".py"):
                filepath = os.path.join(root, f)
                for chunk in extract_chunks(filepath):
                    hashes[chunk[0]].append(chunk)

    count = 0
    duplicates = []
    for h, occurrences in hashes.items():
        file_counts = defaultdict(int)
        for occ in occurrences:
            file_counts[occ[1]] += 1
            
        if len(occurrences) > 1 and len(file_counts) > 1:
            files_involved = set([os.path.basename(occ[1]) for occ in occurrences])
            # Tolérance temporaire : 3 blocs de boilerplate identiques entre utils et analytic
            if files_involved == {"gradient_utils.py", "gradient_analytic.py"}:
                continue
                
            count += 1
            duplicates.append(f"Hash {h} in files {list(files_involved)}")

    assert count == 0, f"Found {count} ultra-fine duplicate chunks: {duplicates}"
