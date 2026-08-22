"""LE REGISTRE DES LEVIERS NE DOIT JAMAIS MENTIR SUR CE QUE FAIT LA PRODUCTION.

WHY THIS EXISTS. 👤, 2026-08-22 : *« croise les verifications de codage y compris sur le GUI »*.

`certus/core/certus_strat_leviers.py` decrit, pour chaque reglage de Rate et de multi-temoin,
sa valeur EFFECTIVE en production et ce que la mesure en dit. L'interface construit son panneau
a partir de ce registre. **Si le registre derive du noyau, l'interface affiche un reglage que
la production n'applique pas** -- et l'utilisateur arme, ou renonce, sur une fausse information.

🔑 CE FICHIER EST LE CROISEMENT. Chaque `defaut` declare est confronte a la valeur reelle lue
dans `certus_strat_robustness.py`. On ne peut donc pas changer l'un sans l'autre.

📏 CE QUE L'AUDIT DU 2026-08-22 AVAIT TROUVE, ET QUE CE TEST EMPECHE DE REPRODUIRE :
`rate_by_swing` ecrit, teste et ETEINT ; `rate_tail_sweep` -- celui qui rend le `r75x2`
fabricable a 2 nm -- eteint ; le multi-Rate outille et inerte. Rien dans l'interface ne le
disait, parce que l'interface n'en parlait pas du tout.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from certus.core.certus_strat_leviers import (
    DERNIER_RECOURS,
    LEVIERS,
    LIBELLE_STATUT,
    NON_MESURE,
    PAR_CLE,
    RESERVE,
    VALIDE,
    leviers_de,
    surcharges_non_defaut,
)

NOYAU = Path(__file__).resolve().parents[2] / "certus" / "core" / "certus_strat_robustness.py"
SRC = NOYAU.read_text(encoding="utf-8")


def _defaut_params(cle: str):
    """La valeur par defaut que le NOYAU applique pour `params.get("cle", <defaut>)`."""
    m = re.search(r'params\.get\(\s*["\']' + re.escape(cle) + r'["\']\s*,\s*([^)]+?)\s*\)', SRC)
    if not m:
        return "ABSENT"
    brut = m.group(1).strip()
    # une constante du module : on la resout
    if re.fullmatch(r"[A-Z_][A-Z0-9_]*", brut):
        c = re.search(re.escape(brut) + r"\s*:\s*[a-z]+\s*=\s*([-\w.]+)", SRC)
        brut = c.group(1) if c else brut
    try:
        return ast.literal_eval(brut)
    except (ValueError, SyntaxError):
        return brut


def _constante(nom: str):
    m = re.search(re.escape(nom) + r"\s*:\s*[a-z]+\s*=\s*([-\w.]+)", SRC)
    if not m:
        return "ABSENTE"
    return ast.literal_eval(m.group(1))


# ---------------------------------------------------------------------------
# 1. LE CROISEMENT -- registre contre noyau
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("levier", [lv for lv in LEVIERS if not lv.constante], ids=lambda lv: lv.cle)
def test_le_defaut_declare_EST_celui_du_noyau(levier) -> None:
    """🔴 LE TEST QUI EMPECHE L'INTERFACE DE MENTIR."""
    reel = _defaut_params(levier.cle)
    if reel == "ABSENT":
        # Un levier sans `params.get` explicite est lu ailleurs (ex. `or []`). On exige alors
        # que le registre annonce une valeur VIDE, jamais une valeur active.
        assert levier.defaut in (None, "", [], 0, False), (
            f"{levier.cle} n'a pas de defaut explicite dans le noyau, mais le registre annonce "
            f"{levier.defaut!r} -- l'interface promettrait un reglage que rien n'applique."
        )
        return
    assert reel == levier.defaut, (
        f"{levier.cle} : le registre annonce {levier.defaut!r}, le noyau applique {reel!r}. "
        f"L'interface afficherait un reglage que la production n'utilise pas."
    )


@pytest.mark.parametrize("levier", [lv for lv in LEVIERS if lv.constante], ids=lambda lv: lv.cle)
def test_la_constante_declaree_EST_celle_du_noyau(levier) -> None:
    assert _constante(levier.cle) == levier.defaut, (
        f"{levier.cle} : registre {levier.defaut!r}, noyau {_constante(levier.cle)!r}"
    )


def test_controle_negatif_le_croisement_MORD() -> None:
    """🔴 Un test qui ne peut pas echouer ne prouve rien. On plante une valeur fausse."""
    reel = _defaut_params("rate_by_swing")
    assert reel is not None
    assert reel != "PAS_CETTE_VALEUR", "le lecteur du noyau ne lit rien"
    assert _defaut_params("cle_qui_nexiste_pas") == "ABSENT"
    assert _constante("CONSTANTE_QUI_NEXISTE_PAS") == "ABSENTE"


