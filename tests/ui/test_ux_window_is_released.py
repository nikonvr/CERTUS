"""Une fenêtre fermée doit mourir — sinon tout ce qui suit ralentit.

🔴 CE QUI A ÉTÉ MESURÉ LE 2026-09-09, `scripts/sonde_fenetres_fuient.py` :

    #  construction (s)   widgets de 1er niveau vivants
    1        0.519                45
    2        0.903                90
    3        1.293               135

**Chaque construction de la fenêtre RE laisse 45 widgets de premier niveau
vivants** — 31 menus, la fenêtre elle-même, et le reste — malgré `close()`, `del`
et un ramassage explicite. Le coût de construction croît **linéairement** avec ce
qui traîne : ×3,54 en six itérations sur RE, ×2,84 sur STRAT.

🔑 **C'EST POURQUOI LA SUITE D'INTERFACE NE PEUT PLUS SE LANCER D'UN SEUL TENANT.**
`test_ux_re_stop_when_idle.py` coûte **6,5 s lancé seul** et **plus de 30 min** à
l'intérieur de la suite, qui partage une seule `QApplication` de portée session.
Ce n'est pas ce fichier qui est lent : c'est tout ce que les 700 tests précédents
ont laissé vivant.

📏 **UNE CAUSE TROUVÉE, ET ELLE ÉTAIT CIRCULAIRE.**
`certus/ui/certus_toast_stack.py` tenait un dictionnaire **de module** qui gardait
chaque pile de notifications ; la pile garde une référence Python vers son parent ;
et le nettoyage était branché sur le signal de destruction du parent. **Ce
nettoyage ne pouvait donc jamais s'exécuter** : il attendait une destruction que sa
propre référence empêchait. Corrigé le 2026-09-09 — c'est ce que ce fichier garde.

🔴 **MAIS CE N'ÉTAIT PAS LA SEULE, ET LA FUITE DES FENÊTRES DEMEURE.** 📏 Remesuré
après le correctif : la fenêtre RE laisse **toujours 45 widgets** par construction,
facteur **×3,63** sur six. Ce fichier prouve donc exactement ce qu'il teste — un
parent qui reçoit une pile est désormais libéré — et **rien de plus**.

📌 **Les retenants restants sont nommés**, par `gc.get_referrers` : quatre méthodes
liées (`CertusBaseApp._schedule_eval`, `CertusRETableMixin.add_target`,
`CertusCommandPaletteMixin._show_default_about_dialog` et `run_onboarding_tour`) et
cinq fermetures lexicales. ⚠️ **Ce ne sont PAS les minuteries à un coup** : laisser
tourner la boucle d'événements 1,5 s ne libère rien, le compte continue de croître.

⚠️ **Un défaut du PRODUIT, pas seulement du harnais.** Une session qui ouvre et
ferme des modules ne rend jamais leur mémoire.

📌 Le contrôle négatif est dans le premier test : un widget qui n'a jamais reçu de
pile est bien libéré. Sans lui, un ramassage cassé ferait passer tout le fichier.
"""

from __future__ import annotations

import gc
import weakref


def _libere(fabrique, preparer=None) -> bool:
    """Le widget est-il réellement collecté une fois la dernière référence lâchée ?

    🔴 IL FAUT UNE FABRIQUE, PAS UN WIDGET DÉJÀ CONSTRUIT, et le contrôle négatif
    l'a démontré avant que ce fichier ne serve à rien. Passer l'objet en argument
    en laisse une référence **chez l'appelant** — sur sa pile d'évaluation, ou
    dans sa variable locale. Le premier jet déclarait donc qu'un `QWidget` nu ne
    se collecte pas, ce qui est faux : c'était l'instrument.
    """
    widget = fabrique()
    if preparer is not None:
        preparer(widget)
    tesson = weakref.ref(widget)
    del widget
    gc.collect()
    return tesson() is None


def test_a_widget_without_a_toast_stack_is_released(qapp):
    """Contrôle négatif : sans lui, un ramassage cassé rendrait le suivant muet."""
    from PyQt6.QtWidgets import QWidget

    assert _libere(QWidget), "même un widget nu n'est pas collecté : c'est le harnais qui est en cause, pas le code"


def test_a_widget_that_owns_a_toast_stack_is_released(qapp):
    """Le défaut lui-même : un appel suffit à rendre le widget immortel."""
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_toast_stack import get_toast_stack

    assert _libere(QWidget, get_toast_stack), (
        "le widget survit à sa dernière référence parce que la pile de notifications "
        "le retient — voir la docstring de ce fichier"
    )


def test_the_same_parent_keeps_the_same_stack(qapp):
    """La correction ne doit pas casser ce que le registre servait à garantir.

    ⚠️ C'est la contrainte que `tests/ui/test_certus_toast_stack.py` pose déjà :
    deux appels rendent la MÊME pile. Reprise ici pour qu'une correction de la
    fuite ne la perde pas en chemin.
    """
    from PyQt6.QtWidgets import QWidget

    from certus.ui.certus_toast_stack import get_toast_stack

    parent = QWidget()
    try:
        assert get_toast_stack(parent) is get_toast_stack(parent), (
            "deux appels rendent deux piles différentes : les notifications ne s'empileraient plus"
        )
    finally:
        parent.deleteLater()


def test_repeated_windows_do_not_pile_up(qapp):
    """La conséquence mesurable : le nombre de widgets vivants doit se stabiliser."""
    from PyQt6.QtWidgets import QApplication, QWidget

    from certus.ui.certus_toast_stack import get_toast_stack

    def cycle() -> int:
        widget = QWidget()
        get_toast_stack(widget)
        widget.close()
        del widget
        gc.collect()
        qapp.processEvents()
        gc.collect()
        return len(QApplication.topLevelWidgets())

    cycle()
    depart = cycle()
    arrivee = depart
    for _ in range(4):
        arrivee = cycle()

    assert arrivee <= depart, (
        f"les widgets de premier niveau passent de {depart} à {arrivee} en quatre cycles : "
        "chaque fenêtre ouverte reste vivante, et la suivante coûte plus cher à construire"
    )
