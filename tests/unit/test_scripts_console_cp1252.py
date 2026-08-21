"""AUCUN SCRIPT NE DOIT POUVOIR PERDRE UNE MESURE SUR UN print().

WHY THIS EXISTS, AND IT COST A REAL MEASUREMENT.

The Windows console is cp1252. A script that prints a single character outside that codepage
raises UnicodeEncodeError -- and it raises it AT THE END, while writing its summary, after the
measurement has been computed. The run looks complete; nothing is saved.

Measured 2026-08-21, three failures in one session:

    coherence_md.py            a green pastille, on the last summary line
    recaler_renvois.py         an arrow, on its FIRST output line -- so the tool had been
                               written and NEVER SEEN WORKING, because the only trial had
                               landed on the "nothing to do" branch, which also raised
    probe_blocs_vs_plantage.py a red pastille in synthese() -- and this one DESTROYED the
                               artifact of a fifty-minute run, because the summary printed
                               BEFORE the artifact was written

The third one is the whole point. A crash in a cosmetic print must never be able to lose a
measurement, and the fix has two halves: protect the console (this test), and write the
artifact before the summary (`probe_blocs_vs_plantage.py`).

The sweep found the problem was systemic, not anecdotal: 62 of the 66 scripts printing
non-cp1252 characters were unprotected.

WHY A LIBRARY IS EXEMPT. A module reconfigures nothing: mutating the caller's `sys.stdout` on
import is a hidden side effect. Its prints are covered by whichever script imports it, and
that script is protected by this rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"

def _hors_cp1252(src: str) -> bool:
    """Un caractere de `src` est-il inencodable en cp1252 ? TESTE, jamais devine.

    🔴 PREMIERE VERSION FAUSSE, ET C'EST INSTRUCTIF. Elle comparait a un seuil, `ord(c) > 0x2500`,
    choisi parce que les pastilles et les emoji sont au-dessus. 📏 Le controle negatif de ce
    fichier l'a refute en une seconde : la fleche `→` vaut 8594, donc SOUS le seuil, et
    elle n'est pas davantage encodable en cp1252. C'est precisement le caractere qui avait fait
    plantant `recaler_renvois.py`.

    Le seuil manquait 1 script sur 66. Le test exact ne peut pas se tromper -- il pose la
    question a l'encodeur.
    """
    for c in set(src):
        try:
            c.encode("cp1252")
        except UnicodeEncodeError:
            return True
    return False


def _scripts_a_risque() -> list[Path]:
    """Les scripts EXECUTABLES qui impriment hors cp1252. Les bibliotheques sont exclues."""
    out = []
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name.startswith("_"):
            continue
        if _hors_cp1252(f.read_text(encoding="utf-8")):
            out.append(f)
    return out


#: ⚠️ La forme exacte n'est pas imposee : `coherence_md.py` boucle sur `(stdout, stderr)` et
#: appelle `_flux.reconfigure(...)`, ce qui est plutot mieux. On cherche donc l'APPEL, pas une
#: ligne litterale -- sinon le test refuserait une implantation superieure a celle qu'il attend.
_MARQUE = ".reconfigure(encoding="


def _est_protege(src: str) -> bool:
    return _MARQUE in src


@pytest.mark.parametrize("script", _scripts_a_risque(), ids=lambda p: p.name)
def test_un_script_qui_imprime_hors_cp1252_protege_sa_console(script: Path):
    """Deux lignes, en tete de module. Sinon la mesure meurt sur son dernier print()."""
    src = script.read_text(encoding="utf-8")
    assert _est_protege(src), (
        f"{script.name} imprime des caracteres hors cp1252 sans proteger sa console.\n"
        f"Ajoute, apres les imports :\n"
        f'    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
        f'    sys.stderr.reconfigure(encoding="utf-8", errors="replace")\n'
        f"Sans cela, UnicodeEncodeError levera A LA FIN du run, apres la mesure."
    )


class TestLaProtectionEstAuBonEndroit:
    """Protegee trop tard, elle ne protege pas les print() qui la precedent."""

    @pytest.mark.parametrize("script", _scripts_a_risque(), ids=lambda p: p.name)
    def test_elle_precede_tout_print_du_module(self, script: Path):
        src = script.read_text(encoding="utf-8")
        lignes = src.splitlines()
        ligne_protection = next(
            (i for i, ln in enumerate(lignes) if _MARQUE in ln), None
        )
        assert ligne_protection is not None, f"{script.name} n'est pas protege"

        tree = ast.parse(src)
        premiers_prints = [
            n.lineno - 1
            for n in tree.body
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name)
            and n.value.func.id == "print"
        ]
        if premiers_prints:
            assert ligne_protection < min(premiers_prints), (
                f"{script.name} : la protection est ligne {ligne_protection + 1} mais un "
                f"print() du module la precede ligne {min(premiers_prints) + 1}"
            )


class TestLeControleNegatif:
    """L'outil sait-il seulement detecter ? Sinon il rassure sans rien garder."""

    def test_il_repere_un_script_a_risque(self):
        assert _scripts_a_risque(), (
            "aucun script a risque trouve : soit le balayage est casse, soit le seuil "
            "cp1252 ne correspond a rien"
        )

    def test_il_refuserait_un_script_non_protege(self):
        assert not _est_protege('print("\U0001f534 une pastille rouge")\n')

    def test_il_accepterait_le_meme_protege(self):
        assert _est_protege(
            'import sys\n'
            'sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n'
            'print("\U0001f534 une pastille rouge")\n'
        )

    def test_il_accepte_la_forme_en_boucle(self):
        """`coherence_md.py` protege stdout ET stderr par une boucle. C'est valide, et mieux."""
        assert _est_protege(
            "\n".join([
                "for _flux in (sys.stdout, sys.stderr):",
                '    _flux.reconfigure(encoding="utf-8", errors="replace")',
            ])
        )

    def test_les_accents_ne_sont_PAS_comptes_a_risque(self):
        """Ils existent en cp1252 : rien a proteger pour eux."""
        for c in "éàçèûœ—«»°":
            assert not _hors_cp1252(c), f"{c!r} serait compte a tort comme a risque"

    def test_les_pastilles_ET_LES_FLECHES_sont_comptees(self):
        """🔴 La fleche est le cas qui a REFUTE la premiere version, celle a seuil.

        `→` vaut 8594, donc SOUS le seuil 0x2500 = 9472 que j'avais choisi -- et elle
        n'est pas encodable en cp1252 pour autant. Le seuil manquait 1 script sur 66.
        """
        for c in "🔴🟢→📏─":
            assert _hors_cp1252(c), f"{c!r} devrait etre compte comme a risque"
