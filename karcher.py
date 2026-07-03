import ast
from pathlib import Path

TARGETS = {
    "certus_tmm_substrate.py": [
        "calculate_bare_substrate_R",
        "calculate_bare_substrate_RT",
        "calculate_single_interface_R",
        "calculate_bare_substrate_R_absorbing",
        "calculate_bare_substrate_T_absorbing"
    ],
    "certus_tmm_single_layer.py": [
        "calculate_RT_single_layer_single",
        "calculate_reflection_array",
        "calculate_transmission_single",
        "calculate_reflection_single",
        "calculate_transmission_array",
        "calculate_RT_single_layer_backside_array",
        "batch_single_layer_T_mse",
        "batch_single_layer_RT_mse",
        "_calculate_RT_absorbing_sub_single",
        "calculate_RT_single_layer_absorbing_substrate_array"
    ],
    "certus_tmm_matrix.py": [
        "compute_complex_phase_components",
        "compute_TMM_single_point_k0",
        "compute_TMM_single_point_k0_exact",
        "calculate_RT_with_backside_fused",
        "calculate_RT_vectorized_real",
        "calculate_RT_no_backside",
        "calc_spectrum_front",
        "calc_spectrum_full",
        "calc_spectrum_full_exact",
        "calc_spectrum_front_wrapper",
        "calc_spectrum_full_wrapper",
        "calc_spectrum_full_exact_wrapper"
    ],
    "certus_tmm_backside.py": [
        "_apply_exact_backside_generic",
        "apply_exact_backside_combination"
    ],
    "certus_tmm_oblique.py": [
        "_calc_spectrum_oblique_parallel",
        "calc_spectrum_oblique_vectorized",
        "calc_spectrum_oblique_backside_vectorized",
        "_oblique_stack_rt_single",
        "oblique_front_char_matrix_single",
        "oblique_front_rt_from_char_matrix_nsub_real",
        "calc_spectrum_full_oblique_exact"
    ],
    "certus_tmm_hl.py": [
        "_calculate_RT_HL_core",
        "calculate_RT_vectorized_real_HL"
    ]
}

def clean_file(filename: str):
    p = Path("certus/physics") / filename
    if not p.exists():
        return
        
    with open(p, "r", encoding="utf-8") as f:
        source = f.read()
        
    tree = ast.parse(source)
    lines = source.splitlines()
    
    allowed = TARGETS[filename]
    
    # We want to find line ranges to delete
    # also we want to delete comments immediately preceding the deleted functions
    to_delete = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name not in allowed:
                # mark lines for deletion
                # node.lineno is 1-indexed
                start = node.lineno - 1
                
                # Check for decorators
                if node.decorator_list:
                    start = node.decorator_list[0].lineno - 1
                    
                # Walk back to include consecutive comments/empty lines before it
                while start > 0:
                    prev_line = lines[start - 1].strip()
                    if prev_line.startswith("#") or prev_line == "":
                        start -= 1
                    else:
                        break

                end = node.end_lineno - 1
                for i in range(start, end + 1):
                    to_delete.add(i)

    if not to_delete:
        print(f"{filename} had no functions to delete.")
        return

    new_lines = []
    for i, line in enumerate(lines):
        if i not in to_delete:
            new_lines.append(line)
            
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
        
    print(f"Cleaned {filename}. Deleted {len(to_delete)} lines.")

def main():
    for f in TARGETS.keys():
        clean_file(f)
        
if __name__ == "__main__":
    main()
