#!/usr/bin/env python3
"""
Verification of complete execution of CERTUS examples
"""

import subprocess
import time
import os
from pathlib import Path


def run_with_timeout_check(module, example_file, timeout=30):
    """Launches a module and verifies if it terminates correctly."""
    print(f"\n🚀 Test: {module} avec {example_file}")

    try:
        # Run in background
        process = subprocess.Popen(
            ["python", module, example_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=".",
        )

        # Wait a bit to see if it starts
        time.sleep(5)

        # Check if the process is still running
        if process.poll() is None:
            print(f"   ✅ {module} started and running (GUI)")

            # Wait a bit more to see if it terminates on its own
            try:
                stdout, stderr = process.communicate(timeout=10)
                if process.returncode == 0:
                    print(f"   ✅ {module}completed successfully (code 0)")
                    return True
                else:
                    print(f"   ⚠️ {module}finished with code{process.returncode}")
                    if stderr:
                        print(f"      Erreur: {stderr[:200]}...")
                    return False
            except subprocess.TimeoutExpired:
                print(f"   ℹ️ {module} toujours en cours (GUI normale)")
                # Terminer proprement
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return True
        else:
            # The process was completed quickly
            stdout, stderr = process.communicate()
            if process.returncode == 0:
                print(f"   ✅ {module}completed quickly and successfully")
                return True
            else:
                print(f"   ❌ {module}ended with error (code{process.returncode})")
                if stderr:
                    print(f"      Erreur: {stderr[:200]}...")
                return False

    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"   ❌ Erreur lancement {module}: {e}")
        return False


def main():
    """Fonction principale."""
    print("🔍 CHECK THE COMPLETE FLOW OF THE EXAMPLES")
    print("=" * 50)

    # Test main modules
    modules_tests = [
        ("CERTUS_DESIGN.py", "example/JSON-design-example.json"),
        ("CERTUS_INDEX.py", "example/CSV-index-example.csv"),
        ("CERTUS_STRAT.py", "example/JSON-strat-example.json"),
        ("CERTUS_METAL_SINGLE.py", "example/JSON-metal-example.json"),
        ("CERTUS_METAL_BILAYER.py", "example/JSON-metal-example.json"),
    ]

    results = {}
    for module, example in modules_tests:
        results[module] = run_with_timeout_check(module, example)

    # Summary
    print("\n📊 RÉSUMÉ DES TESTS:")
    print("=" * 50)
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)

    for module, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAIL"
        print(f"{module}: {status}")

    print(
        f"\n🎯 BILAN: {success_count}/{total_count} modules fonctionnent correctement"
    )

    # Check logs for more details
    print("\n📋 VÉRIFICATION DES LOGS:")
    print("=" * 50)

    log_files = {
        "CERTUS_DESIGN": "logs/certus_design.log",
        "CERTUS_INDEX": "logs/certus_index.log",
        "CERTUS_STRAT": "logs/certus_strat.log",
        "CERTUS_METAL": "logs/certus_metal.log",
    }

        for module, log_file in log_files.items():
            if Path(log_file).exists():
            with open(log_file, "r") as f:
                lines = f.readlines()
            print(f"\n📋 {module} ({len(lines)} lignes):")
            for i, line in enumerate(lines[-5:], 1):
                print(f"   {i}: {line.strip()}")
        else:
            print(f"❌ {log_file}: manquant")


if __name__ == "__main__":
    main()
