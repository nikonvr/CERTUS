"""L'ORCHESTRATEUR MULTI-REALISATION -- et les trois regles qu'il ne doit jamais enfreindre.

WHY THIS EXISTS. `scripts/orchestre_multigraine.py` automatise ce qui a ete fait a la main le
2026-08-22 : rejouer la meme recherche sur K graines, unir ce qu'elles trouvent, renoter. La
mesure qui le justifie, sept graines NUES sur `r75x2` a 2 nm :

    42 -> 0/1617     77 -> 547/2231 ✅     101 -> 0/1630     202 -> 0/1646
   303 -> 0/1680    404 -> 372/2016 ✅     505 -> 311/1995 ✅

Automatiser une methode, c'est aussi automatiser ses pieges. Les trois qui suivent ont chacun
coute quelque chose de reel dans ce depot, et chacun est epingle ici.

    1. NOTER SUR UNE GRAINE QUI A SERVI A TROUVER -- la malediction du vainqueur, mesuree a
       +12,9 % le 2026-08-15. Un score faux de 13 % qui a l'air juste.
    2. COMPARER DES SCORES DE REALISATIONS DIFFERENTES -- interdit par la regle d'or du
       multiseed, et c'est pourquoi l'union se fait en TOURNIQUET et non par tri global.
    3. TRONQUER EN SILENCE -- une union plafonnee sans le dire se lit comme « on a tout
       couvert ».

Chaque test de forme est double d'un CONTROLE NEGATIF quand il en existe un : un test qui ne
peut pas echouer ne prouve rien.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import orchestre_multigraine as OM  # noqa: E402


def _strat(score: float, crash: float, *blocs: tuple[int, int, float], origine: str = "ELITE") -> dict:
    return {
        "score": score,
        "crash_rate": crash,
        "origine": origine,
        "n_blocs": len(blocs),
        "blocs": [{"start": a, "end": b, "wavelength": w} for a, b, w in blocs],
    }


# ---------------------------------------------------------------------------
# 1. LE BUDGET DE TEMPS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("texte", "minutes"),
    [("2h", 120.0), ("90m", 90.0), ("90min", 90.0), ("1h30", 90.0), ("1h30m", 90.0),
     ("nuit", 600.0), ("45", 45.0), ("0,5h", 30.0), (" 3H ", 180.0)],
)
def test_le_budget_se_lit_comme_un_humain_l_ecrit(texte: str, minutes: float) -> None:
    assert OM._duree_en_minutes(texte) == pytest.approx(minutes)


@pytest.mark.parametrize("texte", ["", "demain", "2 heures", "h", "2j"])
def test_un_budget_illisible_LEVE_au_lieu_de_deviner(texte: str) -> None:
    """🔴 Deviner un budget serait pire que refuser : « 2j » silencieusement lu 2 minutes
    rendrait « aucune graine ne trouve » alors que rien n'aurait tourne."""
    with pytest.raises(argparse.ArgumentTypeError):
        OM._duree_en_minutes(texte)


# ---------------------------------------------------------------------------
# 2. L'UNION EN TOURNIQUET -- et le controle negatif qui montre qu'elle sert
# ---------------------------------------------------------------------------

def test_le_tourniquet_prend_le_meilleur_de_CHAQUE_graine_avant_le_second_d_aucune() -> None:
    par_graine = {
        101: [_strat(0.10, 0.01, (0, 5, 500.0)), _strat(0.11, 0.01, (0, 5, 501.0))],
        202: [_strat(0.12, 0.01, (0, 5, 502.0)), _strat(0.13, 0.01, (0, 5, 503.0))],
    }
    plans, ecartes = OM.unir_en_tourniquet(par_graine, plafond=99)
    assert ecartes == 0
    assert [p["nom"].split("_")[0] for p in plans] == ["s101", "s202", "s101", "s202"]


