"""ONGLET « Multi-realisation » -- chercher sur K graines dans un budget, et pouvoir couper.

## POURQUOI CET ONGLET, ET POURQUOI IL NE CALCULE RIEN LUI-MEME

Sur `r75x2` a 2 nm, une graine trouve ou ne trouve pas. Mesure du 2026-08-22, sept graines
NUES, plage complete, aucune surcharge : 42, 101, 202, 303 rendent **zero** ; 77, 404 et 505
trouvent, avec des SEEL de 0,5692, 0,5599 et 0,6112 nm. La reponse produit est donc de rejouer
la meme recherche sur plusieurs realisations.

🔑 **CET ONGLET PILOTE `scripts/orchestre_multigraine.py`, IL NE LE REIMPLEMENTE PAS.** La regle
de la disjonction des graines, l'union en tourniquet, le plafond de temps, l'ecriture des
artefacts -- tout cela vit dans le script, y est teste, et n'existe qu'a un seul endroit. Deux
chemins de code finiraient par diverger, et c'est une facture que ce depot a deja payee.

🔴 **ET LE PILOTAGE PASSE PAR DES PROCESSUS SEPARES, CE N'EST PAS UN DETAIL D'IMPLANTATION.**
`certus_strat_workers.py:1452` force `max_workers = 1` avec le motif « prevent Numba CPU
oversubscription and deadlocks ». Un deadlock numba est INTRA-processus : lancer K recherches
dans des processus distincts contourne le danger au lieu de le braver. C'est aussi ce qui
permet a l'interface de rester vivante pendant des heures de calcul.

## CE QUE L'UTILISATEUR VOIT, ET LA RESERVE QUI VOYAGE AVEC

Le SEEL annonce pendant la campagne est **PROVISOIRE** : il est mesure sur la graine qui l'a
trouve. Le chiffre citable vient de la notation finale sur une graine **disjointe**. L'ecart
est le canal de la malediction du vainqueur -- **+12,9 %** le 2026-08-15, **+0,55 %** le
2026-08-22. Ce n'est donc pas une constante, et la colonne « provisoire » du tableau existe
pour que personne ne cite le mauvais nombre.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
_SCRIPTS = RACINE / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

#: 🔑 Le format d'evenement est IMPORTE de l'emetteur, jamais recopie. Un format dont
#: l'ecriture et la lecture vivent dans deux fichiers derive au premier changement.
from orchestre_multigraine import (  # noqa: E402
    ECHELLE_GRAINES,
    GRAINE_NOTATION_DEFAUT,
    lire_evenement,
)
from probe_blocs_vs_plantage import COMPOSANTS  # noqa: E402


def interpreteur_et_script() -> tuple[str | None, str]:
    """L'interpreteur a lancer et le motif d'un refus. Rend (None, motif) si c'est impossible.

    🔴 EN MODE GELE, RIEN DE TOUT CECI NE MARCHE, ET IL FAUT LE DIRE AU LIEU D'ECHOUER
    BIZARREMENT. `certus_hub.spec` produit un executable PyInstaller ; dans ce paquet
    `sys.executable` est `CERTUS_HUB.exe` et non un python, `__file__` pointe dans un dossier
    d'extraction temporaire, et `scripts/` n'est pas embarque du tout. Lancer
    `sys.executable scripts/orchestre_multigraine.py` y donnerait une erreur incomprehensible.

    ⚠️ La reparation propre serait d'embarquer le script et de retrouver un interpreteur ; elle
    n'est pas faite, et elle ne peut pas etre eprouvee sans construire un paquet. On DETECTE
    donc, et on refuse en disant pourquoi.
    """
    if getattr(sys, "frozen", False):
        return None, (
            "🔴 la recherche multi-realisation n'est pas disponible dans la version COMPILEE : "
            "elle lance des processus separes a partir de `scripts/`, qui n'est pas embarque "
            "dans le paquet. Lance CERTUS depuis les sources pour l'utiliser."
        )
    script = RACINE / "scripts" / "orchestre_multigraine.py"
    if not script.is_file():
        return None, f"🔴 script introuvable : {script}"
    return sys.executable, ""

#: Le bruit sur une DIFFERENCE de SEEL, mesure sur ce depot. Sert a dire si un ecart
#: provisoire -> definitif est significatif ou non.
BRUIT_DIFFERENCE_SEEL_PCT = 2.59


@dataclass
class LigneGraine:
    graine: int
    etat: str = "en attente"
    seel: float | None = None
    n_blocs: int | None = None
    crash: float | None = None
    minutes: float | None = None
    deposables: int = 0
    provisoire: bool = True


@dataclass
class EtatMultigraine:
    """La machine a etats de l'onglet -- PURE, sans Qt, donc testable sans ecran.

    🔑 Elle est separee de la vue deliberement. Une logique d'affichage enfermee dans un widget
    ne se teste qu'en ouvrant une fenetre, et ce depot a deja mesure ce que coute un banc
    graphique (QApplication ramassee par le GC, dialogues modales, `_is_busy` mort).
    """

    lignes: dict[int, LigneGraine] = field(default_factory=dict)
    motif_finalisation: str = ""
    drapeau: str = ""
    en_cours: bool = False
    seel_final: float | None = None
    seel_provisoire_retenu: float | None = None
    non_essayees: list[int] = field(default_factory=list)
    plans_unis: int | None = None
    plans_ecartes: int = 0
    n_blocs_final: int | None = None
    crash_final: float | None = None
    graine_notation: int | None = None
    artefact_final: str = ""

    def appliquer(self, evt: dict) -> None:
        """Consomme un evenement du flux `[ORCH]`. Ignore ce qu'elle ne connait pas.

        ⚠️ Ignorer l'inconnu est VOULU : un evenement ajoute plus tard au script ne doit pas
        faire tomber une interface qui tourne depuis six heures.
        """
        t = evt.get("evt")
        if t == "demarrage":
            self.en_cours = True
            self.lignes = {int(g): LigneGraine(int(g)) for g in evt.get("graines", [])}
        elif t == "drapeau":
            self.drapeau = str(evt.get("chemin", ""))
        elif t in ("deja", "finie"):
            g = int(evt["graine"])
            li = self.lignes.setdefault(g, LigneGraine(g))
            li.deposables = int(evt.get("deposables") or 0)
            li.seel = evt.get("seel")
            li.n_blocs = evt.get("n_blocs")
            li.crash = evt.get("crash")
            li.minutes = evt.get("minutes")
            if t == "deja":
                li.etat = "deja mesuree"
            else:
                li.etat = "trouve" if li.deposables else "rien"
        elif t == "lancee":
            g = int(evt["graine"])
            self.lignes.setdefault(g, LigneGraine(g)).etat = "en cours"
        elif t == "arret":
            self.motif_finalisation = str(evt.get("motif", ""))
        elif t == "union":
            self.plans_unis = int(evt.get("plans") or 0)
            self.plans_ecartes = int(evt.get("ecartes") or 0)
        elif t == "notation":
            for li in self.lignes.values():
                if li.etat == "en attente":
                    li.etat = "non essayee"
        elif t == "resultat":
            self.seel_final = evt.get("seel")
            # 🔑 On retient le provisoire TEL QUE LE SCRIPT L'A VU, pas tel que la vue le
            # recalcule : c'est lui qui a decide de l'arret, et l'ecart publie doit porter
            # sur ce chiffre-la. Les recalculer ici les ferait diverger silencieusement.
            self.seel_provisoire_retenu = evt.get("seel_provisoire")
            self.n_blocs_final = evt.get("n_blocs")
            self.crash_final = evt.get("crash")
            self.graine_notation = evt.get("graine_notation")
            self.artefact_final = str(evt.get("artefact") or "")
        elif t == "fin":
            self.en_cours = False
            self.non_essayees = [int(g) for g in evt.get("non_essayees", [])]

    # -- lectures ------------------------------------------------------------------------

    def meilleur_provisoire(self) -> float | None:
        """Le meilleur SEEL annonce en cours de campagne. 🔴 PROVISOIRE : chaque valeur est
        mesuree sur la graine qui l'a trouvee, et elles ne sont pas comparables entre elles au
        sens strict. On l'affiche comme un REPERE pour decider d'arreter, jamais comme un
        resultat."""
        vus = [li.seel for li in self.lignes.values() if li.seel is not None]
        return min(vus) if vus else None

    def combien_trouvent(self) -> int:
        return sum(1 for li in self.lignes.values() if li.deposables > 0)

    def ecart_provisoire_final_pct(self) -> float | None:
        """Le canal de malediction du vainqueur, mesure a CETTE campagne."""
        prov = self.seel_provisoire_retenu or self.meilleur_provisoire()
        if prov is None or self.seel_final is None or prov <= 0:
            return None
        return 100.0 * (self.seel_final - prov) / prov

    def avertissement_ecart(self) -> str:
        e = self.ecart_provisoire_final_pct()
        if e is None or e <= BRUIT_DIFFERENCE_SEEL_PCT:
            return ""
        return (
            f"l'ecart provisoire -> definitif vaut {e:+.2f} %, au-dela du bruit de "
            f"{BRUIT_DIFFERENCE_SEEL_PCT} % : le chiffre annonce en cours de route etait OPTIMISTE"
        )


def composant_depuis_fichier(chemin: str | None) -> str | None:
    """Le nom de composant que la sonde attend, deduit du fichier CHARGE dans l'application.

    🔴 CETTE FONCTION EXISTE PARCE QUE LA PREMIERE VERSION DE L'ONGLET CODAIT « r75x2 » EN DUR.
    L'utilisateur pouvait charger n'importe quel composant : l'onglet aurait cherche sur un
    AUTRE, et rendu un SEEL parfaitement plausible portant sur un empilement qui n'est pas
    celui affiche. C'est la faute que ce depot redoute le plus -- « une erreur silencieuse ne
    plante pas : elle produit un resultat faux qui a l'air juste, et quelqu'un fabrique une
    piece avec » (AGENTS.md).

    Rend None si le fichier ne correspond a aucune entree de `COMPOSANTS` -- et l'appelant doit
    alors REFUSER, jamais choisir a la place de l'utilisateur.
    """
    if not chemin:
        return None
    try:
        cible = Path(chemin).resolve()
    except (OSError, ValueError):
        return None
    for nom, (rel, _n) in COMPOSANTS.items():
        try:
            if (RACINE / rel).resolve() == cible:
                return nom
        except (OSError, ValueError):
            continue
    # Repli sur le nom de fichier : un depot clone ailleurs, ou un chemin relatif, ne doit pas
    # faire perdre la correspondance.
    for nom, (rel, _n) in COMPOSANTS.items():
        if Path(rel).name.lower() == cible.name.lower():
            return nom
    return None


def construire_arguments(
    *,
    composant: str,
    budget: str,
    objectif: str,
    seel_cible: float | None,
    slots: int,
    mode: str = "deep",
    resolution: float = 2.0,
    graines: list[int] | None = None,
    graine_notation: int = GRAINE_NOTATION_DEFAUT,
) -> list[str]:
    """La ligne de commande, construite en UN endroit et testable sans lancer Qt.

    🔴 `--evenements` est TOUJOURS pose : c'est par lui que l'interface sait ce qui se passe.
    """
    args = [
        "scripts/orchestre_multigraine.py", composant,
        "--budget", budget,
        "--objectif", objectif,
        "--mode", mode,
        "--resolution", f"{resolution:g}",
        "--slots", str(int(slots)),
        "--graine-notation", str(int(graine_notation)),
        "--evenements",
    ]
    if seel_cible is not None:
        args += ["--seel-cible", f"{seel_cible:g}"]
    if graines:
        args += ["--graines", *[str(int(g)) for g in graines]]
    return args


# =========================================================================================
# LA VUE -- mince par construction : elle affiche l'etat ci-dessus et pilote un QProcess.
# =========================================================================================

class CertusStratMultigraineMixin:
    """Onglet « Multi-realisation ». Melange dans `CertusStratApp`."""

    def _create_multigraine_tab(self) -> None:
        from PyQt6.QtCore import QProcess
        from PyQt6.QtWidgets import (
            QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
            QTableWidget, QVBoxLayout, QWidget,
        )
        from certus.ui.certus_ui_widgets_cards import CertusCard

        self._mg_etat = EtatMultigraine()
        self._mg_proc: QProcess | None = None
        self._mg_tampon = ""

        onglet = QWidget()
        self.tabs.addTab(onglet, "Multi-realisation")
        v = QVBoxLayout(onglet)
        v.setSpacing(10)
        v.setContentsMargins(5, 5, 5, 5)

        # -- reglages ---------------------------------------------------------------------
        carte = CertusCard("Budget et objectif")
        g = QHBoxLayout()
        # 🔴 LE COMPOSANT EST EXPLICITE, ET SANS VALEUR PAR DEFAUT MUETTE. La premiere version
        # codait « r75x2 » en dur : l'utilisateur pouvait avoir charge un tout autre
        # empilement et l'onglet aurait rendu un SEEL plausible portant sur autre chose.
        self._mg_composant = QComboBox()
        self._mg_composant.addItem("")
        self._mg_composant.addItems(sorted(COMPOSANTS))
        self._mg_composant.setToolTip(
            "Le composant a chercher. Pre-selectionne sur celui que vous avez charge, quand il "
            "correspond a une entree connue.\n🔴 Sans choix explicite, la recherche est REFUSEE."
        )
        _pre = composant_depuis_fichier(getattr(self, "_last_config_file", None))
        if _pre:
            self._mg_composant.setCurrentText(_pre)
        self._mg_budget = QLineEdit("2h")
        self._mg_budget.setToolTip(
            "Duree maximale : 2h · 90m · 1h30 · nuit (10 h).\n"
            "Le budget gouverne les LANCEMENTS, pas les arrets : un run deja en vol est "
            "laisse finir, parce qu'un run coupe est une mesure detruite."
        )
        self._mg_objectif = QComboBox()
        self._mg_objectif.addItems(["premier", "meilleur"])
        self._mg_objectif.setToolTip(
            "premier : on s'arrete des qu'une realisation trouve -- le plus rapide.\n"
            "meilleur : on epuise le budget et on unit tout.\n"
            "⚠️ Les trois graines qui trouvent s'etalent de 0,5599 a 0,6112 nm, soit 9,2 % : "
            "s'arreter au premier peut couter cela."
        )
        self._mg_cible = QLineEdit("")
        self._mg_cible.setPlaceholderText("ex. 0.57")
        self._mg_cible.setToolTip(
            "On arrete des qu'une realisation rend un SEEL <= cette valeur, en nm.\n"
            "Laisser vide pour ne pas armer de cible."
        )
        self._mg_slots = QLineEdit("2")
        self._mg_slots.setToolTip(
            "Recherches concurrentes, en processus SEPARES.\n"
            "Mesure du 2026-08-22 sur 16 threads : deux runs concurrents rendent +29 % de "
            "debit, pas +100 % -- le goulot est la bande passante memoire."
        )
        for lib, w in (("Composant :", self._mg_composant),
                       ("Budget :", self._mg_budget), ("Objectif :", self._mg_objectif),
                       ("SEEL cible (nm) :", self._mg_cible), ("Slots :", self._mg_slots)):
            g.addWidget(QLabel(lib))
            g.addWidget(w)
        carte.body.addLayout(g)
        v.addWidget(carte)

        # -- boutons ----------------------------------------------------------------------
        barre = QHBoxLayout()
        self._mg_bouton_lancer = QPushButton("Lancer la recherche multi-realisation")
        self._mg_bouton_lancer.clicked.connect(self._mg_lancer)
        # 🔑 LE MOT EST « FINALISER », PAS « ARRETER », ET C'EST 👤 QUI L'A TROUVE :
        # « plutot que arreter, le vrai mot serait finaliser ». « Arreter » dit ce qu'on
        # QUITTE et se lit « tout annuler » ; or les deux boutons produisent le chiffre
        # citable -- ils ne different que par le sort des realisations EN VOL. Le mot juste
        # dit ce qu'on OBTIENT.
        self._mg_bouton_finaliser = QPushButton("Finaliser — laisser finir les realisations en vol")
        self._mg_bouton_finaliser.setEnabled(False)
        self._mg_bouton_finaliser.setToolTip(
            "Cesse de LANCER de nouvelles realisations, LAISSE FINIR celles qui tournent, puis "
            "enchaine sur l'union et la notation finale.\nRien n'est gaspille — mais il faut "
            "attendre la fin des runs en vol."
        )
        self._mg_bouton_finaliser.clicked.connect(lambda: self._mg_finaliser("attendre"))

        self._mg_bouton_finaliser_vite = QPushButton("Finaliser tout de suite — abandonner ce qui vole")
        self._mg_bouton_finaliser_vite.setEnabled(False)
        self._mg_bouton_finaliser_vite.setToolTip(
            "Passe a l'union et a la notation finale IMMEDIATEMENT, sur ce qui est deja mesure.\n"
            "⚠️ Les realisations en vol sont tuees et leur travail est PERDU — quatre mesures "
            "de 91 min l'ont ete ainsi le 2026-08-22, coupees a 98,9 % d'avancement."
        )
        self._mg_bouton_finaliser_vite.clicked.connect(lambda: self._mg_finaliser("abandonner"))

        barre.addWidget(self._mg_bouton_lancer)
        barre.addWidget(self._mg_bouton_finaliser)
        barre.addWidget(self._mg_bouton_finaliser_vite)
        barre.addStretch(1)
        v.addLayout(barre)

        # -- tableau vivant ---------------------------------------------------------------
        self._mg_table = QTableWidget(0, 6)
        self._mg_table.setHorizontalHeaderLabels(
            ["Graine", "Etat", "SEEL (nm)", "Blocs", "Plantage", "Duree"]
        )
        self._mg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        v.addWidget(self._mg_table, 1)

        self._mg_resume = QLabel(
            "Le SEEL affiche pendant la campagne est PROVISOIRE : il est mesure sur la graine "
            "qui l'a trouve. Le chiffre citable vient de la notation finale sur une graine "
            "disjointe."
        )
        self._mg_resume.setWordWrap(True)
        v.addWidget(self._mg_resume)
        self._mg_rafraichir()

    # -- pilotage -------------------------------------------------------------------------

    def _mg_lancer(self) -> None:
        from PyQt6.QtCore import QProcess

        try:
            cible = float(self._mg_cible.text().replace(",", ".")) if self._mg_cible.text().strip() else None
            slots = int(self._mg_slots.text())
        except ValueError:
            self._mg_resume.setText("🔴 SEEL cible ou slots illisible.")
            return

        py, motif = interpreteur_et_script()
        if py is None:
            self._mg_resume.setText(motif)
            return

        composant = self._mg_composant_courant()
        if composant is None:
            # 🔴 ON REFUSE, ON NE DEVINE PAS. Chercher sur un composant que 👤 n'a pas designe
            # rendrait un SEEL parfaitement plausible portant sur un autre empilement.
            self._mg_resume.setText(
                "🔴 choisis un COMPOSANT avant de lancer. Aucun defaut n'est applique : "
                "chercher sur un empilement que tu n'as pas designe rendrait un SEEL "
                "plausible et faux."
            )
            return

        args = construire_arguments(
            composant=composant,
            budget=self._mg_budget.text().strip() or "2h",
            objectif=self._mg_objectif.currentText(),
            seel_cible=cible,
            slots=slots,
        )
        self._mg_python = py
        self._mg_demarrer_processus(args)

    _mg_python: str = sys.executable

    def _mg_demarrer_processus(self, args: list[str]) -> None:
        """La couture. 🔑 Elle existe pour que la chaine ENTIERE -- demarrage, sortie standard,
        decodage, machine a etats, tableau -- soit eprouvee par un test au lieu d'etre supposee.
        Sans elle, le seul moyen de verifier le pilotage serait de lancer une vraie campagne de
        plusieurs heures, donc personne ne le ferait."""
        from PyQt6.QtCore import QProcess

        self._mg_etat = EtatMultigraine()
        self._mg_tampon = ""
        self._mg_proc = QProcess()
        self._mg_proc.setWorkingDirectory(str(RACINE))
        self._mg_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._mg_proc.readyReadStandardOutput.connect(self._mg_sur_sortie)
        self._mg_proc.finished.connect(self._mg_sur_fin)
        self._mg_proc.start(self._mg_python, args)
        self._mg_bouton_lancer.setEnabled(False)
        self._mg_bouton_finaliser.setEnabled(True)
        self._mg_bouton_finaliser_vite.setEnabled(True)
        self._mg_rafraichir()

    def _mg_composant_courant(self) -> str | None:
        """Le composant a chercher : celui que l'utilisateur a CHOISI dans la liste.

        🔴 Rend None si rien n'est choisi, et l'appelant REFUSE de lancer. Il n'y a
        deliberement aucune valeur par defaut : chercher sur un composant que l'utilisateur
        n'a pas designe rendrait un SEEL plausible portant sur un autre empilement.
        """
        nom = self._mg_composant.currentText().strip()
        return nom if nom in COMPOSANTS else None

    def _mg_finaliser(self, mode: str = "attendre") -> None:
        """🔑 ON DEPOSE UN FICHIER, ON NE TUE PAS depuis l'interface -- et son CONTENU dit le
        mode. 👤 : « si on clique sur arreter, on n'est pas oblige de terminer de suite, on peut
        passer a l'etape 3 ».

        Les DEUX modes menent a l'etape 3, l'union puis la notation finale. Ce qui les separe
        est le sort des realisations en vol :

            attendre    on les laisse finir     rien n'est perdu, mais on attend
            abandonner  on les tue              etape 3 tout de suite, leur travail est perdu
        """
        if not self._mg_etat.drapeau:
            # 🔴 UN BOUTON ACTIF QUI N'AGIT PAS EST PIRE QU'UN BOUTON GRISE. Ce cas ne devrait
            # plus arriver -- le script annonce son drapeau des la premiere seconde -- mais
            # s'il arrivait, 👤 doit le savoir plutot que de croire l'arret demande.
            self._mg_resume.setText(
                "🔴 finalisation IMPOSSIBLE pour l'instant : la campagne n'a pas encore annonce son "
                "point de finalisation. Reessaie dans un instant."
            )
            return
        Path(self._mg_etat.drapeau).write_text(
            "abandonner" if mode == "abandonner" else "", encoding="utf-8"
        )
        self._mg_bouton_finaliser.setEnabled(False)
        self._mg_bouton_finaliser_vite.setEnabled(False)
        self._mg_resume.setText(
            "⏹ FINALISATION demandee — les realisations en vol sont TUEES, l'union et la notation "
            "sur graine disjointe s'enchainent tout de suite."
            if mode == "abandonner" else
            "⏹ FINALISATION demandee — les realisations en vol sont laissees finir, puis l'union et "
            "la notation sur graine disjointe produisent le chiffre citable."
        )

    def _mg_sur_sortie(self) -> None:
        brut = bytes(self._mg_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._mg_tampon += brut
        # ⚠️ On decoupe sur les lignes COMPLETES seulement : un evenement JSON coupe en deux
        # par la frontiere d'un paquet serait illisible, et `lire_evenement` rendrait None
        # en silence.
        *lignes, self._mg_tampon = self._mg_tampon.split("\n")
        for ligne in lignes:
            evt = lire_evenement(ligne.strip())
            if evt is not None:
                self._mg_etat.appliquer(evt)
        self._mg_rafraichir()

    def _mg_sur_fin(self) -> None:
        # 🔴 ON VIDE LE TUYAU AVANT DE CONCLURE. `finished` peut arriver alors qu'un dernier
        # paquet n'a pas ete lu : sans ce drainage, les evenements `resultat` et `fin` -- donc
        # LE CHIFFRE CITABLE -- se perdraient, et l'interface afficherait un provisoire comme
        # s'il etait definitif. C'est le pire sens possible pour une perte.
        try:
            self._mg_sur_sortie()
        except (RuntimeError, AttributeError):
            pass
        # ⚠️ Et le reste peut porter PLUSIEURS lignes, dont une derniere sans retour chariot --
        # un processus tue en ecrivant en laisse une. 📏 Ma premiere version traitait tout le
        # tampon comme UNE ligne : le JSON devenait illisible et les evenements etaient perdus
        # tous ensemble. C'est un test qui l'a trouve, pas une relecture.
        if self._mg_tampon:
            for ligne in self._mg_tampon.split("\n"):
                evt = lire_evenement(ligne.strip())
                if evt is not None:
                    self._mg_etat.appliquer(evt)
            self._mg_tampon = ""
        self._mg_etat.en_cours = False
        self._mg_bouton_lancer.setEnabled(True)
        self._mg_bouton_finaliser.setEnabled(False)
        self._mg_bouton_finaliser_vite.setEnabled(False)
        self._mg_rafraichir()

    def _mg_rafraichir(self) -> None:
        from PyQt6.QtWidgets import QTableWidgetItem

        e = self._mg_etat
        lignes = sorted(e.lignes.values(), key=lambda li: li.graine)
        self._mg_table.setRowCount(len(lignes))
        for r, li in enumerate(lignes):
            for c, txt in enumerate((
                str(li.graine),
                li.etat,
                f"{li.seel:.4f}" if li.seel is not None else "--",
                str(li.n_blocs) if li.n_blocs is not None else "--",
                f"{100 * li.crash:.2f} %" if li.crash is not None else "--",
                f"{li.minutes:.0f} min" if li.minutes is not None else "--",
            )):
                self._mg_table.setItem(r, c, QTableWidgetItem(txt))
        self._mg_resume.setText(resumer(e))


def resumer(e: EtatMultigraine) -> str:
    """Le texte du bandeau. Fonction PURE, donc testable -- et c'est la phrase que 👤 lira
    pour decider d'arreter, elle doit dire ce que le chiffre vaut."""
    bouts = [f"{e.combien_trouvent()} realisation(s) ont trouve sur {len(e.lignes)}"]
    prov = e.meilleur_provisoire()
    if prov is not None:
        bouts.append(f"meilleur SEEL {prov:.4f} nm — PROVISOIRE, note sur sa propre graine")
    if e.plans_unis is not None:
        u = f"union : {e.plans_unis} plan(s)"
        if e.plans_ecartes:
            u += f", {e.plans_ecartes} ECARTE(S) par le plafond"
        bouts.append(u)
    if e.seel_final is not None:
        bouts.append(f"RESULTAT CITABLE {e.seel_final:.4f} nm, note sur une graine disjointe")
        av = e.avertissement_ecart()
        if av:
            bouts.append("⚠️ " + av)
    if e.motif_finalisation:
        bouts.append(f"arret : {e.motif_finalisation}")
    if e.non_essayees:
        bouts.append(f"⚠️ NON ESSAYEES faute de budget : {e.non_essayees}")
    return " · ".join(bouts)


__all__ = [
    "BRUIT_DIFFERENCE_SEEL_PCT",
    "CertusStratMultigraineMixin",
    "ECHELLE_GRAINES",
    "EtatMultigraine",
    "LigneGraine",
    "construire_arguments",
    "resumer",
]
