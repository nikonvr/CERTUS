"""L'ONGLET MULTI-REALISATION -- sa logique, testee SANS ouvrir de fenetre.

WHY THIS EXISTS, ET POURQUOI LA LOGIQUE EST HORS DU WIDGET.

Ce depot a deja mesure ce que coute un banc graphique : QApplication ramassee par le GC,
stdout detourne, dialogues modales, `_is_busy` mort. Une logique d'affichage enfermee dans un
widget ne se teste donc qu'au prix fort, et finit par ne plus se tester du tout.

`EtatMultigraine`, `resumer` et `construire_arguments` sont par consequent PURS et au niveau du
module. Le widget n'est qu'une vue par-dessus.

CE QUE CES TESTS PROTEGENT, ET CHAQUE POINT A COUTE QUELQUE CHOSE :

    1. LE MOT « PROVISOIRE » DOIT SURVIVRE. Le SEEL affiche pendant la campagne est mesure sur
       la graine qui l'a trouve. C'est sur lui que 👤 decide d'arreter -- il doit donc porter sa
       reserve. Le canal de malediction du vainqueur valait +12,9 % le 2026-08-15.
    2. CE QUI N'A PAS ETE ESSAYE DOIT SE VOIR. Sans cela, « 0 trouve » se lit « ca ne marche
       pas » alors que c'est « on n'a pas eu le temps ».
    3. UNE TRONCATURE SE DIT. 483 plans ecartes par le plafond lors du premier essai reel :
       muette, elle se lirait comme « on a tout couvert ».
    4. UN EVENEMENT INCONNU NE DOIT RIEN CASSER. Une interface qui tourne depuis six heures ne
       doit pas tomber parce que le script a gagne un evenement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import orchestre_multigraine as OM  # noqa: E402
from certus.ui.certus_strat_multigraine_ui import (  # noqa: E402
    BRUIT_DIFFERENCE_SEEL_PCT,
    EtatMultigraine,
    construire_arguments,
    lire_evenement,
    resumer,
)


def _etat(*evts: dict) -> EtatMultigraine:
    e = EtatMultigraine()
    for v in evts:
        e.appliquer(v)
    return e


# ---------------------------------------------------------------------------
# 1. LE FORMAT D'EVENEMENT -- ecriture et lecture doivent rester d'accord
# ---------------------------------------------------------------------------

def test_le_format_fait_un_aller_retour(capsys: pytest.CaptureFixture) -> None:
    """🔑 L'emetteur et le lecteur vivent dans le meme fichier pour ne pas deriver. Ce test
    l'epingle : si l'un change de prefixe, l'autre cesse de comprendre."""
    OM._evenements_armes = True
    try:
        OM._evt("finie", graine=404, seel=0.5599)
    finally:
        OM._evenements_armes = False
    ligne = capsys.readouterr().out.strip()
    assert lire_evenement(ligne) == {"evt": "finie", "graine": 404, "seel": 0.5599}


def test_une_ligne_ORDINAIRE_n_est_pas_un_evenement() -> None:
    """Controle negatif : les phrases humaines ne doivent pas etre lues comme des donnees."""
    assert lire_evenement("  ✅ graine 404 : 372 deposable(s)") is None
    assert lire_evenement("") is None


def test_un_evenement_MALFORME_rend_None_au_lieu_de_lever() -> None:
    assert lire_evenement(OM.PREFIXE_EVT + "{pas du json") is None
    assert lire_evenement(OM.PREFIXE_EVT + '{"sans": "cle evt"}') is None


def test_muet_par_defaut(capsys: pytest.CaptureFixture) -> None:
    """Sans `--evenements`, rien ne doit polluer la sortie humaine."""
    OM._evt("finie", graine=1)
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# 2. LA MACHINE A ETATS
# ---------------------------------------------------------------------------

def test_le_demarrage_cree_une_ligne_par_graine() -> None:
    e = _etat({"evt": "demarrage", "graines": [101, 202, 303]})
    assert sorted(e.lignes) == [101, 202, 303]
    assert all(li.etat == "en attente" for li in e.lignes.values())
    assert e.en_cours


def test_une_graine_qui_trouve_et_une_qui_ne_trouve_pas() -> None:
    e = _etat(
        {"evt": "demarrage", "graines": [404, 303]},
        {"evt": "finie", "graine": 404, "deposables": 372, "seel": 0.5599,
         "n_blocs": 10, "crash": 0.0067, "minutes": 44.0},
        {"evt": "finie", "graine": 303, "deposables": 0, "seel": None, "minutes": 50.0},
    )
    assert e.lignes[404].etat == "trouve"
    assert e.lignes[303].etat == "rien"
    assert e.combien_trouvent() == 1
    assert e.meilleur_provisoire() == pytest.approx(0.5599)


