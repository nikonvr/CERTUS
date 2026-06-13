from pathlib import Path

def get_class_bounds(lines, class_name):
    start = -1
    end = -1
    for i, line in enumerate(lines):
        if line.startswith(f"class {class_name}") or line.startswith(f"@dataclass\nclass {class_name}") or (line.startswith("@dataclass") and i+1 < len(lines) and lines[i+1].startswith(f"class {class_name}")):
            if line.startswith("@dataclass"):
                start = i
            elif i > 0 and lines[i-1].startswith("@dataclass"):
                start = i - 1
            else:
                start = i
                
            # Find end
            j = start + 1
            while j < len(lines):
                if lines[j].startswith("class ") or lines[j].startswith("def ") or lines[j].startswith("@"):
                    if not lines[j].startswith("    "): # not indented
                        end = j - 1
                        break
                j += 1
            if end == -1: end = len(lines) - 1
            break
    return start, end

lines = Path('certus/spline/spline_profile_corridors.py').read_text(encoding='utf-8').splitlines()

s, e = get_class_bounds(lines, "ProfileCorridorConfig")
print(f"ProfileCorridorConfig: {s} to {e}")

s, e = get_class_bounds(lines, "RegularGridProfileContext")
print(f"RegularGridProfileContext: {s} to {e}")

s, e = get_class_bounds(lines, "CorridorContextBuilder")
print(f"CorridorContextBuilder: {s} to {e}")

