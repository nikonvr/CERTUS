"""Adapt final native result metadata to the archived article plotting schema."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "pour_article"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def peaks(analysis: dict, fields: list[dict]) -> list[dict]:
    return [
        {
            "peak_lambda_nm": peak["peak_wavelength_nm"],
            "peak_height": peak["height"],
            "pole_fwhm_nm": peak["width_nm"],
            "e2max_at_this_peak": next(
                (field["e2max_at_this_peak"] for field in fields
                 if abs(field["wavelength_nm"] - peak["peak_wavelength_nm"]) < 1e-7),
                None,
            ),
        }
        for peak in analysis["charged_peaks"]
    ]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    charged = ROOT / "pilote_natif_109_v3"
    nominal = ROOT / "pilote_natif_109_temoin_v3"
    source = ROOT.parent / "A2_preparation_calculs_2026-11-05/pilote_109/initial_design.json"
    result = read(charged / "native_result.json")
    summary = read(charged / "summary.json")
    shutil.copyfile(source, OUT / "initial_design.json")
    shutil.copyfile(charged / "height_rounds.csv", OUT / "height_rounds.csv")
    shutil.copyfile(nominal / "nominal_rounds.csv", OUT / "nominal_rounds.csv")
    before = {"charged_peaks": peaks(result["initial"], []), "counts": summary["counts_before"]}
    after = {
        "charged_peaks": peaks(result["final"], summary["fields_at_charged_peaks"]),
        "counts": summary["counts_after"],
        "source": "native CERTUS backend v3, stationary real maxima",
    }
    converted = {
        "arms": {
            "height": {"selected_state": summary["selected_state"], "audit": after},
            "nominal": {"selected_state": read(nominal / "summary.json")["selected_state"]},
        },
        "sources": [str(charged), str(nominal)],
        "conversion": "Metadata and file copies only; no optical calculation or optimization.",
    }
    for name, value in (("before.json", before), ("summary.json", converted)):
        data = json.dumps(value, indent=2) + "\n"
        (OUT / name).write_text(data, encoding="utf-8")
        assert (OUT / name).read_text(encoding="utf-8") == data
    print("ARTICLE_NATIVE_INPUTS=GO: final v3 charged and nominal runs")


if __name__ == "__main__":
    main()