def test_le_meilleur_provisoire_est_le_PLUS_PETIT() -> None:
    """Les trois graines qui trouvent s'etalent de 0,5599 a 0,6112 : 9,2 %."""
    e = _etat(
        {"evt": "deja", "graine": 505, "deposables": 311, "seel": 0.6112},
        {"evt": "deja", "graine": 404, "deposables": 372, "seel": 0.5599},
    )
    assert e.meilleur_provisoire() == pytest.approx(0.5599)


def test_la_notation_requalifie_les_graines_JAMAIS_LANCEES() -> None:
    """Une graine restee « en attente » quand la notation commence n'a pas ete essayee.
    L'afficher « en attente » laisserait croire qu'elle va encore tourner."""
    e = _etat(
        {"evt": "demarrage", "graines": [404, 909]},
        {"evt": "deja", "graine": 404, "deposables": 372, "seel": 0.5599},
        {"evt": "notation", "graine": 42},
    )
    assert e.lignes[909].etat == "non essayee"
    assert e.lignes[404].etat == "deja mesuree"


def test_un_evenement_INCONNU_est_ignore_sans_casser() -> None:
    """🔴 Une interface qui tourne depuis six heures ne tombe pas parce que le script a
    gagne un evenement."""
    e = _etat({"evt": "demarrage", "graines": [101]}, {"evt": "quelque_chose_de_neuf", "x": 1})
    assert sorted(e.lignes) == [101]


# ---------------------------------------------------------------------------
# 3. LE PROVISOIRE, ET L'ECART QUI LE CORRIGE
# ---------------------------------------------------------------------------

def test_le_bandeau_dit_PROVISOIRE_tant_qu_il_n_y_a_pas_de_notation() -> None:
    """🔴 C'est sur ce chiffre que 👤 decide d'arreter. Il doit porter sa reserve."""
    e = _etat({"evt": "deja", "graine": 404, "deposables": 372, "seel": 0.5599})
    assert "PROVISOIRE" in resumer(e)


def test_le_bandeau_annonce_le_CITABLE_apres_notation() -> None:
    e = _etat(
        {"evt": "deja", "graine": 404, "deposables": 372, "seel": 0.5599},
        {"evt": "resultat", "seel": 0.5612, "seel_provisoire": 0.5599, "n_blocs": 10},
    )
    t = resumer(e)
    assert "CITABLE" in t and "0.5612" in t and "disjointe" in t


def test_l_ecart_utilise_le_provisoire_VU_PAR_LE_SCRIPT() -> None:
    """🔑 Pas celui que la vue recalculerait : c'est le premier qui a decide de l'arret.
    Ici la vue verrait 0,5000 (une graine arrivee apres), le script a decide sur 0,5599."""
    e = _etat(
        {"evt": "resultat", "seel": 0.5612, "seel_provisoire": 0.5599},
        {"evt": "deja", "graine": 909, "deposables": 1, "seel": 0.5000},
    )
    assert e.ecart_provisoire_final_pct() == pytest.approx(100 * (0.5612 - 0.5599) / 0.5599)


def test_un_ecart_SOUS_le_bruit_n_alerte_pas() -> None:
    """+0,55 % mesure le 2026-08-22, cinq fois sous le bruit."""
    e = _etat({"evt": "resultat", "seel": 0.5599 * 1.0055, "seel_provisoire": 0.5599})
    assert e.avertissement_ecart() == ""


def test_un_ecart_AU_DESSUS_du_bruit_alerte() -> None:
    """+12,9 % mesure le 2026-08-15 : le chiffre annonce etait optimiste."""
    e = _etat({"evt": "resultat", "seel": 0.5599 * 1.129, "seel_provisoire": 0.5599})
    av = e.avertissement_ecart()
    assert "OPTIMISTE" in av
    assert f"{BRUIT_DIFFERENCE_SEEL_PCT}" in av


def test_un_resultat_MEILLEUR_que_le_provisoire_n_alerte_pas() -> None:
    """L'alerte vise l'optimisme, pas la surprise agreable."""
    e = _etat({"evt": "resultat", "seel": 0.5400, "seel_provisoire": 0.5599})
    assert e.avertissement_ecart() == ""


