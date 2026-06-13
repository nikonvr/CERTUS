import sys
import subprocess
import os


def run_smoke_test(module_name, class_name):
    print(f"Testing {module_name} ({class_name})... ", end="", flush=True)

    # Python code to run in subprocess
    code = f"""
import sys
import os
from PyQt6.QtWidgets import QApplication

# Add current dir to path
sys.path.insert(0, os.getcwd())

# Mock certus_license to avoid activation popups
try:
    from {module_name} import {class_name}
    from certus.ui.certus_ui import init_certus_app
    
    app = QApplication(sys.argv)
    init_certus_app("{module_name.replace('.py', '')}", app=app)
    
    # Instantiate
    window = {class_name}()
    window.show()
    window.close()
    sys.exit(0)
except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""

    try:
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdout, stderr = process.communicate(timeout=30)

        if process.returncode == 0:
            print("PASSED")
            return True
        else:
            print("FAILED")
            print(f"Error in {module_name}:\n{stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("TIMEOUT (Assuming hanging initialization or blocking dialog)")
        process.kill()
        return False
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"ERROR: {str(e)}")
        return False


def main():
    modules = [
        ("CERTUS_HUB", "CertusHub"),
        ("CERTUS_STRAT", "CertusStratApp"),
        ("CERTUS_DESIGN", "CertusDesignApp"),
        ("CERTUS_INDEX", "CertusIndexApp"),
        ("CERTUS_METAL_SINGLE", "CertusMetalSingleApp"),
        ("CERTUS_METAL_BILAYER", "CertusMetalBilayerApp"),
    ]

    all_passed = True
    for mod, cls in modules:
        if not run_smoke_test(mod, cls):
            all_passed = False

    if all_passed:
        print("\nAll modules launched successfully.")
        sys.exit(0)
    else:
        print("\nSome modules failed the smoke test.")
        sys.exit(1)


if __name__ == "__main__":
    main()
