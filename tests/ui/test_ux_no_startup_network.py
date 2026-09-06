"""OUVRIR UNE FENETRE NE DOIT JOINDRE AUCUN RESEAU — etape 3.2.

📏 Mesure du 2026-09-06. `CertusTheme.apply_to_app()` — le point d'entree du theme, appele au
demarrage de **chaque** fenetre — appelait inconditionnellement `load_inter_font()`, qui
tentait deux `urllib.request.urlopen` vers `github.com` avec `timeout=2`.

Et rien de tout cela ne marchait plus :

    %APPDATA%/certus_fonts      existe, et il est VIDE (cree le 2026-09-04)
    les deux URL GitHub         HTTP 404 -- elles sont mortes

Le telechargement echouait donc **toujours**, rien n'etait jamais mis en cache, et il etait
**retente a chaque lancement**.

## 🔑 POURQUOI C'EST GRAVE ICI PLUS QU'AILLEURS

Le cout tombe sur la machine la plus susceptible d'etre hors ligne : **un poste de bati, en
salle**. Sans route reseau, c'est jusqu'a 2 s par fichier, deux fichiers, a chaque ouverture
de fenetre — et la suite en compte onze. Sur un poste connecte, le DNS resout et l'erreur
revient en 0,11 s, ce qui masque entierement le probleme. **Le defaut ne se voit que la ou il
fait mal.**

Un logiciel scientifique de production ne doit pas dependre d'un depot tiers pour dessiner sa
propre interface.

## Ce que ce fichier verrouille, et ce qu'il NE teste PAS

Il verifie **l'absence d'appel reseau**, ce qui est une propriete du CODE.

⚠️ Il ne teste **pas** quelle police est resolue. Le §3.2 du dossier le dit : le harnais
**epingle** `Segoe UI` depuis le correctif 0.1, donc toute mesure de police faite ici
decrirait la machine et non le projet. C'est l'erreur n° 4 du §5 de `CLAUDE.md` — une grandeur
qui ne varie pas avec ce qui devrait la faire varier.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


class TestAucunAppelReseauAuDemarrage:
    """🔴 CE TEST COMPTE LES APPELS. Il ne leve PAS depuis le faux `urlopen`, et c'est la
    seule forme qui marche ici.

    Une premiere version levait une exception depuis le piege. Elle aurait ete un FAUX
    NEGATIF : le code d'avant enveloppait le telechargement dans un `except Exception:
    pass`, donc il aurait **avale** l'exception et le test serait passe sur le code
    fautif -- un test incapable d'echouer, ce que le §12 de `CLAUDE.md` interdit
    explicitement. Compter l'appel echappe a toute clause `except`.
    """

    def test_la_resolution_de_police_ne_telecharge_rien(self, qapp, monkeypatch) -> None:
        import urllib.request

        from certus.ui.certus_theme import CertusTheme

        appels: list[tuple] = []

        def _piege(*args, **kwargs):
            appels.append(args)
            raise OSError("reseau coupe par le test")

        monkeypatch.setattr(urllib.request, "urlopen", _piege)
        famille = CertusTheme.load_inter_font()

        assert not appels, (
            f"load_inter_font a tente {len(appels)} acces reseau : {appels}. Le demarrage "
            "doit rester local — voir la docstring de la methode pour la chaine de repli."
        )
        assert famille in ("Inter", "Segoe UI"), f"famille inattendue : {famille!r}"

    def test_le_module_ne_cite_plus_aucune_url(self) -> None:
        """Un `urlopen` peut revenir sans passer par `urllib.request` — on regarde le texte.

        📏 Les deux URL mortes etaient
        `github.com/rsms/inter/raw/master/docs/font-files/Inter-{Regular,Bold}.ttf`.
        """
        import re
        from pathlib import Path

        chemin = Path(__file__).resolve().parents[2] / "certus" / "ui" / "certus_theme.py"
        source = chemin.read_text(encoding="utf-8")
        # On retire les docstrings et commentaires : ils DECRIVENT le defaut retire, et
        # les compter reviendrait a interdire d'expliquer ce qu'on a corrige. C'est la
        # meme lecon que le garde-fou du chevron (etape 3.8).
        sans_commentaire = re.sub(r"#[^\n]*", "", source)
        sans_docstring = re.sub(r'"""(?:.|\n)*?"""', "", sans_commentaire)
        urls = re.findall(r"https?://[^\s\"']+", sans_docstring)
        assert not urls, f"le theme cite encore des URL en dehors de sa documentation : {urls}"


class TestLeControleNegatif:
    """Le garde-fou saurait-il encore voir un telechargement ? Sinon il ne garde rien."""

    def test_il_attraperait_un_urlopen_reintroduit(self, monkeypatch) -> None:
        import urllib.request

        appels = []
        monkeypatch.setattr(
            urllib.request, "urlopen", lambda *a, **k: appels.append(a) or (_ for _ in ()).throw(OSError)
        )

        def _code_fautif():
            try:
                urllib.request.urlopen("https://example.invalid/x.ttf", timeout=2)
            except OSError:
                pass

        _code_fautif()
        assert appels, "le piege de monkeypatch ne voit plus les appels : il ne garde rien"
