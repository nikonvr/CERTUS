# Prompts pour Claude Code — CERTUS

Trois sessions distinctes, dans cet ordre. **Une session = un sujet** : la politique
zéro régression du projet interdit de tout enchaîner d'un coup.

Lancement :

```
cd "D:\drivefl\couches minces 2026\CERTUS\0108"
claude
```

---

## Session 1 — Sécuriser le travail en cours ⚠️ à faire en premier

> À faire de votre côté avant de lancer : **révoquer la clé API Anthropic** sur
> console.anthropic.com. Elle est exposée depuis le 3 juillet sur le dépôt public.

```
Lis CLAUDE.md, en particulier la section 5.4 sur l'état git.

J'ai 130 fichiers modifiés non commités depuis 3 semaines, sur un dossier
synchronisé cloud — je veux sécuriser ça avant toute autre chose.

Étape 1 — hygiène du dépôt :
- Ajoute à .gitignore : .env, desktop.ini, .coverage, *.log, *.jsonl,
  MagicMock/, __pycache__/, .venv/
- git rm --cached sur les 69 desktop.ini trackés
- Supprime les refs git cassées nommées desktop.ini (git for-each-ref puis
  git update-ref -d). Vérifie ensuite que git log --all fonctionne correctement.

Étape 2 — analyse avant de committer :
- Classe les 130 fichiers modifiés par thème (physique / UI / workers / tests /
  config) et présente-moi le tableau.
- Signale les 3 fichiers supprimés non commités (certus_opt_gradients.py,
  certus_opt_gradients_compat.py, test_strict_material_substrate_boundary.py) :
  suppression volontaire ou accident ? Vérifie qu'aucun code vivant ne les importe.
- Signale tout fichier non suivi qui devrait l'être (certus/core/certus_lazy_imports.py,
  certus_performance.py, certus/utils/certus_copy_utils.py, etc.)

Étape 3 — commits :
- Propose-moi un découpage en commits thématiques avec les messages.
- Attends ma validation avant chaque commit. Ne pousse rien.

Ne touche pas au .env pour l'instant : la purge de l'historique se fera séparément,
après révocation de la clé.
```

---

## Session 2 — Corriger le bug de signe TMM

```
Lis CLAUDE.md section 5.1 : bug de convention de signe dans le TMM monocouche.

Avant de corriger, je veux que tu vérifies toi-même le diagnostic — n'accepte ni
les marqueurs LOCKED ni les docstrings comme preuve, ils affirment précisément
ce qui est faux ici.

1. Écris une référence TMM indépendante (matrice caractéristique Macleod,
   n̂ = n − ik, δ = k₀·n̂·d) et confirme que
   certus/physics/certus_tmm_matrix.py:19 renvoie bien cos/sin(φr + i·φi)
   au lieu de cos/sin(φr − i·φi).

2. Confirme que les deux appelants divergent :
   - certus_tmm_oblique.py:160 et :550 passent phi.imag signé → correct
   - certus_tmm_single_layer.py:41 passe une grandeur positive → faux si k > 0

3. Applique le correctif ligne 41 (phi_i = -k * n_film_imag * thickness_nm)
   et corrige dans le même commit l'assertion qui verrouille le mauvais signe :
   tests/core/test_certus_physics_tmm.py:56 → assert cos2_i < 0.0
   La convention correcte donne +sin(π/2)·sinh(1) = +1,175, donc positif.

4. Ajoute un test de non-régression comparant à la référence analytique sur
   k ∈ {0 ; 0,05 ; 3,0} et un cas métal (n=0,15 k=3,5). Le test doit échouer
   avec l'ancien signe.

5. Lance pytest sur tests/core/, tests/unit/ et tests/property/ avant de rendre.

Attention : calculate_transmission_single inclut délibérément la réflexion de face
arrière. Ses écarts avec un TMM nu sont légitimes — ne les corrige pas.
```

---

## Session 3 — Remettre la CI en état de servir

```
Lis CLAUDE.md section 5.3.

Le projet a 226 fichiers de tests et 2240 tests, la CI n'en exécute que 3 fichiers.
Et lint.yml ne surveille que main, qui a 137 commits de retard sur la branche
de travail.

1. Modifie .github/workflows/lint.yml pour :
   - se déclencher aussi sur refactor-corridors-mixins
   - exécuter la suite complète : pytest tests/ -q --no-cov
   Propose une stratégie si la suite est trop lente (marqueurs slow/performance
   déjà déclarés dans pyproject.toml — utilise-les plutôt que d'exclure au hasard).

2. Le projet a une recette d'environnement Linux validée (CLAUDE.md §4) avec
   Python 3.14.5, PyQt6 6.11.0 en offscreen et numba 0.66.0. Utilise-la pour
   faire tourner les tests sur ubuntu-latest plutôt que sur windows-latest,
   c'est bien plus rapide. Les libs système nécessaires sont listées dans le
   CLAUDE.md.

3. Fais tourner la suite localement d'abord et donne-moi le nombre d'échecs
   avant de toucher au workflow — inutile de brancher une CI sur une suite rouge.

Ne modifie pas release-windows.yml : le build gelé et la vérification des hashs
du lockfile sont corrects, je ne veux pas y toucher.
```

---

## Plus tard

| Sujet | Prompt d'amorce |
|-------|-----------------|
| `__all__` cassés | « Corrige les 202 F822 sur les 4 fichiers UI listés dans CLAUDE.md §5.2, puis retire F822 de l'extend-ignore du pyproject. » |
| Imports morts | « Nettoie les F401 répertoire par répertoire, avec revue de diff. Jamais de --fix global. » |
| Cycles de couches | « Déplace les DTO de certus/workers vers certus/domain pour casser le cycle core ↔ workers (CLAUDE.md §2). » |
| Racine encombrée | « Archive les 58 rapports .md dans docs/archive/ et les 29 scripts jetables dans scripts/legacy/. » |
