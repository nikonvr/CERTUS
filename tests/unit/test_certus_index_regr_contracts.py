from CERTUS_INDEX import CertusIndexApp
from CERTUS_RE import CertusREApp
from CERTUS_STRAT import _select_best_strat_result


def test_strat_best_result_prefers_positive_ranked_scores():
    items = [
        {"robustness_score": 0.0, "rmse": 0.0},
        {"robustness_score": 0.12, "rmse": 0.34},
        {"robustness_score": 0.09, "rmse": 0.11},
    ]
    best = _select_best_strat_result(items)
    assert best is not None
    assert float(best["robustness_score"]) == 0.12


def test_index_normalization_keeps_substrate_and_film_fields_separate():
    app = CertusIndexApp.__new__(CertusIndexApp)
    normalized = app._normalize_index_config(
        {
            "substratee_choice": "SiO2",
            "substrate_choice": "SiO2",
            "h_material": "HfO2",
            "l_material": "SiO2",
            "stack_string": "1,2,3",
        }
    )
    assert normalized["substrate"] == "SiO2"
    assert normalized["h_material_file"] == "HfO2"
    assert normalized["l_material_file"] == "SiO2"
    assert "substratee_choice" in normalized
    assert normalized["stack_string"] == "1,2,3"


def test_re_normalization_keeps_substrate_and_stack_terms_distinct():
    app = CertusREApp.__new__(CertusREApp)
    normalized = app._normalize_re_config(
        {
            "substratee_choice": "SiO2",
            "lambda_ref_nm": "550.0",
            "stack": ["H", "L", "H"],
        }
    )
    assert normalized["substrate_choice"] == "SiO2"
    assert normalized["l0"] == 550.0
    assert normalized["stack_string"] == "H,L,H"