def test_controle_negatif_un_TRI_GLOBAL_affamerait_une_graine() -> None:
    """🔴 LE TEST QUI PROUVE QUE LE TOURNIQUET N'EST PAS DECORATIF.

    Sous plafond, un tri global par score garderait les DEUX plans de la graine 101 et
    ZERO de la 202 -- alors que ces scores viennent de realisations differentes et ne sont
    pas comparables. Le tourniquet garde une de chaque.
    """
    par_graine = {
        101: [_strat(0.10, 0.01, (0, 5, 500.0)), _strat(0.11, 0.01, (0, 5, 501.0))],
        202: [_strat(0.12, 0.01, (0, 5, 502.0)), _strat(0.13, 0.01, (0, 5, 503.0))],
    }
    plans, ecartes = OM.unir_en_tourniquet(par_graine, plafond=2)
    graines_gardees = {p["nom"].split("_")[0] for p in plans}
    assert graines_gardees == {"s101", "s202"}, "une graine a ete affamee -- c'est le tri global"
    assert ecartes == 2

    tri_global = sorted(
        [(g, s) for g, lst in par_graine.items() for s in lst], key=lambda x: x[1]["score"]
    )[:2]
    assert {g for g, _ in tri_global} == {101}, "le controle negatif ne reproduit plus la faute"


def test_l_union_deduplique_par_PLAN_et_pas_par_identifiant() -> None:
    """Mesure §24-51 : 21 identifiants sur 79 portent des plans DIFFERENTS."""
    meme_plan = (0, 8, 450.0), (8, 75, 610.0)
    par_graine = {
        101: [_strat(0.10, 0.01, *meme_plan)],
        202: [_strat(0.12, 0.01, *meme_plan)],  # meme plan, autre graine -> UNE seule entree
        303: [_strat(0.11, 0.01, (0, 8, 450.0), (8, 75, 611.0))],  # 1 nm d'ecart -> distincte
    }
    plans, _ = OM.unir_en_tourniquet(par_graine, plafond=99)
    assert len(plans) == 2


def test_un_plan_VIDE_n_entre_jamais_dans_l_union() -> None:
    """Un artefact d'avant le 2026-08-20 porte `blocs: null`, et une rampe au plan vide
    ressemble a un resultat. Elle est refusee."""
    par_graine = {101: [{"score": 0.1, "crash_rate": 0.01, "n_blocs": 0, "blocs": []}]}
    plans, _ = OM.unir_en_tourniquet(par_graine, plafond=99)
    assert plans == []


def test_le_plafond_COMPTE_ce_qu_il_ecarte() -> None:
    """🔴 Une troncature silencieuse se lit comme « on a tout couvert »."""
    par_graine = {101: [_strat(0.1 + i / 100, 0.01, (0, 5, 500.0 + i)) for i in range(7)]}
    plans, ecartes = OM.unir_en_tourniquet(par_graine, plafond=3)
    assert len(plans) == 3
    assert ecartes == 4


# ---------------------------------------------------------------------------
# 3. LA GARDE ANTI-MALEDICTION DU VAINQUEUR -- elle REFUSE, elle n'avertit pas
# ---------------------------------------------------------------------------

def test_noter_sur_une_graine_de_generation_est_REFUSE(capsys: pytest.CaptureFixture) -> None:
    code = OM.main(["r75x2", "--graines", "101", "202", "--graine-notation", "202"])
    assert code == 2, "un simple avertissement ne suffit pas : le score serait faux de +12,9 %"
    assert "malediction" in capsys.readouterr().out.lower()


def test_une_graine_de_notation_disjointe_passe_la_garde() -> None:
    """Controle negatif de la garde : elle ne doit pas refuser tout le monde."""
    code = OM.main(["r75x2", "--graines", "101", "202", "--graine-notation", "42", "--dry-run"])
    assert code == 0


