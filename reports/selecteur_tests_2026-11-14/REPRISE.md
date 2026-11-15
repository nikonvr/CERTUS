# Reprise — Chantier 19 (sélecteur de tests)

Révisée le 2026-11-14 après audit contradictoire. Tenir ce fichier à jour à chaque étape ; il n'est jamais commité et
ne se supprime qu'à la toute fin (étape 6).

## 1. État de `master` (`ac191592`)

- Chantiers **21(a)** et **07** fusionnés. `validate_parallel.py` → `VALIDATION=GO` sur `723674f4`. L'écart
  `723674f4..ac191592` ne contient que `reports/chantier07_amorcage_2026-11-14/` (bilan et `probe_cold_start.py`).
- Un worktree secondaire existe : `.claude/worktrees/claude-code-suije-bf4f1f` (branche
  `claude/claude-code-suije-bf4f1f`). Il porte, **non commités** à l'écriture de ce fichier : les corrections de
  `docs/CHANTIERS_RESTANTS.md` (chantiers 34 à 42, décisions de 👤, préalable C20), une phrase de `docs/ETAT.md` §6 et
  `reports/audit_general_2026-11-14/bilan.md`. Les fusionner dans `master` avant l'étape 5.
- 93 commits non poussés ; pousser ou faire un bundle reste une décision de 👤.

## 2. Acquis (`reports/selecteur_tests_2026-11-14/runs/`)

- `control.json` : `"green": true` sur `ac191592`, cinq paliers pytest (ni ruff ni contrôles documentaires).
  **Le palier `unit` n'est pas propre** : `test_the_slit_profile_is_inert_when_absent_or_zero` échoue au premier
  passage et passe au rejeu isolé (statut `ARTEFACT`). Même test, même comportement à la validation de `de52e01c`.
  Suivi : chantier 34.
- `infrared_center.json` : `"status": "OK"`, `"escaped": []`, cas 1/8. Suite complète : 2 échecs ; sélection : 1,
  car elle s'arrête au premier (`-x`). Le second est `test_a_reduced_offender_lowers_its_ceiling`, déclenché par le
  patch inversé lui-même (le fichier raccourcit), pas par la faute. 204 fichiers élus sur 668 ; 506 s contre 1 466 s
  pour le témoin complet.
- Le nombre d'ouvriers du témoin n'est pas consigné.

## 3. Ce que `OK` prouve, et ne prouve pas

`probe_test_selector.py::classify` rend `OK` si la suite complète est rouge, la sélection rouge, et si chaque fichier
en échec de la suite complète figure parmi les fichiers élus. Il ne vérifie pas que la sélection a échoué **sur le
test de la faute**. `escaped` est une appartenance de fichier, pas un test joué.

## 4. Mesure en cours — REFAITE sur `df36593f` (premier essai sur `20b979d9` : témoin tué, worker mort au join de 180 s, corrigé `ddd29cc4`) (décision du 2026-11-14, 22 h 45)

Raison : à `ac191592`, `test_le_pilotage_par_QProcess_remplit_reellement_le_tableau` peut tuer un worker xdist
(corrigé `b6d392bb`) ; une mutation d'un fichier qui cite numba vide le cache et rend ce crash probable, et un passage
tronqué fausse `escaped`. L'empreinte couvre les tests : témoin et 8 cas sont refaits. Les anciens `runs/` restent
dans `certus1111` (non suivis), témoin de `ac191592`.

- Arbre mesuré : `%LOCALAPPDATA%\Temp\certus_c19_df36593f` (worktree détaché de `df36593f`, retiré en fin de commande).
- Sorties : `reports/selecteur_tests_2026-11-14/runs_df36593f/` (`console.txt`, `control.json`, `<cas>.json`).
- Après une coupure : relancer `--cases` seul si `control.json` est vert (les cas faits sont repris) ; si le worktree
  est resté muté : `git -C <wt> checkout -- .`.

## 5. Bilan et documentation

1. Rédiger `reports/selecteur_tests_2026-11-14/bilan.md`. Par cas : statut, tests en échec dans la sélection et dans
   la suite complète, s'il s'agit bien du test du correctif (historique) ou d'un test visant la ligne mutée,
   fichiers élus sur 668, durées sélection / complète, `escaped`.
   Limites à écrire : 8 cas choisis à la main, tous dans des `.py` à tests directs, donc zéro échappé laisse un taux
   d'échappement possible d'environ 30 % (borne à 95 %) ; aucun cas sur un fichier non Python, un `conftest` ou
   `_certus_physics_impl.py` ; le sens de `OK` (§3) ; l'artefact du témoin (§2).
   Les points sur `selection.collect`, les garde-fous doc, `full_suite_reason` et les fixtures de session sont à
   **vérifier dans le code avant de les écrire**, et à marquer « lu dans le code », pas « mesuré ».
2. Commiter `bilan.md` et `runs/` seulement (pas `REPRISE.md`).
3. `docs/CHANTIERS_RESTANTS.md`, un commit : retirer `07` (clos). Le `19` ne sort de la table que si
   `verify_changed.py --audit-calls` a aussi tourné sans trou sur `tests/unit`, `tests/ui` et `tests/oracle` (aucun
   résultat consigné à ce jour) ; sinon mettre sa ligne à jour (8 cas faits, audit d'appels restant). Ajouter dans
   `Sources conservées` les liens vers les bilans `audit_chantiers_2026-11-14`, `chantier07_amorcage_2026-11-14` et
   `selecteur_tests_2026-11-14`.
4. `docs/ETAT.md` section 0, un autre commit : `**Dernière validation complète**` doit citer les deux têtes —
   `VALIDATION=GO` complet sur `723674f4` ; cinq paliers pytest verts sur `ac191592`, avec un artefact unitaire vert au
   rejeu isolé (≤ 330 caractères pour `orient.last_validation()`). Ne pas écrire « validation complète sur
   `ac191592` » : aucune commande ne l'a faite.

## 6. Clôture

`python -m ruff check .`, `python scripts/check_docs.py`, `python scripts/coherence_md.py`,
`python scripts/check_claude_md.py`, `python -m pytest tests/unit/test_orient.py -q --no-cov`. Puis supprimer ce
fichier. Ne jamais faire `git push`.
