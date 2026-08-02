#!/usr/bin/env python3
import ast
import os
import sys
from pathlib import Path

class ExceptionVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.relative_path = filepath.relative_to(filepath.parents[2]) if len(filepath.parts) > 2 else filepath
        self.issues = []

    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            line_no = handler.lineno
            # Determine type of exception caught
            handler_type = "bare"
            if handler.type is not None:
                if isinstance(handler.type, ast.Name):
                    handler_type = handler.type.id
                elif isinstance(handler.type, ast.Tuple):
                    handler_type = "tuple"
                else:
                    handler_type = ast.unparse(handler.type) if hasattr(ast, "unparse") else "complex"

            # Check if it's generic
            is_generic = handler_type in ("bare", "Exception", "BaseException")

            # Check if it's silent/unlogged
            is_silent = True
            has_logging_or_raise = False
            
            for child in ast.walk(handler):
                # Check for raise statements
                if isinstance(child, ast.Raise):
                    has_logging_or_raise = True
                    is_silent = False
                    break
                # Check for calls like logger.info, print, logging.error, etc.
                if isinstance(child, ast.Call):
                    call_str = ""
                    if isinstance(child.func, ast.Name):
                        call_str = child.func.id
                    elif isinstance(child.func, ast.Attribute):
                        call_str = ast.unparse(child.func) if hasattr(ast, "unparse") else child.func.attr
                    
                    call_lower = call_str.lower()
                    if any(term in call_lower for term in ("log", "print", "warn", "error", "info", "traceback", "exception")):
                        has_logging_or_raise = True
                        is_silent = False
                        break

            # If it has only "pass", "continue" or simple returns, it's silent
            body_statements = [stmt for stmt in handler.body if not isinstance(stmt, ast.Expr)]
            if len(body_statements) == 1:
                first_stmt = body_statements[0]
                if isinstance(first_stmt, (ast.Pass, ast.Continue)) or (
                    isinstance(first_stmt, ast.Return) and first_stmt.value is None
                ):
                    is_silent = True

            if is_generic or is_silent:
                self.issues.append({
                    "line": line_no,
                    "type": handler_type,
                    "is_generic": is_generic,
                    "is_silent": is_silent,
                    "code": (ast.unparse(handler).split('\n')[0] if hasattr(ast, "unparse") else "")
                })
        
        self.generic_visit(node)


def audit_exceptions(root_dir: Path) -> dict:
    all_issues = {}
    total_files = 0
    total_try_blocks = 0
    
    for dirpath, _, filenames in os.walk(root_dir):
        # Exclude pycache and virtual environments
        if any(part in dirpath for part in ("__pycache__", ".venv", "env", "build", "dist")):
            continue
            
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = Path(dirpath) / filename
                total_files += 1
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=str(filepath))
                    
                    visitor = ExceptionVisitor(filepath)
                    visitor.visit(tree)
                    
                    if visitor.issues:
                        all_issues[str(visitor.relative_path)] = visitor.issues
                except Exception as e:
                    print(f"Error parsing {filepath}: {e}", file=sys.stderr)
                    
    return all_issues


def generate_report(issues: dict, output_file: Path):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# CERTUS - Rapport d'Audit des Blocs Try/Except\n\n")
        f.write("Ce rapport répertorie tous les blocs `try/except` contenant des `bare except`, ")
        f.write("des captures d'exceptions génériques (`Exception`), ou des gestions silencieuses.\n\n")
        
        total_issues = sum(len(file_issues) for file_issues in issues.values())
        f.write(f"**Total de blocs problématiques identifiés :** {total_issues} répartis sur {len(issues)} fichiers.\n\n")
        
        f.write("## Table des Matières\n\n")
        for filepath in sorted(issues.keys()):
            f.write(f"- [{filepath}](#{filepath.replace('/', '').replace('.', '').replace('_', '')})\n")
        f.write("\n---\n\n")
        
        for filepath in sorted(issues.keys()):
            f.write(f"### {filepath}\n\n")
            f.write("| Ligne | Type Exception | Silencieux ? | Code / Extrait |\n")
            f.write("|---|---|---|---|\n")
            for issue in issues[filepath]:
                silent_str = "🛑 Oui" if issue["is_silent"] else "🟢 Non (log/raise présent)"
                type_str = f"`{issue['type']}`"
                code_str = f"`{issue['code'][:80]}`" if issue["code"] else "N/A"
                f.write(f"| {issue['line']} | {type_str} | {silent_str} | {code_str} |\n")
            f.write("\n")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    certus_dir = project_root / "certus"
    report_file = project_root / "exceptions_audit_report.md"
    
    print(f"Scanning directory: {certus_dir}...")
    issues = audit_exceptions(certus_dir)
    print(f"Found issues in {len(issues)} files. Generating report...")
    generate_report(issues, report_file)
    print(f"Report generated successfully at: {report_file}")
