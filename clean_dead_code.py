import os
from pathlib import Path

def remove_lines_with(filepath: Path, search_strings: list[str]):
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    modified = False
    for line in lines:
        if any(s in line for s in search_strings):
            modified = True
            continue
        new_lines.append(line)
        
    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Cleaned {filepath.name}")

def main():
    root = Path(".")
    
    # 1. Clean UI Spline Mixins
    for ui_file in (root / "certus" / "ui").glob("certus_index_spline_*.py"):
        remove_lines_with(ui_file, ["_RMSEPlotContext"])
        
    for spline_file in (root / "certus" / "spline").glob("*.py"):
        remove_lines_with(spline_file, ["_RMSEPlotContext"])

    # 2. _certus_physics_impl.py
    phys_impl = root / "certus" / "core" / "_certus_physics_impl.py"
    remove_lines_with(phys_impl, [
        "_spline_cache", 
        "compute_metal_bilayer_gradient_analytic", 
        "calculate_reflectance_bilayer_vectorized"
    ])
    
    # 3. certus_core.py
    c_core = root / "certus" / "core" / "certus_core.py"
    remove_lines_with(c_core, [
        "get_app_display_name",
        "get_app_full_name",
        "get_app_version"
    ])

    # 4. certus_re_solvers.py
    re_solv = root / "certus" / "core" / "certus_re_solvers.py"
    remove_lines_with(re_solv, [
        "_global_evaluate_p2_fd_derivative",
        "_phase4_aperture_slice"
    ])
    
    # 5. certus_substrate_index.py
    sub_ind = root / "certus" / "core" / "certus_substrate_index.py"
    remove_lines_with(sub_ind, [
        "_sellmeier_build_candidates",
        "_sellmeier_initial_context"
    ])
    
    # 6. certus_opt_kernels.py
    opt_k = root / "certus" / "physics" / "certus_opt_kernels.py"
    remove_lines_with(opt_k, [
        "calculate_reflectance_bilayer_vectorized",
        "compute_metal_bilayer_gradient_analytic"
    ])
    
    # 7. certus_ui.py
    c_ui = root / "certus" / "ui" / "certus_ui.py"
    remove_lines_with(c_ui, ["create_colored_label"])
    
    # 8. certus_strat_service.py
    strat_srv = root / "certus" / "utils" / "certus_strat_service.py"
    remove_lines_with(strat_srv, ["import certus_physics"])
    
    # 9. certus_design_workers.py
    dsgn_wrk = root / "certus" / "workers" / "certus_design_workers.py"
    remove_lines_with(dsgn_wrk, ["ColorOptimizationStrategy"])
    
if __name__ == "__main__":
    main()
