"""L'audit de symboles morts doit chercher les appels LÀ OÙ ILS SONT.

🔴 CE QUI A ÉTÉ MESURÉ LE 2026-09-08. `lint.yml` lance
`tools/dead_symbol_audit.py --ci`, et ce job rendait **32 candidats non résolus**,
donc un rouge permanent. Sur les 32, **27 sont appelés depuis `certus/`** — l'arbre
que l'outil n'ouvrait jamais. Il collectait ses références dans le même périmètre
étroit que ses définitions : la racine plus `certus_physics/`.

🔑 **Un symbole n'est pas mort parce qu'on a regardé ailleurs.** Le périmètre des
*définitions* s'étend paquet par paquet après examen : racine, `certus_physics`,
`certus/metal`, `certus/spline`, `certus/core`, `certus/domain`, puis
`certus/physics`. Celui des *références* couvre
tout le code d'exécution : une référence compte d'où qu'elle vienne.

⚠️ **`tests/` reste dehors, et c'est voulu** : un symbole que seul un test appelle
est mort en production. L'y inclure masquerait exactement ce qu'on cherche.

📌 Ce que l'outil ne sait pas faire, et qu'il ne faut pas lui prêter : il apparie
par **nom nu**, pas par symbole qualifié. Un `dropEvent` défini dans une classe est
tenu pour vivant si une *autre* classe en appelle un. Il sous-signale donc, ce qui
est le bon sens d'erreur pour une barrière de CI — mais un vert ne prouve pas
l'absence de code mort.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "tools" / "dead_symbol_audit.py"
LISTE_BLANCHE = ROOT / "tools" / "dead_symbol_whitelist.txt"

#: Cinq symboles signalés « morts » le 2026-09-08, et le site qui les appelle.
#: Le fragment sert de contrôle d'auto-invalidation : si l'appel disparaît, c'est
#: le premier test qui casse, et non celui-ci qui passerait pour de mauvaises
#: raisons.
SITES_D_APPEL = {
    "certus_physics.structures:PGlobalConfig.for_index": (
        "certus/workers/certus_index_workers_opt_strat.py",
        "PGlobalConfig.for_index(",
    ),
    "certus_physics.structures:PGlobalConfig.for_local": (
        "certus/core/certus_design_worker_utils.py",
        "PGlobalConfig.for_local(",
    ),
    "CERTUS_METAL_SINGLE:CertusMetalSingleApp._setup_plots": (
        "certus/metal/certus_metal_common.py",
        "self._setup_plots()",
    ),
    "CERTUS_METAL_SINGLE:CertusMetalSingleApp._setup_parameter_grid": (
        "certus/metal/certus_metal_common.py",
        "self._setup_parameter_grid(",
    ),
    "CERTUS_METAL_SINGLE:CertusMetalSingleApp._warmup_numba": (
        "certus/ui/certus_base_app.py",
        "self._warmup_numba",
    ),
}


def _signale_sans_liste_blanche() -> set[str]:
    """Les candidats bruts, liste blanche neutralisée.

    On passe un chemin inexistant plutôt que la vraie liste : ce test porte sur ce
    que l'outil TROUVE, pas sur ce que le projet a décidé de tolérer.
    """
    out = subprocess.run(
        [sys.executable, str(AUDIT), "--whitelist", str(ROOT / "tools" / "_aucune_liste_blanche")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, f"l'audit ne s'exécute plus :\n{out.stderr}"
    return _candidats(out.stdout)


def _candidats(sortie: str) -> set[str]:
    """Les identifiants de symbole que l'audit liste dans sa sortie."""
    return {
        ligne.strip().removeprefix("- ").split(" (")[0]
        for ligne in sortie.splitlines()
        if ligne.strip().startswith("- ")
    }


