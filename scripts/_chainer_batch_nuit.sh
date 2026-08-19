#!/usr/bin/env bash
# Attend la fin du batch « voie de garage », puis enchaine le batch de nuit.
# 🔴 « Une mesure, une machine » (§11-5) : on n'empile pas deux campagnes sur les memes coeurs.
set -u
cd /c/certus || exit 1
SORTIE="$1"
until grep -q "BATCH TERMINE" "$SORTIE" 2>/dev/null; do sleep 60; done
echo "=== batch voie-de-garage termine, enchainement ==="
grep -E "^BILAN|^  (OK|ECHEC)" "$SORTIE" | tail -6
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 /c/envs/certus/Scripts/python.exe scripts/batch_nuit_2026-08-19.py
echo "BATCH NUIT TERMINE code=$?"