def test_l_echelle_par_defaut_ne_contient_PAS_la_graine_de_notation() -> None:
    """La disjonction par defaut doit etre vraie par CONSTRUCTION, pas par chance."""
    assert OM.GRAINE_NOTATION_DEFAUT not in OM.ECHELLE_GRAINES


def test_l_echelle_par_defaut_n_a_aucun_doublon() -> None:
    assert len(set(OM.ECHELLE_GRAINES)) == len(OM.ECHELLE_GRAINES)


# ---------------------------------------------------------------------------
# 4. CE QUI COMPTE COMME UNE MESURE
# ---------------------------------------------------------------------------

def _ecrire(tmp: Path, **champs) -> Path:
    f = tmp / "a.json"
    f.write_text(json.dumps(champs), encoding="utf-8")
    return f


def test_un_artefact_sans_verdict_OK_n_est_PAS_une_mesure(tmp_path: Path) -> None:
    """Les quatre mesures perdues du 2026-08-22 portaient toutes un artefact."""
    assert OM._lire_artefact(_ecrire(tmp_path, verdict="TIMEOUT", strategies=[{"a": 1}])) is None


def test_un_artefact_SANS_STRATEGIE_n_est_PAS_une_mesure(tmp_path: Path) -> None:
    assert OM._lire_artefact(_ecrire(tmp_path, verdict="OK", strategies=[])) is None


def test_un_artefact_complet_EST_une_mesure(tmp_path: Path) -> None:
    """Controle negatif : le lecteur ne doit pas tout rejeter."""
    assert OM._lire_artefact(_ecrire(tmp_path, verdict="OK", strategies=[{"a": 1}])) is not None


def test_un_fichier_absent_ou_illisible_rend_None(tmp_path: Path) -> None:
    assert OM._lire_artefact(tmp_path / "nexistepas.json") is None
    casse = tmp_path / "casse.json"
    casse.write_text("{ pas du json", encoding="utf-8")
    assert OM._lire_artefact(casse) is None


# ---------------------------------------------------------------------------
# 4bis. LA DECISION D'ARRET -- 👤 doit pouvoir couper des qu'un SEEL lui convient
# ---------------------------------------------------------------------------

def _motif(tmp: Path, **kw) -> str:
    base = {"drapeau": tmp / "FINALISER", "seel_cible": None, "meilleur_seel": None,
            "succes": False, "objectif": "meilleur"}
    base.update(kw)
    return OM.motif_finalisation(**base)


def test_sans_raison_on_continue(tmp_path: Path) -> None:
    assert _motif(tmp_path) == ""


def test_le_fichier_FINALISER_arrete(tmp_path: Path) -> None:
    """🔑 Le vrai bouton : il marche depuis une AUTRE fenetre, donc une campagne de nuit
    detachee du terminal reste interruptible."""
    (tmp_path / "FINALISER").write_text("", encoding="utf-8")
    assert "utilisateur" in _motif(tmp_path)


def test_la_cible_de_SEEL_arrete_quand_elle_est_ATTEINTE(tmp_path: Path) -> None:
    assert "cible atteinte" in _motif(tmp_path, seel_cible=0.58, meilleur_seel=0.5599)


def test_la_cible_de_SEEL_n_arrete_PAS_quand_elle_ne_l_est_pas(tmp_path: Path) -> None:
    """Controle negatif : 0,6112 est le SEEL de la graine 505, au-dessus d'une cible a 0,58."""
    assert _motif(tmp_path, seel_cible=0.58, meilleur_seel=0.6112) == ""


def test_la_cible_est_inclusive(tmp_path: Path) -> None:
    """« un SEEL qui lui convient » : atteindre la cible exactement, c'est la convenir."""
    assert _motif(tmp_path, seel_cible=0.5599, meilleur_seel=0.5599) != ""


def test_une_cible_ABSENTE_ne_declenche_jamais(tmp_path: Path) -> None:
    assert _motif(tmp_path, seel_cible=None, meilleur_seel=0.0001) == ""


