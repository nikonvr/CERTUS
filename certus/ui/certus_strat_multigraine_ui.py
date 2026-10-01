"""« Multi-realisation » TAB -- search over K seeds within a budget, and be able to stop.

## WHY THIS TAB, AND WHY IT COMPUTES NOTHING ITSELF

On `r75x2` at 2 nm, a seed finds or does not find. Measured on 2026-08-22, seven BARE seeds,
full range, no override: 42, 101, 202, 303 return **zero**; 77, 404 and 505 find, with SEELs
of 0.5692, 0.5599 and 0.6112 nm. The product answer is therefore to replay the same search
over several realisations.

🔑 **THIS TAB DRIVES `scripts/orchestre_multigraine.py`, IT DOES NOT REIMPLEMENT IT.** The rule
of disjoint seeds, the round-robin union, the time cap, the writing of the artefacts -- all of
it lives in the script, is tested there, and exists in one single place. Two code paths would
end up diverging, and that is a bill this repository has already paid.

🔴 **AND THE DRIVING GOES THROUGH SEPARATE PROCESSES, WHICH IS NOT AN IMPLEMENTATION DETAIL.**
`certus_strat_workers.py` forces `max_workers = 1` with the reason "prevent Numba CPU
oversubscription and deadlocks". A numba deadlock is INTRA-process: launching K searches in
distinct processes sidesteps the danger instead of braving it. It is also what keeps the
interface alive during hours of computation.

## WHAT THE USER SEES, AND THE CAVEAT THAT TRAVELS WITH IT

The SEEL announced during the campaign is **PROVISIONAL**: it is measured on the seed that
found it. The quotable figure comes from the final scoring on a **disjoint** seed. The gap is
the channel of the winner's curse -- **+12.9 %** on 2026-08-15, **+0.55 %** on 2026-08-22. It is
therefore not a constant, and the "provisional" column of the table exists so that nobody
quotes the wrong number.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
_SCRIPTS = RACINE / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

#: 🔑 The event format is IMPORTED from the emitter, never copied. A format whose
#: writing and reading live in two files drifts at the first change.
from orchestre_multigraine import (  # noqa: E402
    ECHELLE_GRAINES,
    GRAINE_NOTATION_DEFAUT,
    lire_evenement,
)
from probe_blocs_vs_plantage import COMPOSANTS  # noqa: E402


def interpreteur_et_script() -> tuple[str | None, str]:
    """The interpreter to launch and the reason for a refusal. Returns (None, reason) if impossible.

    🔴 IN FROZEN MODE, NONE OF THIS WORKS, AND IT MUST BE SAID INSTEAD OF FAILING
    STRANGELY. `certus_hub.spec` produces a PyInstaller executable; in that bundle
    `sys.executable` is `CERTUS_HUB.exe` and not a python, `__file__` points into a temporary
    extraction folder, and `scripts/` is not bundled at all. Launching
    `sys.executable scripts/orchestre_multigraine.py` there would give an incomprehensible error.

    ⚠️ The proper repair would be to bundle the script and find an interpreter; it is not
    done, and it cannot be tried without building a bundle. So this DETECTS, and refuses
    saying why.
    """
    if getattr(sys, "frozen", False):
        return None, (
            "🔴 The multi-seed search is not available in the COMPILED build: it starts "
            "separate processes from `scripts/`, which is not bundled. Run CERTUS from "
            "the sources to use it."
        )
    script = RACINE / "scripts" / "orchestre_multigraine.py"
    if not script.is_file():
        return None, f"🔴 script not found: {script}"
    return sys.executable, ""

#: The noise on a DIFFERENCE of SEEL, measured on this repository. Used to say whether
#: a provisional -> final gap is significant or not.
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
    """The state machine of the tab -- PURE, without Qt, hence testable without a screen.

    🔑 It is separated from the view deliberately. Display logic locked inside a widget can
    only be tested by opening a window, and this repository has already measured what a
    graphical bench costs (QApplication collected by the GC, modal dialogs, dead `_is_busy`).
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
        """Consumes an event of the `[ORCH]` stream. Ignores what it does not know.

        ⚠️ Ignoring the unknown is INTENDED: an event added to the script later must not
        bring down an interface that has been running for six hours.
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
            # 🔑 The provisional value is kept AS THE SCRIPT SAW IT, not as the view
            # recomputes it: that value decided the stop, and the published gap must be about
            # that figure. Recomputing them here would make them diverge silently.
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
        """The best SEEL announced during the campaign. 🔴 PROVISIONAL: each value is
        measured on the seed that found it, and they are not strictly comparable with one
        another. It is displayed as a MARKER to decide when to stop, never as a
        result."""
        vus = [li.seel for li in self.lignes.values() if li.seel is not None]
        return min(vus) if vus else None

    def combien_trouvent(self) -> int:
        return sum(1 for li in self.lignes.values() if li.deposables > 0)

    def ecart_provisoire_final_pct(self) -> float | None:
        """The winner's-curse channel, measured on THIS campaign."""
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
    """The component name the probe expects, deduced from the file LOADED in the application.

    🔴 THIS FUNCTION EXISTS BECAUSE THE FIRST VERSION OF THE TAB HARD-CODED "r75x2".
    The user could load any component: the tab would have searched on ANOTHER one, and
    returned a perfectly plausible SEEL about a stack that is not the one displayed. That
    is the mistake this repository fears most -- "a silent error does not crash: it
    produces a wrong result that looks right, and someone manufactures a part with it"
    (CLAUDE.md).

    Returns None if the file matches no entry of `COMPOSANTS` -- and the caller must then
    REFUSE, never choose in the user's place.
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
    # Fall back on the file name: a repository cloned elsewhere, or a relative path,
    # must not lose the match.
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
    """The command line, built in ONE place and testable without starting Qt.

    🔴 `--evenements` is ALWAYS set: it is how the interface knows what is happening.
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
# THE VIEW -- thin by construction: it displays the state above and drives a QProcess.
# =========================================================================================