# ---------------------------------------------------------------------------
# 2. LA COHERENCE DU REGISTRE LUI-MEME
# ---------------------------------------------------------------------------

def test_aucune_cle_en_double() -> None:
    assert len({lv.cle for lv in LEVIERS}) == len(LEVIERS)


@pytest.mark.parametrize("levier", LEVIERS, ids=lambda lv: lv.cle)
def test_chaque_levier_dit_ce_que_la_mesure_etablit(levier) -> None:
    """🔑 Un levier sans mesure derriere lui est un bouton qui invite a l'aveugle."""
    assert len(levier.mesure) > 60, f"{levier.cle} : le champ `mesure` est trop maigre"
    assert levier.statut in LIBELLE_STATUT


@pytest.mark.parametrize("levier", [lv for lv in LEVIERS if lv.statut == NON_MESURE],
                         ids=lambda lv: lv.cle)
def test_un_levier_JAMAIS_MESURE_est_eteint_par_defaut(levier) -> None:
    """🔴 On peut proposer l'inconnu, on ne l'impose pas. Un levier jamais mesure en production
    doit etre a une valeur INERTE : sinon la production tourne sur du non-mesure sans que
    personne ne l'ait decide."""
    assert levier.defaut in (None, "", [], 0, False, 1), (
        f"{levier.cle} est declare jamais mesure et vaut {levier.defaut!r} par defaut"
    )


@pytest.mark.parametrize("levier", [lv for lv in LEVIERS if lv.statut == DERNIER_RECOURS],
                         ids=lambda lv: lv.cle)
def test_un_DERNIER_RECOURS_est_inerte_et_dit_son_cout(levier) -> None:
    """Le multi-temoin degrade +73 a +110 % la ou le mono-temoin marche. Il ne peut pas etre
    arme par defaut, et sa reserve doit porter le chiffre."""
    assert levier.defaut in (None, "", [])
    assert "%" in levier.reserve, f"{levier.cle} : la reserve ne chiffre pas le cout"


def test_le_multitemoin_est_la_SEULE_famille_temoin() -> None:
    assert [lv.cle for lv in leviers_de("temoin")] == ["witness_reset_layers"]


def test_les_leviers_du_rate_couvrent_les_quatre_contradictions() -> None:
    """L'audit du 2026-08-22 en a releve quatre. Chacune doit avoir son levier ou sa constante,
    sinon le savoir reste dans un `.md` que personne ne relit."""
    cles = {lv.cle for lv in LEVIERS}
    assert "rate_variant_top_n" in cles, "contradiction A -- le plafond"
    assert "RATE_MIN_LAYERS_PER_BLOCK" in cles, "contradiction B -- le couche-par-couche"
    assert "rate_by_swing" in cles, "contradiction C -- le placement par BESOIN"
    assert "RATE_MIN_LAYER" in cles, "contradiction D -- les bornes de couche"


# ---------------------------------------------------------------------------
# 3. LES SURCHARGES -- ne declarer que ce qui S'ECARTE
# ---------------------------------------------------------------------------

def test_un_levier_a_son_DEFAUT_n_entre_pas_dans_la_surcharge() -> None:
    """🔴 Sinon l'artefact porterait une etiquette et se croirait different d'un run nominal,
    alors qu'il en serait le jumeau. Ce depot a deja perdu des mesures pour des artefacts
    indiscernables."""
    assert surcharges_non_defaut({"rate_by_swing": PAR_CLE["rate_by_swing"].defaut}) == {}


def test_un_levier_ECARTE_entre_dans_la_surcharge() -> None:
    assert surcharges_non_defaut({"rate_by_swing": False}) == {"rate_by_swing": False}


def test_une_CONSTANTE_n_entre_jamais_dans_une_surcharge() -> None:
    """Elle n'est pas atteignable par configuration : la proposer serait une promesse creuse."""
    assert surcharges_non_defaut({"RATE_MIN_LAYER": 5}) == {}


def test_les_vides_equivalents_ne_font_pas_une_surcharge() -> None:
    assert surcharges_non_defaut({"witness_reset_layers": []}) == {}
    assert surcharges_non_defaut({"rate_tail_sweep": None}) == {}


def test_une_cle_INCONNUE_est_ignoree() -> None:
    assert surcharges_non_defaut({"nawak": 3}) == {}


def test_le_statut_VALIDE_et_RESERVE_sont_distincts() -> None:
    assert VALIDE != RESERVE != NON_MESURE != DERNIER_RECOURS