# ---------------------------------------------------------------------------
# 4. CE QUI EST TU EST PERDU
# ---------------------------------------------------------------------------

def test_la_TRONCATURE_de_l_union_se_voit() -> None:
    """📏 Premier essai reel du 2026-08-22 : 200 plans retenus, 483 ECARTES."""
    e = _etat({"evt": "union", "plans": 200, "ecartes": 483})
    assert "483" in resumer(e) and "ECARTE" in resumer(e)


def test_les_graines_NON_ESSAYEES_se_voient() -> None:
    e = _etat({"evt": "fin", "trouve": False, "non_essayees": [909, 1111]})
    assert "NON ESSAYEES" in resumer(e) and "909" in resumer(e)


def test_le_MOTIF_d_arret_se_voit() -> None:
    e = _etat({"evt": "arret", "motif": "cible atteinte : SEEL 0.5599 <= 0.5700 nm"})
    assert "cible atteinte" in resumer(e)


def test_le_drapeau_d_arret_est_retenu() -> None:
    """C'est le chemin qu'ecrira le bouton « Arreter »."""
    e = _etat({"evt": "drapeau", "chemin": r"C:\certus\reports\orchestre_x\FINALISER"})
    assert e.drapeau.endswith("FINALISER")


# ---------------------------------------------------------------------------
# 5. LA LIGNE DE COMMANDE CONSTRUITE PAR L'INTERFACE
# ---------------------------------------------------------------------------

def test_les_evenements_sont_TOUJOURS_armes() -> None:
    """🔴 Sans `--evenements`, l'interface serait aveugle et n'afficherait jamais rien."""
    args = construire_arguments(composant="r75x2", budget="2h", objectif="premier",
                                seel_cible=None, slots=2)
    assert "--evenements" in args


def test_la_cible_n_est_passee_que_si_elle_existe() -> None:
    sans = construire_arguments(composant="r75x2", budget="2h", objectif="premier",
                                seel_cible=None, slots=2)
    avec = construire_arguments(composant="r75x2", budget="2h", objectif="premier",
                                seel_cible=0.57, slots=2)
    assert "--seel-cible" not in sans
    assert avec[avec.index("--seel-cible") + 1] == "0.57"


def test_la_ligne_construite_est_ACCEPTEE_par_le_script() -> None:
    """🔑 LE TEST QUI RELIE LES DEUX MOITIES. Une interface qui construirait une commande que
    le script refuse echouerait a l'execution, pas ici. On la fait donc analyser pour de vrai.
    """
    args = construire_arguments(composant="r75x2", budget="1h30", objectif="meilleur",
                                seel_cible=0.57, slots=3, graines=[101, 202])
    # args[0] est le chemin du script ; `main` recoit ce qui vient apres.
    assert OM.main([*args[1:], "--dry-run"]) == 0


def test_la_garde_de_disjonction_tient_AUSSI_depuis_l_interface() -> None:
    """La regle ne doit pas etre contournable en passant par le GUI."""
    args = construire_arguments(composant="r75x2", budget="2h", objectif="premier",
                                seel_cible=None, slots=2, graines=[101, 202],
                                graine_notation=202)
    assert OM.main([*args[1:], "--dry-run"]) == 2


def test_le_json_du_flux_survit_a_un_chemin_WINDOWS() -> None:
    """Les antislashs d'un chemin Windows doivent traverser le JSON sans le casser."""
    d = json.loads(json.dumps({"chemin": r"C:\certus\reports\x\FINALISER"}))
    assert d["chemin"].endswith("FINALISER")


