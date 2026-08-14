"""Extraction exacte de la stratégie 36102 depuis les rapports."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

for p in sorted(ROOT.glob("reports/*bandpass*.json")):
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "strategies" in data:
            for s in data["strategies"]:
                if s.get("id") == 36102:
                    print(f"Fichier : {p.name}")
                    print(f"Stratégie 36102 : n_blocks={s.get('n_blocks')}, crash={s.get('crash')}, score={s.get('score')}")
                    if "blocks" in s:
                        print("Blocs :", s["blocks"])
                    break
    except Exception as e:
        pass