def test_l_objectif_premier_arrete_au_premier_succes(tmp_path: Path) -> None:
    assert "premier" in _motif(tmp_path, succes=True, objectif="premier")


def test_l_objectif_meilleur_NE_s_arrete_PAS_au_premier_succes(tmp_path: Path) -> None:
    """C'est toute la difference entre les deux modes : les trois graines qui trouvent
    s'etalent de 0,5599 a 0,6112, soit 9,2 % -- s'arreter au premier peut couter cela."""
    assert _motif(tmp_path, succes=True, objectif="meilleur") == ""


def test_la_demande_de_l_utilisateur_passe_DEVANT_la_cible(tmp_path: Path) -> None:
    """Elle vient de l'exterieur ; il doit la voir reconnue plutot qu'un autre motif."""
    (tmp_path / "FINALISER").write_text("", encoding="utf-8")
    assert "utilisateur" in _motif(tmp_path, seel_cible=0.9, meilleur_seel=0.5)


# ---------------------------------------------------------------------------
# 5. RESOUDRE L'ARTEFACT -- le defaut n° 2 de `generer_rampes`, et son symetrique
# ---------------------------------------------------------------------------

@pytest.fixture
def reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    monkeypatch.setattr(OM, "RACINE", tmp_path)
    return d


def _touche(d: Path, nom: str, mtime: float) -> Path:
    f = d / nom
    f.write_text("{}", encoding="utf-8")
    import os

    os.utime(f, (mtime, mtime))
    return f


def test_un_artefact_HORODATE_est_trouve(reports: Path) -> None:
    """🔴 Le defaut n° 2 : la mesure a plein budget de la graine 101 vit sous
    `..._s101_20260822_102742.json`. Un lecteur par nom canonique la rate et refait 45 min."""
    _touche(reports, "blocs_vs_plantage_r75x2_deep_s101_20260822_102742.json", 1000)
    assert OM._resoudre_artefact("r75x2", "deep", 101) is not None


def test_un_artefact_ETIQUETE_n_est_JAMAIS_pris_pour_la_reference(reports: Path) -> None:
    """🔴 La faute symetrique, et elle est pire : `..._s101_mcreduit4x.json` est un run a
    BUDGET REDUIT. Le prendre pour la mesure de reference melangerait deux configurations."""
    _touche(reports, "blocs_vs_plantage_r75x2_deep_s101_mcreduit4x.json", 1000)
    assert OM._resoudre_artefact("r75x2", "deep", 101) is None
    assert OM._resoudre_artefact("r75x2", "deep", 101, tag="mcreduit4x") is not None


def test_entre_deux_homonymes_on_prend_le_PLUS_RECENT(reports: Path) -> None:
    """Defaut n° 2 dans sa seconde moitie : resoudre au hasard prenait le PLUS ANCIEN."""
    _touche(reports, "blocs_vs_plantage_r75x2_deep_s101.json", 1000)
    recent = _touche(reports, "blocs_vs_plantage_r75x2_deep_s101_20260822_102742.json", 9000)
    assert OM._resoudre_artefact("r75x2", "deep", 101) == recent


def test_une_graine_ne_ramasse_pas_celle_dont_elle_est_le_PREFIXE(reports: Path) -> None:
    """`s101*` attrape `s1011`. Le reste « 1 » n'est pas un horodatage : rejete."""
    _touche(reports, "blocs_vs_plantage_r75x2_deep_s1011.json", 1000)
    assert OM._resoudre_artefact("r75x2", "deep", 101) is None
    assert OM._resoudre_artefact("r75x2", "deep", 1011) is not None


def test_un_autre_MODE_ou_un_autre_COMPOSANT_ne_repond_pas(reports: Path) -> None:
    _touche(reports, "blocs_vs_plantage_r75x2_premium_s101.json", 1000)
    _touche(reports, "blocs_vs_plantage_r75x2-2nm_deep_s101.json", 1000)
    assert OM._resoudre_artefact("r75x2", "deep", 101) is None