class CertusStratMultigraineMixin:
    """« Multi-realisation » tab. Mixed into `CertusStratApp`."""

    def _create_multigraine_tab(self) -> None:
        from PyQt6.QtCore import QProcess, Qt
        from PyQt6.QtWidgets import (
            QAbstractItemView,
            QComboBox,
            QGridLayout,
            QHeaderView,
            QLabel,
            QLineEdit,
            QPushButton,
            QTableWidget,
            QVBoxLayout,
            QWidget,
        )

        from certus.ui.certus_ui_widgets_cards import CertusCard

        self._mg_etat = EtatMultigraine()
        self._mg_proc: QProcess | None = None
        self._mg_tampon = ""

        onglet = QWidget()
        self.tabs.addTab(onglet, "Multi-seed")
        v = QVBoxLayout(onglet)
        v.setSpacing(10)
        v.setContentsMargins(5, 5, 5, 5)

        # -- reglages ---------------------------------------------------------------------
        carte = CertusCard("Budget and objective")
        # 🔴 THE COMPONENT IS EXPLICIT, AND WITHOUT A SILENT DEFAULT. The first version
        # hard-coded "r75x2": the user could have loaded an entirely different stack and
        # the tab would have returned a plausible SEEL about something else.
        self._mg_composant = QComboBox()
        self._mg_composant.addItem("")
        self._mg_composant.addItems(sorted(COMPOSANTS))
        self._mg_composant.setToolTip(
            "The component to search. Pre-selected from the one you loaded, when it matches "
            "a known entry.\n🔴 Without an explicit choice, the search is REFUSED."
        )
        _pre = composant_depuis_fichier(getattr(self, "_last_config_file", None))
        if _pre:
            self._mg_composant.setCurrentText(_pre)
        self._mg_budget = QLineEdit("2h")
        self._mg_budget.setToolTip(
            "Maximum duration: 2h · 90m · 1h30 · nuit (10 h).\n"
            "The last one is a keyword of the runner, not a label: type it as it stands.\n"
            "The budget governs what is STARTED, never what is stopped: a run already in "
            "flight is left to finish, because a run cut short is a measurement destroyed."
        )
        self._mg_objectif = QComboBox()
        # 🔴 THE LABEL IS ENGLISH, THE VALUE STAYS FRENCH. The `--objectif` flag of
        # `orchestre_multigraine.py` only accepts two French tokens: renaming the
        # entries would make argparse reject the command line.
        self._mg_objectif.addItem("first to find", "premier")
        self._mg_objectif.addItem("best within budget", "meilleur")
        self._mg_objectif.setToolTip(
            "first to find: stop as soon as one run succeeds -- the fastest.\n"
            "best within budget: spend the whole budget, then merge everything.\n"
            "⚠️ The three seeds that succeed spread from 0.5599 to 0.6112 nm, i.e. 9.2 %: "
            "stopping at the first one can cost that much."
        )
        self._mg_cible = QLineEdit("")
        self._mg_cible.setPlaceholderText("ex. 0.57")
        self._mg_cible.setToolTip(
            "Stop as soon as one run reaches a SEEL <= this value, in nm.\n"
            "Leave empty to arm no target."
        )
        self._mg_slots = QLineEdit("2")
        self._mg_slots.setToolTip(
            "Concurrent searches, in SEPARATE processes.\n"
            "Measured 2026-08-22 on 16 threads: two concurrent runs give +29 % throughput, "
            "not +100 % -- the bottleneck is memory bandwidth."
        )
        # QGridLayout with 2 columns (label | widget): avoids the ~870 px minimum of the
        # QHBoxLayout with 5 pairs in a row, which caused horizontal scrolling at 1366x768.
        g = QGridLayout()
        g.setColumnStretch(1, 1)
        for _row, (lib, w) in enumerate((("Component:", self._mg_composant),
                                         ("Budget:", self._mg_budget),
                                         ("Objective:", self._mg_objectif),
                                         ("Target SEEL (nm):", self._mg_cible),
                                         ("Slots:", self._mg_slots))):
            g.addWidget(QLabel(lib), _row, 0)
            g.addWidget(w, _row, 1)
        carte.body.addLayout(g)
        v.addWidget(carte)

        # -- buttons ----------------------------------------------------------------------
        # QVBoxLayout: the three labels are too long to share one line without imposing
        # a ~825 px minimum on the panel.
        barre = QVBoxLayout()
        self._mg_bouton_lancer = QPushButton("Start the search")
        self._mg_bouton_lancer.setToolTip(
            "Replays the search over several seeds within a given time budget."
        )
        self._mg_bouton_lancer.clicked.connect(self._mg_lancer)
        # 🔑 THE WORD IS "FINALISE", NOT "STOP", AND 👤 FOUND IT: "rather than stop, the
        # real word would be finalise". "Stop" says what is LEFT and reads as "cancel
        # everything"; yet both buttons produce the quotable figure -- they only differ by
        # the fate of the realisations IN FLIGHT. The right word says what is OBTAINED.
        self._mg_bouton_finaliser = QPushButton("Finalise (let runs finish)")
        self._mg_bouton_finaliser.setEnabled(False)
        self._mg_bouton_finaliser.setToolTip(
            "Stops STARTING new runs, LETS the running ones FINISH, then moves on to the "
            "merge and the final scoring.\nNothing is wasted — but you must wait for the "
            "runs still in flight."
        )
        self._mg_bouton_finaliser.clicked.connect(lambda: self._mg_finaliser("attendre"))

        self._mg_bouton_finaliser_vite = QPushButton("Finalise now")
        self._mg_bouton_finaliser_vite.setEnabled(False)
        self._mg_bouton_finaliser_vite.setToolTip(
            "Moves to the merge and the final scoring IMMEDIATELY, on what is already measured.\n"
            "⚠️ Runs in flight are killed and their work is LOST — four 91-minute measurements "
            "went that way on 2026-08-22, cut at 98.9 % of their progress."
        )
        self._mg_bouton_finaliser_vite.clicked.connect(lambda: self._mg_finaliser("abandonner"))

        barre.addWidget(self._mg_bouton_lancer)
        barre.addWidget(self._mg_bouton_finaliser)
        barre.addWidget(self._mg_bouton_finaliser_vite)
        v.addLayout(barre)

        # -- tableau vivant ---------------------------------------------------------------
        self._mg_table = QTableWidget(0, 6)
        self._mg_table.setHorizontalHeaderLabels(
            ["Seed", "Status", "SEEL (nm)", "Blocks", "Crash rate", "Duration"]
        )
        self._mg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # A results table: the operator reads and sorts it (best SEEL first, say), never types in it.
        # The refresh rewrites every cell from the state, so an edit would be lost at the next event.
        self._mg_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Seeds in increasing order until the operator picks another column: enabling the sort
        # applies the header's current indicator, and Qt's default is descending.
        self._mg_table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self._mg_table.setSortingEnabled(True)
        v.addWidget(self._mg_table, 1)

        # Empty at construction: `_mg_rafraichir` just below writes it at once.
        # The previous version put a paragraph here that was overwritten before being seen.
        self._mg_resume = QLabel("")
        self._mg_resume.setWordWrap(True)
        v.addWidget(self._mg_resume)
        self._mg_rafraichir()

    # -- pilotage -------------------------------------------------------------------------

    def _mg_objectif_courant(self) -> str:
        """The token the script accepts, not the label the operator reads."""
        return self._mg_objectif.currentData() or "premier"

    def _mg_lancer(self) -> None:
        from PyQt6.QtCore import QProcess

        try:
            cible = float(self._mg_cible.text().replace(",", ".")) if self._mg_cible.text().strip() else None
            slots = int(self._mg_slots.text())
        except ValueError:
            self._mg_resume.setText("🔴 Target SEEL or slot count unreadable.")
            return

        py, motif = interpreteur_et_script()
        if py is None:
            self._mg_resume.setText(motif)
            return

        composant = self._mg_composant_courant()
        if composant is None:
            # 🔴 REFUSE, DO NOT GUESS. Searching on a component 👤 did not designate would
            # return a perfectly plausible SEEL about another stack.
            self._mg_resume.setText(
                "🔴 Pick a COMPONENT before starting. No default is applied: searching a "
                "stack you did not name would return a SEEL that is plausible and wrong."
            )
            return

        args = construire_arguments(
            composant=composant,
            budget=self._mg_budget.text().strip() or "2h",
            objectif=self._mg_objectif_courant(),
            seel_cible=cible,
            slots=slots,
        )
        self._mg_python = py
        self._mg_demarrer_processus(args)

    _mg_python: str = sys.executable

    def _mg_demarrer_processus(self, args: list[str]) -> None:
        """The seam. 🔑 It exists so that the WHOLE chain -- start-up, standard output,
        decoding, state machine, table -- is proven by a test instead of being assumed.
        Without it, the only way to check the driving would be to launch a real campaign of
        several hours, so nobody would do it."""
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
        """The component to search: the one the user CHOSE in the list.

        🔴 Returns None if nothing is chosen, and the caller REFUSES to launch. There is
        deliberately no default value: searching on a component the user did not
        designate would return a plausible SEEL about another stack.
        """
        nom = self._mg_composant.currentText().strip()
        return nom if nom in COMPOSANTS else None

    def _mg_finaliser(self, mode: str = "attendre") -> None:
        """🔑 A FILE IS DROPPED, NOTHING IS KILLED from the interface -- and its CONTENT says
        the mode. 👤: "if we click on stop, we do not have to finish right away, we can
        move on to step 3".

        BOTH modes lead to step 3, the union then the final scoring. What separates them
        is the fate of the realisations in flight:

            attendre    they are left to finish     nothing is lost, but we wait
            abandonner  they are killed             step 3 at once, their work is lost
        """
        if not self._mg_etat.drapeau:
            # 🔴 AN ACTIVE BUTTON THAT DOES NOTHING IS WORSE THAN A GREYED ONE. This case
            # should no longer happen -- the script announces its flag within the first second --
            # but if it did, 👤 must know it rather than believe the stop was requested.
            self._mg_resume.setText(
                "🔴 Cannot finalise yet: the campaign has not announced its finalisation "
                "point. Try again in a moment."
            )
            return
        Path(self._mg_etat.drapeau).write_text(
            "abandonner" if mode == "abandonner" else "", encoding="utf-8"
        )
        self._mg_bouton_finaliser.setEnabled(False)
        self._mg_bouton_finaliser_vite.setEnabled(False)
        self._mg_resume.setText(
            "⏹ FINALISATION requested — runs in flight are KILLED; the merge and the scoring "
            "on a disjoint seed follow immediately."
            if mode == "abandonner" else
            "⏹ FINALISATION requested — runs in flight are left to finish, then the merge and "
            "the scoring on a disjoint seed produce the quotable figure."
        )

    def _mg_sur_sortie(self) -> None:
        brut = bytes(self._mg_proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._mg_tampon += brut
        # ⚠️ Only COMPLETE lines are split: a JSON event cut in two by the boundary
        # of a chunk would be unreadable, and `lire_evenement` would return None
        # silently.
        *lignes, self._mg_tampon = self._mg_tampon.split("\n")
        for ligne in lignes:
            evt = lire_evenement(ligne.strip())
            if evt is not None:
                self._mg_etat.appliquer(evt)
        self._mg_rafraichir()

    def _mg_sur_fin(self) -> None:
        # 🔴 THE PIPE IS DRAINED BEFORE CONCLUDING. `finished` can arrive while a last
        # chunk has not been read: without this draining, the `resultat` and `fin` events --
        # hence THE QUOTABLE FIGURE -- would be lost, and the interface would show a
        # provisional value as if it were final. That is the worst possible direction for a loss.
        try:
            self._mg_sur_sortie()
        except (RuntimeError, AttributeError):
            pass
        # ⚠️ And the remainder can carry SEVERAL lines, the last one without a newline --
        # a process killed while writing leaves one. 📏 My first version treated the whole
        # buffer as ONE line: the JSON became unreadable and the events were lost all
        # together. A test found it, not a review.
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
        from certus.ui.certus_ui_widgets_utils import SortKeyItem

        e = self._mg_etat
        lignes = sorted(e.lignes.values(), key=lambda li: li.graine)
        # The cells are written one at a time: with the sort live, the first cell of a row would
        # send it elsewhere and the next five would land in another seed's row. Re-enabling the
        # sort at the end applies the column and the order the operator had picked.
        self._mg_table.setSortingEnabled(False)
        self._mg_table.setRowCount(len(lignes))
        for r, li in enumerate(lignes):
            for c, (txt, cle) in enumerate((
                (str(li.graine), li.graine),
                (ETAT_AFFICHE.get(li.etat, li.etat), None),
                (f"{li.seel:.4f}" if li.seel is not None else "--", li.seel),
                (str(li.n_blocs) if li.n_blocs is not None else "--", li.n_blocs),
                (f"{100 * li.crash:.2f} %" if li.crash is not None else "--", li.crash),
                (f"{li.minutes:.0f} min" if li.minutes is not None else "--", li.minutes),
            )):
                self._mg_table.setItem(r, c, SortKeyItem(txt, cle))
        self._mg_table.setSortingEnabled(True)
        self._mg_resume.setText(resumer(e))


#: The states are INTERNAL tokens of a pure state machine, pinned BY VALUE
#: in tests/unit/test_strat_multigraine_ui.py. They are therefore translated at
#: DISPLAY time rather than renamed: a label is not a value.
ETAT_AFFICHE: dict[str, str] = {
    "en attente": "waiting",
    "en cours": "running",
    "trouve": "found",
    "rien": "nothing found",
    "deja mesuree": "already measured",
    "non essayee": "not tried",
}


def resumer(e: EtatMultigraine) -> str:
    """The banner text. PURE function, hence testable -- and it is the sentence 👤 will read
    to decide when to stop, so it must say what the figure is worth.

    The RENDERED TEXT is in English, like the rest of the interface; the identifiers of
    this module stay French, because tests and the script's flags pin them.

    The former first sentence said "N realisation(s) ont trouve": a plural verb on a
    count that very often equals 1, and it is the most watched figure of the tab.
    """
    bouts: list[str] = []
    if e.lignes:
        trouves = e.combien_trouvent()
        bouts.append(f"{trouves} seed{'' if trouves == 1 else 's'} found out of {len(e.lignes)}")
    prov = e.meilleur_provisoire()
    if prov is not None:
        bouts.append(f"best SEEL {prov:.4f} nm — PROVISIONAL, scored on its own seed")
    if e.plans_unis is not None:
        u = f"merge: {e.plans_unis} plan(s)"
        if e.plans_ecartes:
            u += f", {e.plans_ecartes} DISCARDED by the cap"
        bouts.append(u)
    if e.seel_final is not None:
        bouts.append(f"QUOTABLE RESULT {e.seel_final:.4f} nm, scored on a disjoint seed")
        av = e.avertissement_ecart()
        if av:
            bouts.append("⚠️ " + av)
    if e.motif_finalisation:
        bouts.append(f"stopped: {e.motif_finalisation}")
    if e.non_essayees:
        bouts.append(f"⚠️ NOT TRIED for lack of budget: {e.non_essayees}")
    if not bouts:
        # Nothing has been announced yet: say what the figure will be worth, rather
        # than "0 of 0". ⚠️ The condition is on `bouts`, NOT on `e.lignes`: a campaign
        # can announce a union or a stop reason without any seed line existing, and a
        # first version swallowed them all.
        return (
            "The SEEL shown during a campaign is PROVISIONAL: it is measured on the very "
            "seed that found it. The quotable figure comes from the final scoring, on a "
            "disjoint seed."
        )
    return " · ".join(bouts)


__all__ = [
    "BRUIT_DIFFERENCE_SEEL_PCT",
    "ECHELLE_GRAINES",
    "CertusStratMultigraineMixin",
    "EtatMultigraine",
    "LigneGraine",
    "construire_arguments",
    "resumer",
]
