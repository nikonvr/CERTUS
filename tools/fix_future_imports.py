from pathlib import Path

ui_dir = Path('certus/spline')
for f in ui_dir.glob('spline_pipeline_*.py'):
    lines = f.read_text(encoding='utf-8').split('\n')
    has_future = False
    new_lines = []
    
    for line in lines:
        if "from __future__ import annotations" in line:
            has_future = True
        else:
            new_lines.append(line)
            
    if has_future:
        final_content = "from __future__ import annotations\n" + '\n'.join(new_lines)
        f.write_text(final_content, encoding='utf-8')
        print(f"Fixed {f.name}")

# Also fix spline_pipeline.py if needed
f = ui_dir / 'spline_pipeline.py'
lines = f.read_text(encoding='utf-8').split('\n')
has_future = False
new_lines = []
for line in lines:
    if "from __future__ import annotations" in line:
        has_future = True
    else:
        new_lines.append(line)
if has_future:
    final_content = "from __future__ import annotations\n" + '\n'.join(new_lines)
    f.write_text(final_content, encoding='utf-8')
    print(f"Fixed {f.name}")