def test_la_tolerance_de_plantage_est_celle_du_projet() -> None:
    """5 %, et `crash_rate` est DEJA le maximum sur les trois niveaux de bruit (§3 point 7)."""
    assert OM.TOLERANCE_PLANTAGE == 0.05
    art = {"strategies": [_strat(0.1, 0.049, (0, 5, 500.0)), _strat(0.2, 0.051, (0, 5, 501.0))]}
    assert len(OM._deposables(art)) == 1


# ---------------------------------------------------------------------------
# 6. L'ECART PROVISOIRE -> DEFINITIF NE DOIT PAS SE PERDRE A LA REPRISE
# ---------------------------------------------------------------------------

def test_le_meilleur_SEEL_est_initialise_AVANT_le_balayage_de_reprise() -> None:
    """🔴 CE TEST GARDE UNE REPARATION DU 2026-08-22, TROUVEE PAR UNE VRAIE CAMPAGNE.

    `meilleur_seel` vivait dans la boucle de lancement. Une campagne dont TOUTES les graines
    portaient deja un artefact -- le cas de REPRISE, le plus frequent -- le laissait vide : le
    programme allait donc jusqu'a la notation finale sans jamais pouvoir publier l'ecart
    provisoire -> definitif. Or cet ecart EST la mesure du canal de malediction du vainqueur,
    +12,9 % le 2026-08-15 et +0,55 % le 2026-08-22. Le sauter en silence, c'est cesser de
    surveiller la seule chose qui rende un score publie faux sans que rien ne le dise.

    La validation de bout en bout du 2026-08-22 est tombee exactement dans ce cas : deux
    graines deja mesurees, resultat citable 0,5642 nm, et AUCUN ecart publie.
    """
    src = (Path(OM.__file__)).read_text(encoding="utf-8")
    i_init = src.index("meilleur_seel: float | None = None")
    i_reprise = src.index("--- Reprise")
    i_boucle = src.index("--- La boucle")
    assert i_reprise < i_init < i_boucle, (
        "meilleur_seel doit etre initialise ENTRE l'en-tete de reprise et la boucle : "
        "sinon une campagne entierement reprise ne publie aucun ecart."
    )
    assert src.count("meilleur_seel: float | None = None") == 1, (
        "deux initialisations : la seconde ecraserait ce que le balayage de reprise a trouve"
    )


def test_le_balayage_de_reprise_MET_A_JOUR_le_meilleur_SEEL() -> None:
    """Controle de forme : la mise a jour doit vivre dans le balayage, pas seulement dans la
    boucle. Sans elle, hisser la variable ne servirait a rien."""
    src = (Path(OM.__file__)).read_text(encoding="utf-8")
    debut = src.index("--- Reprise")
    fin = src.index("--- La boucle")
    assert "seel_deja" in src[debut:fin], (
        "le balayage de reprise ne met pas a jour meilleur_seel"
    )


# ---------------------------------------------------------------------------
# 7. LA BOUCLE PRINCIPALE -- que AUCUN test ne traversait
# ---------------------------------------------------------------------------

def _sans_vrai_lancement(monkeypatch, argv: list[str], tmp_path=None) -> int:
    """Traverse la boucle SANS lancer un seul calcul NI ecrire dans le vrai `reports/`.

    🔑 Indispensable depuis que « le premier lancement passe malgre le budget » : sans lui, un
    test unitaire declencherait un run de production de cinquante minutes.

    🔴 ET IL DEPLACE `RACINE`. 📏 Le 2026-08-23, ces tests avaient seme QUARANTE-NEUF dossiers
    `reports/orchestre_*` vides dans le depot. Un test qui salit l'endroit ou l'on cherche les
    mesures est un test qui coutera une lecture fausse un jour.
    """
    if tmp_path is not None:
        monkeypatch.setattr(OM, "RACINE", tmp_path)

    class _Faux:
        returncode = 0
        pid = 1

        def poll(self):
            return 0

        def wait(self):
            return 0

    def _faux(py, composant, mode, res, graine, journal, env_sup=None):
        f = _Faux()
        f._certus_journal = type("F", (), {"close": lambda self: None})()
        return f

    monkeypatch.setattr(OM, "_lancer", _faux)
    return OM.main(argv)