def test_the_audit_exists_and_runs(tmp_path):
    """Contrôle négatif : un audit introuvable, ou qui ne signale plus rien, ferait passer tout le reste.

    Le symbole mort est PLANTÉ dans une arborescence jetable, à côté d'un symbole
    appelé : l'audit doit signaler l'un et taire l'autre. Le contrôle ne dépend donc
    pas du code mort que contient le projet — le périmètre des définitions peut
    n'en plus contenir aucun sans que l'audit ait cessé de
    mordre, et exiger d'y en trouver un ferait alors échouer ce test à tort.
    """
    assert AUDIT.is_file(), f"{AUDIT} est introuvable — lint.yml le lance pourtant"
    copie = tmp_path / "tools" / AUDIT.name
    copie.parent.mkdir()
    shutil.copy2(AUDIT, copie)
    (tmp_path / "CERTUS_SONDE.py").write_text(
        "def _sonde_morte():\n    return 0\n\n\ndef _sonde_vivante():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "CERTUS_APPELANT.py").write_text(
        "from CERTUS_SONDE import _sonde_vivante\n\nVALEUR = _sonde_vivante()\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(copie), "--whitelist", str(tmp_path / "aucune_liste_blanche")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, f"l'audit ne s'exécute plus :\n{out.stderr}"
    signales = _candidats(out.stdout)
    assert "CERTUS_SONDE:_sonde_morte" in signales, (
        "l'audit ne signale plus un symbole mort planté exprès : il ne mord plus, "
        "et un vert en CI ne voudrait plus rien dire"
    )
    assert "CERTUS_SONDE:_sonde_vivante" not in signales, (
        f"l'audit signale un symbole appelé : il mord au hasard — {sorted(signales)}"
    )


def test_an_aliased_import_counts_only_when_called(tmp_path):
    """Les imports renommés de SPLINE ne doivent ni cacher du mort ni créer un faux positif."""
    copie = tmp_path / "tools" / AUDIT.name
    copie.parent.mkdir()
    shutil.copy2(AUDIT, copie)
    (tmp_path / "CERTUS_SONDE.py").write_text(
        "def aliased_live():\n    return 1\n\n\ndef aliased_dead():\n    return 0\n",
        encoding="utf-8",
    )
    (tmp_path / "CERTUS_APPELANT.py").write_text(
        "from CERTUS_SONDE import aliased_live as _called, aliased_dead as _unused\n"
        "VALEUR = _called()\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(copie), "--whitelist", str(tmp_path / "aucune_liste_blanche")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    signales = _candidats(out.stdout)
    assert "CERTUS_SONDE:aliased_dead" in signales
    assert "CERTUS_SONDE:aliased_live" not in signales


def test_framework_validators_are_not_reported_as_dead(tmp_path):
    """Pydantic invokes decorated validators without an explicit Python call site."""
    copie = tmp_path / "tools" / AUDIT.name
    copie.parent.mkdir()
    shutil.copy2(AUDIT, copie)
    (tmp_path / "CERTUS_SONDE.py").write_text(
        "class Model:\n"
        "    @field_validator('x')\n"
        "    @classmethod\n"
        "    def normalize_field(cls, value):\n        return value\n\n"
        "    @model_validator(mode='after')\n"
        "    def normalize_model(self):\n        return self\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(copie), "--whitelist", str(tmp_path / "aucune_liste_blanche")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    signales = _candidats(out.stdout)
    assert "CERTUS_SONDE:Model.normalize_field" not in signales
    assert "CERTUS_SONDE:Model.normalize_model" not in signales


@pytest.mark.parametrize("package", ["spline", "core", "domain", "physics"])
def test_reviewed_package_definitions_enter_the_gate(tmp_path, package):
    """Un symbole mort d'un paquet contrôlé doit rendre un verdict ; un appel UI compte."""
    copie = tmp_path / "tools" / AUDIT.name
    copie.parent.mkdir()
    shutil.copy2(AUDIT, copie)
    sonde = tmp_path / "certus" / package / "probe.py"
    sonde.parent.mkdir(parents=True)
    sonde.write_text(
        "def reviewed_dead():\n    return 0\n\n\ndef reviewed_live():\n    return 1\n",
        encoding="utf-8",
    )
    appelant = tmp_path / "certus" / "ui" / "caller.py"
    appelant.parent.mkdir(parents=True)
    appelant.write_text(
        f"from certus.{package}.probe import reviewed_live as _live\nVALEUR = _live()\n",
        encoding="utf-8",
    )
    out = subprocess.run(
        [sys.executable, str(copie), "--whitelist", str(tmp_path / "aucune_liste_blanche")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    signales = _candidats(out.stdout)
    assert f"certus.{package}.probe:reviewed_dead" in signales
    assert f"certus.{package}.probe:reviewed_live" not in signales


def test_the_ci_step_passes():
    """Le verdict que `lint.yml` rend vraiment, rendu ICI aussi.

    🔴 Ce job était rouge en permanence — 32 candidats non résolus — et un job
    rouge en permanence n'est pas un garde-fou : personne ne le regarde.
    """
    out = subprocess.run(
        [sys.executable, str(AUDIT), "--ci", "--whitelist", str(LISTE_BLANCHE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, "des symboles morts ne sont ni corrigés ni justifiés :\n" + (out.stdout or out.stderr)


def test_the_whitelist_carries_no_fossil_entry():
    """Une exemption qui ne peut plus rien couvrir est une promesse que personne ne vérifie.

    📏 Le 2026-09-08 la liste en portait **64 pour 7 candidats** : 57 dataient d'un
    périmètre plus large et ne pouvaient plus rien apparier. Le risque n'est pas le
    désordre, c'est qu'une de ces lignes couvre en silence un symbole qui meurt
    plus tard.

    ⚠️ Ce test échoue aussi quand on RÉPARE quelque chose — c'est voulu : la
    réparation faite, l'exemption doit partir avec.
    """
    candidats = _signale_sans_liste_blanche()
    inscrits = {
        ligne.strip()
        for ligne in LISTE_BLANCHE.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.strip().startswith("#")
    }
    fossiles = sorted(inscrits - candidats)
    assert not fossiles, (
        f"{len(fossiles)} exemption(s) ne correspondent plus à aucun candidat — "
        f"retire-les de {LISTE_BLANCHE.name} : {fossiles}"
    )


def test_the_measured_call_sites_still_exist():
    """Auto-invalidation : si un appel a bougé, ce fichier a besoin d'être remesuré."""
    for symbole, (fichier, fragment) in SITES_D_APPEL.items():
        chemin = ROOT / fichier
        assert chemin.is_file(), f"{fichier} a disparu — le site d'appel de {symbole} est à remesurer"
        assert fragment in chemin.read_text(encoding="utf-8", errors="ignore"), (
            f"{fichier} ne contient plus « {fragment} » : le site d'appel de {symbole} "
            "a bougé, remesure-le avant de croire le test suivant"
        )


def test_a_symbol_called_from_the_application_is_not_reported():
    """Le vrai défaut : ces cinq-là sont appelés, et l'audit les disait morts."""
    signales = _signale_sans_liste_blanche()
    faux_positifs = sorted(SITES_D_APPEL.keys() & signales)
    assert not faux_positifs, (
        f"l'audit signale comme morts des symboles dont le site d'appel est vérifié juste au-dessus : {faux_positifs}"
    )


def test_the_reference_perimeter_covers_the_application_but_not_the_tests():
    """La propriété, sans passer par un nom qui se périme.

    ⚠️ `tests/` doit rester DEHORS : un symbole que seul un test appelle est mort
    en production, et l'inclure rendrait l'audit muet là où il sert.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from dead_symbol_audit import _iter_reference_files

    fichiers = _iter_reference_files(ROOT)
    zones = {p.relative_to(ROOT).parts[0] for p in fichiers if len(p.relative_to(ROOT).parts) > 1}

    assert "certus" in zones, f"le périmètre des références ignore certus/ — zones vues : {sorted(zones)}"
    assert "tests" not in zones, "les tests comptent comme des références : le code mort en production sera masqué"


def test_the_definition_perimeter_is_reviewed():
    """Le périmètre des DÉFINITIONS s'élargit paquet par paquet après examen.

    Le signaler ici évite qu'on « répare » le rouge en faisant les deux d'un coup —
    ce serait deux changements à la fois, et le résultat ne s'attribuerait pas.
    `certus/metal` y est entré le 2026-09-28 (D30), `certus/spline` et
    `certus/core`, `certus/domain` et `certus/physics` après examen des candidats D24 ;
    le reste attend son examen.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    from dead_symbol_audit import _iter_python_files

    fichiers = _iter_python_files(ROOT)
    zones = {
        "/".join(p.relative_to(ROOT).parts[:2]) if p.relative_to(ROOT).parts[0] == "certus" else p.relative_to(ROOT).parts[0]
        for p in fichiers
        if len(p.relative_to(ROOT).parts) > 1
    }

    assert zones == {"certus_physics", "certus/metal", "certus/spline", "certus/core", "certus/domain", "certus/physics"}, (
        f"le périmètre des définitions s'est élargi à {sorted(zones)} : c'est une décision "
        "de portée, pas un correctif de faux positif"
    )