# ---------------------------------------------------------------------------
# 6. LA CHAINE ENTIERE -- QProcess -> sortie -> decodage -> tableau
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    __import__("os").environ.get("CERTUS_SKIP_GUI") == "1",
    reason="banc graphique desactive",
)
def test_le_pilotage_par_QProcess_remplit_reellement_le_tableau() -> None:
    """🔑 LE TEST QUI EPROUVE LE MAILLON QU'ON SUPPOSE TOUJOURS BON.

    Tout le reste de ce fichier teste des fonctions pures. Ici on demarre un VRAI processus,
    on laisse Qt lire sa sortie, et on verifie que le tableau se remplit. Le run est en
    `--dry-run` : la chaine de pilotage est identique, seul le calcul est absent.

    🔴 La QApplication est gardee dans une variable LOCALE et referencee jusqu'a la fin :
    ramassee par le GC, elle emporte la fenetre, et ce depot a deja perdu une soiree ainsi.
    """
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QCoreApplication, QEventLoop, QProcess
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None

    from certus.ui.certus_strat_ui import CertusStratApp

    fen = CertusStratApp()
    args = construire_arguments(composant="r75x2", budget="2h", objectif="premier",
                                seel_cible=None, slots=2)
    # ⚠️ La liste ENTIERE, chemin du script compris -- c'est ce que la vue passe a QProcess.
    # 📏 La premiere version de ce test retirait `args[0]` par symetrie avec `OM.main`, qui lui
    # recoit argv SANS le script : QProcess tentait alors d'executer un fichier nomme
    # « r75x2 » et sortait en code 2. Le test etait faux, pas le code -- mais il n'aurait
    # jamais ete trouve sans demarrer un vrai processus.
    fen._mg_demarrer_processus([*args, "--dry-run"])
    proc: QProcess = fen._mg_proc
    assert proc.waitForStarted(20_000), "le processus n'a meme pas demarre"
    proc.waitForFinished(120_000)
    assert proc.exitCode() == 0, f"la commande construite par l'interface a echoue (code {proc.exitCode()})"
    # Qt ne pompe les signaux que dans une boucle : sans cela `_mg_sur_sortie` ne serait
    # jamais appele et le test passerait sur un tableau vide.
    for _ in range(50):
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if fen._mg_etat.lignes and fen._mg_etat.drapeau:
            break

    assert fen._mg_etat.lignes, "aucun evenement n'a traverse le pilotage"
    assert fen._mg_table.rowCount() == len(fen._mg_etat.lignes)
    assert fen._mg_etat.drapeau.endswith("FINALISER"), "le bouton Arreter n'aurait pas de cible"

    # 🔴 ON DEBRANCHE AVANT DE PARTIR. Sans cela `finished` se declenche apres que le test a
    # rendu la main, sur une fenetre que le GC a deja emportee -- « wrapped C/C++ object of
    # type CertusStratApp has been deleted ». C'est un avertissement ici, mais c'est le meme
    # mecanisme qui a coute une soiree a ce depot sur son banc headless.
    proc.readyReadStandardOutput.disconnect()
    proc.finished.disconnect()


# ---------------------------------------------------------------------------
# 7. FINALISER N'EST PAS ANNULER -- les deux modes menent a l'etape 3
# ---------------------------------------------------------------------------

def test_pas_de_fichier_pas_d_arret(tmp_path: Path) -> None:
    assert OM.mode_finalisation_demandee(tmp_path / "FINALISER") == ""


def test_un_fichier_VIDE_veut_dire_ATTENDRE(tmp_path: Path) -> None:
    """Le mode par defaut : rien n'est gaspille, on laisse finir ce qui vole."""
    f = tmp_path / "FINALISER"
    f.write_text("", encoding="utf-8")
    assert OM.mode_finalisation_demandee(f) == "attendre"


def test_le_mot_abandonner_veut_dire_ETAPE_3_TOUT_DE_SUITE(tmp_path: Path) -> None:
    """👤 : « on n'est pas oblige de terminer de suite, on peut passer a l'etape 3 »."""
    f = tmp_path / "FINALISER"
    f.write_text("abandonner", encoding="utf-8")
    assert OM.mode_finalisation_demandee(f) == "abandonner"


@pytest.mark.parametrize("contenu", ["ABANDONNER", "  abandonner\n", "abandonner tout de suite"])
def test_le_mot_est_reconnu_malgre_la_casse_et_les_blancs(tmp_path: Path, contenu: str) -> None:
    f = tmp_path / "FINALISER"
    f.write_text(contenu, encoding="utf-8")
    assert OM.mode_finalisation_demandee(f) == "abandonner"


def test_un_contenu_INATTENDU_retombe_sur_le_mode_PRUDENT(tmp_path: Path) -> None:
    """🔴 En cas de doute on ATTEND : detruire une mesure de 45 minutes sur un contenu mal
    ecrit serait le mauvais sens de l'erreur."""
    f = tmp_path / "FINALISER"
    f.write_text("stop please", encoding="utf-8")
    assert OM.mode_finalisation_demandee(f) == "attendre"


# ---------------------------------------------------------------------------
# 8. LA PASSE CONTRADICTOIRE -- ce que la premiere version rendait FAUX
# ---------------------------------------------------------------------------

