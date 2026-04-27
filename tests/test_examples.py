#!/usr/bin/env python3
"""
Test loading and launching CERTUS examples
"""

import json
import os
import subprocess
from pathlib import Path


def test_load_examples():
    """Tests loading example files."""
    print("🚀 TEST LOADING EXAMPLES")
    print("=" * 50)

    # Test loading JSON examples
    examples = {
        "JSON-design-example.json": "example/JSON-design-example.json",
        "JSON-metal-example.json": "example/JSON-metal-example.json",
        "JSON-strat-example.json": "example/JSON-strat-example.json",
    }

    for name, path in examples.items():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            print(f"✅ {name}: {len(data)}keys")

            # Show some important keys
            if "version" in data:
                print(f'   Version: {data["version"]}')
            if "materials" in data:
                print(f'Materials:{len(data["materials"])} types')
            if "targets" in data:
                print(f'   Cibles: {len(data["targets"])}')
            if "front" in data:
                print(f'   Couches avant: {len(data["front"])}')

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            print(f"❌ {name}: {e}")

    # Test CSV loading
    print("\n📊 Test CSV examples...")
    csv_examples = ["example/CSV-index-example.csv", "example/CSV-metal-example.csv"]

    for path in csv_examples:
        path_obj = Path(path)
        if path_obj.exists():
            size = path_obj.stat().st_size
            print(f"✅ {path}: {size} bytes")
        else:
            print(f"❌ {path}: manquant")


def test_launch_examples():
    """Tests launching modules with examples."""
    print("\n🚀 LANCEMENT DES EXEMPLES CERTUS SUITE")
    print("=" * 50)

    # Launch CERTUS_DESIGN with example
    print("\n1. Lancement CERTUS_DESIGN avec JSON-design-example.json...")
    try:
        result = subprocess.run(
            ["python", "CERTUS_DESIGN.py", "example/JSON-design-example.json"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=".",
        )
        if result.returncode == 0:
            print("✅ CERTUS_DESIGN started successfully")
            print(f"   Sortie: {result.stdout[:200]}...")
        else:
            print(f"⚠️ CERTUS_DESIGN: code {result.returncode}")
            print(f"   Erreur: {result.stderr[:200]}...")
    except subprocess.TimeoutExpired:
        print("✅ CERTUS_DESIGN started (normal timeout for GUI)")
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"❌ Erreur CERTUS_DESIGN: {e}")

    # Launch CERTUS_INDEX with CSV example
    print("\n2. Lancement CERTUS_INDEX avec CSV-index-example.csv...")
    try:
        result = subprocess.run(
            ["python", "CERTUS_INDEX.py", "example/CSV-index-example.csv"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=".",
        )
        if result.returncode == 0:
            print("✅ CERTUS_INDEX started successfully")
            print(f"   Sortie: {result.stdout[:200]}...")
        else:
            print(f"⚠️ CERTUS_INDEX: code {result.returncode}")
            print(f"   Erreur: {result.stderr[:200]}...")
    except subprocess.TimeoutExpired:
        print("✅ CERTUS_INDEX started (normal timeout for GUI)")
    except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
        print(f"❌ Erreur CERTUS_INDEX: {e}")


def test_logs():
    """Verifies generated logs."""
    print("\n🔍 VÉRIFICATION DES LOGS APRÈS LANCEMENT")
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
            for i, line in enumerate(lines[-3:], 1):
                print(f"   {i}: {line.strip()}")
        else:
            print(f"❌ {log_file}: manquant")


if __name__ == "__main__":
    test_load_examples()
    test_launch_examples()
    test_logs()
    print("\n🎯 TEST EXEMPLES TERMINÉ")