def test_la_BOUCLE_s_execute_reellement_au_moins_une_fois(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """🔴 CE TEST EXISTE PARCE QUE LA CAMPAGNE DU 2026-08-22 A PLANTE EN 0 MINUTE.

    Un renommage mecanique avait donne le MEME nom a la fonction `motif_finalisation` et a la
    variable locale qui retient son resultat. La variable masquait la fonction :

        TypeError: 'str' object is not callable

    🔑 ET AUCUN TEST NE L'A VU, POUR UNE RAISON QUI VAUT PLUS QUE LE BUG : tous passaient par
    `--dry-run`, qui rend la main AVANT la boucle. La boucle principale -- le coeur du
    programme -- n'etait traversee par rien. Quarante-deux tests verts, et le premier vrai
    lancement tombe a la premiere ligne.

    Ce test entre DANS la boucle sans lancer le moindre calcul : un budget d'une minute rend
    `_rentre()` faux, donc rien ne demarre, mais la ligne fautive est bien executee. Cout : une
    fraction de seconde.
    """
    # ⚠️ LE LANCEUR EST SIMULE, ET C'EST OBLIGATOIRE DEPUIS LE 2026-08-22. Ce test s'appuyait
    # sur un budget d'une minute pour que RIEN ne parte -- exactement le comportement repare
    # depuis (« un budget sous-estime doit quand meme lancer la premiere »). Sans simulation il
    # declencherait desormais un vrai run de cinquante minutes dans la suite unitaire.
    code = _sans_vrai_lancement(monkeypatch, [
        "r75x1.75", "--budget", "1", "--graines", "909", "--graine-notation", "42",
        "--duree-attendue", "60",
    ], tmp_path)
    # 1 = « aucune realisation n'a trouve » : le faux lanceur n'ecrit aucun artefact. Ce qui
    # compte est qu'on TRAVERSE la boucle sans exception.
    assert code == 1


def test_ce_qui_n_a_PAS_ete_essaye_faute_de_budget_se_DIT(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """🔴 Sans cette ligne, « 0 trouve » se lirait « ca ne marche pas » alors que la verite est
    « on n'a pas eu le temps ». Les deux menent a des decisions opposees.

    On donne QUATRE graines et un budget d'une minute : la premiere passe (garde du premier
    lancement), les autres non -- et le programme doit le DIRE.
    """
    lances: list[int] = []

    class _Faux:
        # 🔑 `returncode != 0` DELIBEREMENT : la duree REELLE n'est apprise que sur un run
        # REUSSI. Avec un faux run instantane et reussi, `duree_reelle` tomberait a 0,08 min
        # et le budget d'une minute autoriserait legitimement des dizaines de lancements --
        # le test ne testerait alors plus la garde, mais l'arithmetique. On garde donc la
        # duree ATTENDUE de 60 min, qui est le cas reel.
        returncode = 1
        pid = 1

        def poll(self):
            return 1

    def _faux(py, composant, mode, res, graine, journal, env_sup=None):
        lances.append(int(graine))
        f = _Faux()
        f._certus_journal = type("F", (), {"close": lambda self: None})()
        return f

    monkeypatch.setattr(OM, "_lancer", _faux)
    monkeypatch.setattr(OM, "RACINE", tmp_path)  # ne pas salir le vrai reports/
    OM.main(["r75x1.75", "--budget", "1", "--graines", "909", "1111", "1212", "1313",
             "--graine-notation", "42", "--duree-attendue", "60", "--slots", "1"])
    sortie = capsys.readouterr().out
    assert len(lances) < 4, f"le budget n'a borne personne : {lances}"
    assert "NON LANCEE" in sortie or "NON ESSAYEES" in sortie, (
        "ce qui n'a pas ete essaye n'est pas dit -- « 0 trouve » se lirait « ca ne marche pas »"
    )



def test_un_budget_SOUS_ESTIME_lance_quand_meme_la_premiere(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """🔴 CE TEST A COUTE UNE NUIT DE CALCUL, LE 2026-08-22.

    La campagne de 12 h n'a RIEN lance. Avec `--budget 1h` et une duree attendue de 60 min,
    `_rentre()` valait `0,001 + 60 <= 60` -- FAUX D'UN CHEVEU. Douze graines declarees « NON
    LANCEES », zero calcul, et un journal qui avait l'air parfaitement normal.

    🔑 Un budget sous-estime doit rendre UNE mesure et un depassement DIT, jamais zero mesure
    en silence. C'est le sens d'un budget : borner l'ambition, pas interdire d'essayer.

    Le lanceur est SIMULE : on teste la decision, pas le calcul. Sans cela ce test durerait
    cinquante minutes et personne ne le lancerait.
    """
    lances: list[int] = []

    class _Faux:
        returncode = 0
        pid = 4242

        def poll(self):
            return 0

        def wait(self):
            return 0

    def _faux_lancer(py, composant, mode, res, graine, journal, env_sup=None):
        lances.append(int(graine))
        f = _Faux()
        f._certus_journal = type("F", (), {"close": lambda self: None})()
        return f

    monkeypatch.setattr(OM, "_lancer", _faux_lancer)
    monkeypatch.setattr(OM, "RACINE", tmp_path)  # ne pas salir le vrai reports/
    # Budget d'UNE minute, duree attendue de SOIXANTE : le cas exact qui a echoue.
    OM.main(["r75x1.75", "--budget", "1", "--graines", "909", "--graine-notation", "42",
             "--duree-attendue", "60"])
    assert lances, (
        "aucun lancement avec un budget sous-estime -- c'est la panne du 2026-08-22 : "
        "douze graines « NON LANCEES » et zero calcul, en silence."
    )
    assert lances[0] == 909


def test_le_budget_borne_QUAND_MEME_les_lancements_suivants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Controle negatif de la reparation : la garde ne doit pas ouvrir les vannes.

    Une seule graine passe malgre le budget ; les suivantes sont refusees, sinon le budget ne
    bornerait plus rien.
    """
    lances: list[int] = []

    class _Faux:
        returncode = 1  # pas de mesure exploitable -> `fait` reste vide... mais `en_vol` non
        pid = 1

        def poll(self):
            return 1

    def _faux_lancer(py, composant, mode, res, graine, journal, env_sup=None):
        lances.append(int(graine))
        f = _Faux()
        f._certus_journal = type("F", (), {"close": lambda self: None})()
        return f

    monkeypatch.setattr(OM, "_lancer", _faux_lancer)
    monkeypatch.setattr(OM, "RACINE", tmp_path)  # ne pas salir le vrai reports/
    OM.main(["r75x1.75", "--budget", "1", "--graines", "909", "1111", "1212", "1313",
             "--graine-notation", "42", "--duree-attendue", "60", "--slots", "1"])
    assert len(lances) < 4, (
        f"le budget ne borne plus rien : {len(lances)} lancements sur 4 avec un budget d'une "
        f"minute"
    )


# ---------------------------------------------------------------------------
# 8. LE GARDE-FOU : une coupure n'agit que sur ce qui vient APRES elle
# ---------------------------------------------------------------------------

def _strat_amorce(premiere_negative: int, profondeur_pire: int = 60) -> dict:
    """Une strategie dont la marge `level` passe sous zero a `premiere_negative`."""
    lv = {str(i): 3.0 for i in range(0, premiere_negative)}
    lv[str(premiere_negative)] = -0.5
    lv[str(profondeur_pire)] = -1800.0
    return {"margin_by_layer": {"level": lv},
            "critical_layer": {"layer": profondeur_pire, "cause": "niveau d'arret hors d'atteinte"}}


def test_l_amorce_est_la_PREMIERE_marge_negative_pas_la_pire() -> None:
    """🔴 CETTE DISTINCTION A COUTE TROIS RUNS le 2026-08-23.

    Le champ `critical_layer` rapporte la marge la PIRE, donc la plus profonde -- mediane 57
    sur `r75x2`. En le lisant on croit le probleme profond et une coupure a 38 bien placee.
    📏 La PREMIERE marge negative est a la couche 6.
    """
    s = _strat_amorce(6, profondeur_pire=57)
    assert OM.amorce_defaillance([s]) == 6
    assert s["critical_layer"]["layer"] == 57, "le temoin du piege doit rester dans le test"


def test_l_amorce_est_la_MEDIANE_sur_la_population() -> None:
    lot = [_strat_amorce(4), _strat_amorce(6), _strat_amorce(30)]
    assert OM.amorce_defaillance(lot) == 6


def test_aucune_marge_negative_rend_None() -> None:
    assert OM.amorce_defaillance([{"margin_by_layer": {"level": {"3": 2.0}}}]) is None
    assert OM.amorce_defaillance([]) is None
    assert OM.amorce_defaillance([{}]) is None


def test_une_defaillance_EN_AMONT_de_toute_coupure_est_refusee() -> None:
    """📏 `r75x2` : amorce mediane couche 7, coupure la moins profonde a 4 temoins = couche 19.
    Verifie sur artefacts, plans APPARIES : 28 plans sur 29 ont un plantage INCHANGE avec
    coupure, et l'amorce ne bouge dans AUCUN des 80 cas."""
    peut, pourquoi = OM.multitemoin_peut_agir(75, 7, 4)
    assert peut is False
    assert "INUTILE PAR CONSTRUCTION" in pourquoi
    assert "couche 7" in pourquoi and "couche 19" in pourquoi


def test_le_cas_LIMITE_de_r75x0_5_est_refuse_lui_aussi() -> None:
    """⚠️ Amorce 17 contre une coupure a 19 : DEUX couches d'ecart. Le garde-fou refuse, et
    c'est le bon sens de l'erreur -- mais il dit combien de temoins il faudrait, pour qu'on
    puisse en decider."""
    peut, pourquoi = OM.multitemoin_peut_agir(75, 17, 4)
    assert peut is False
    assert "~5 temoins" in pourquoi or "5 temoins" in pourquoi


def test_controle_negatif_une_defaillance_PROFONDE_laisse_passer() -> None:
    """🔴 Un garde-fou qui refuse tout ne garde rien."""
    peut, pourquoi = OM.multitemoin_peut_agir(75, 45, 4)
    assert peut is True
    assert "peut l'atteindre" in pourquoi


def test_une_amorce_INCONNUE_ne_bloque_pas() -> None:
    """En l'absence de donnee, on n'invente pas un refus : on laisse essayer."""
    peut, _ = OM.multitemoin_peut_agir(75, None, 4)
    assert peut is True


def test_le_garde_fou_ne_dit_PAS_que_le_composant_est_infaisable() -> None:
    """🔑 Deux affirmations differentes, et `r75x2` le prouve : le meme empilement, la meme
    graine et la meme fente rendent 251 deposables des qu'on injecte des plans connus."""
    _, pourquoi = OM.multitemoin_peut_agir(75, 7, 4)
    assert "ne dit PAS que le composant est infaisable" in pourquoi