from certus.ui.certus_strat_multigraine_ui import (  # noqa: E402
    COMPOSANTS,
    composant_depuis_fichier,
    interpreteur_et_script,
)


def test_le_composant_est_DEDUIT_du_fichier_charge() -> None:
    """🔴 La premiere version codait « r75x2 » EN DUR. 👤 pouvait avoir charge un tout autre
    empilement : l'onglet aurait rendu un SEEL plausible portant sur autre chose. C'est la
    faute que ce depot redoute le plus."""
    for nom, (rel, _n) in COMPOSANTS.items():
        assert composant_depuis_fichier(rel) == nom, f"{rel} ne retrouve pas {nom}"


def test_un_fichier_INCONNU_ne_rend_AUCUN_composant() -> None:
    """🔴 Et surtout PAS un defaut : l'appelant doit refuser."""
    assert composant_depuis_fichier("example/example_strat/JSON-strat-inexistant.json") is None
    assert composant_depuis_fichier("") is None
    assert composant_depuis_fichier(None) is None


def test_le_chemin_ABSOLU_du_depot_est_reconnu() -> None:
    from certus.ui.certus_strat_multigraine_ui import RACINE

    rel, _ = COMPOSANTS["r75x2"]
    assert composant_depuis_fichier(str(RACINE / rel)) == "r75x2"


def test_deux_composants_VOISINS_ne_se_confondent_pas() -> None:
    """`r75x2` et `r75x2-2nm` sont deux composants DISTINCTS et deliberement proches : l'un
    porte les rampes, l'autre non. Les confondre inverserait la conclusion du 2026-08-22."""
    a, _ = COMPOSANTS["r75x2"]
    b, _ = COMPOSANTS["r75x2-2nm"]
    assert a != b
    assert composant_depuis_fichier(a) == "r75x2"
    assert composant_depuis_fichier(b) == "r75x2-2nm"


def test_hors_mode_gele_l_interpreteur_est_trouvable() -> None:
    py, motif = interpreteur_et_script()
    assert py is not None and motif == ""


def test_en_mode_GELE_on_REFUSE_en_disant_pourquoi(monkeypatch: pytest.MonkeyPatch) -> None:
    """🔴 `certus_hub.spec` produit un executable PyInstaller. Dans ce paquet `sys.executable`
    est `CERTUS_HUB.exe`, `__file__` pointe dans un dossier temporaire et `scripts/` n'est pas
    embarque. Lancer le script y donnerait une erreur incomprehensible."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    py, motif = interpreteur_et_script()
    assert py is None
    assert "COMPILEE" in motif and "sources" in motif


def test_une_derniere_ligne_SANS_retour_chariot_n_est_pas_perdue() -> None:
    """🔴 Le tampon decoupe sur les lignes COMPLETES. Un dernier paquet sans « \n » y resterait
    coince -- et ce dernier paquet peut porter `resultat`, donc LE CHIFFRE CITABLE. L'interface
    afficherait alors un provisoire comme s'il etait definitif : le pire sens de la perte."""
    # ⚠️ PAS d'application complete ici : `CertusStratApp` demarre un fil de prechauffage
    # numba qui emet un signal apres coup, sur une fenetre que le GC a emportee. Ce test n'a
    # besoin que du drainage, donc d'un objet portant le mixin -- rien de plus.
    from certus.ui.certus_strat_multigraine_ui import CertusStratMultigraineMixin

    class _Bouton:
        def setEnabled(self, _v: bool) -> None: ...

    class _Stub(CertusStratMultigraineMixin):
        _mg_bouton_lancer = _Bouton()
        _mg_bouton_finaliser = _Bouton()
        _mg_bouton_finaliser_vite = _Bouton()

        def _mg_rafraichir(self) -> None:  # la vue n'est pas le sujet de ce test
            ...

    fen = _Stub()
    fen._mg_etat = EtatMultigraine()
    # un evenement complet, puis un second SANS retour chariot
    fen._mg_tampon = (
        OM.PREFIXE_EVT + '{"evt": "union", "plans": 200, "ecartes": 483}\n'
        + OM.PREFIXE_EVT + '{"evt": "resultat", "seel": 0.5642, "seel_provisoire": 0.5599}'
    )
    fen._mg_proc = None
    fen._mg_sur_fin()
    assert fen._mg_etat.plans_unis == 200
    assert fen._mg_etat.seel_final == pytest.approx(0.5642), (
        "le chiffre citable a ete perdu dans le tampon"
    )
