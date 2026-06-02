import os

# 1. certus_index_spline_ui.py
filepath = r'certus\ui\certus_index_spline_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('    def _execute_smart_init_recall_best(self, state: _SmartInitState) -> str | None:'):
        # skip until 'return None'
        while not lines[i].strip() == 'return None':
            i += 1
        i += 1
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        continue
    new_lines.append(line)
    i += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("certus_index_spline_ui.py cleaned")

# 2. certus_index_ui.py
filepath = r'certus\ui\certus_index_ui.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.startswith('    def reattach_plot(self, plot_name: str) -> None:'):
        # skip until next def
        while i < len(lines):
            i += 1
            if lines[i].startswith('    def '):
                # go back to empty lines before def
                while lines[i-1].strip() == '':
                    i -= 1
                break
        continue
    new_lines.append(line)
    i += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("certus_index_ui.py cleaned")
