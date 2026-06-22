import ast

with open("old_ui.py", "r", encoding="utf-16") as f:
    code = f.read()

tree = ast.parse(code)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_compute_n_results":
        func_code = ast.unparse(node)
        func_code = func_code.replace('self.progress_widget.update(', 'self.view.update_progress(')
        func_code = func_code.replace('self._is_cancel_requested()', 'self.view.is_cancel_requested()')
        
        with open("compute_extracted.py", "w", encoding="utf-8") as out:
            out.write(func_code)
        break
