# REPRISE — refactoring des corridors d'INDEX SPLINE et feuille de route UX

Fichier de reprise, **autonome** : il suffit pour reprendre le chantier sur un autre ordinateur, sans la conversation ni
la mémoire de l'assistant. Il est mis à jour à chaque étape, avant de passer à la suivante. Le détail de chaque phase et
de chaque décision est dans `REFACTOR_PLAN.md`, même dossier ; ce fichier dit où on en est, comment repartir, et comment
faire la suite.

**État au 2026-11-12, 21 h** : le refactoring des corridors est **fini** (Phases 0 à 10, toutes validées). Feuille de
route UX : **U1 à U5 faites et validées**, **poussées sur `master`** (`9bb4999b`, sur ordre de 👤). La prochaine étape
est U6, sur la branche `claude/reprise-057fcd`, en autonomie (nuit du 2026-11-12) ; ce qui suit `9bb4999b` n'est pas
poussé.

## 1. Le chantier en cinq lignes

La fenêtre INDEX SPLINE (`certus/ui/certus_index_spline_*.py`) était faite de 21 mixins dont les méthodes « corridor »
étaient réparties par l'histoire des fichiers. Elles sont maintenant regroupées par fonctionnalité dans cinq **tranches**
(`certus_index_spline_corridor_run`, `_rmse_view`, `_interval`, `_nk`, `_rmse_plot`), par **déplacement pur** : texte
inchangé, bytecode prouvé identique par `scripts/refactor_guard.py`. S'y sont ajoutés les correctifs révélés par l'audit
(Phase 10), deux arêtes entre familles (Phase 7), puis la feuille de route UX (plan, sections 5.5 et 5.6), en cours.

## 2. Reprendre sur un autre ordinateur

### 2.1 Avoir la branche

Tout jusqu'à `9bb4999b` (U1d) est sur **`master`, poussé** le 2026-11-12. La suite est sur la branche locale
**`claude/reprise-057fcd`**, au-dessus de `origin/master`, non poussée. Branches plus anciennes, toutes contenues dans
`master` : `claude/certus-refactor-audit-6cd1fc`, `claude/reprise-certus1111-926596`, `claude/certus-1111-reprise-60e136`
(leurs worktrees sont supprimés).

| Voie | Quand | Commandes |
|---|---|---|
| Le dossier `certus1111` arrive entier, `.git` compris (synchronisation du disque) | cas attendu | `git branch --sort=-committerdate` montre la branche en tête. Si un worktree pointe sur un chemin absent : `git worktree repair`, ou `git worktree prune` |
| Un fichier unique à copier | si `.git` ne suit pas | ancien PC : `git bundle create certus_corridors.bundle origin/master..claude/reprise-certus1111-926596` ; nouveau PC, dans un clone de `github.com/nikonvr/CERTUS` : `git fetch certus_corridors.bundle claude/reprise-certus1111-926596:claude/reprise-certus1111-926596` |
| Pousser la branche | **seulement sur ordre de 👤** : le dépôt est public | `git push origin claude/reprise-certus1111-926596` |

Une session neuve de l'assistant ouvre un worktree neuf sur `master`, qui n'a pas le travail. Y faire
`git branch --sort=-committerdate`, puis `git merge --ff-only <la branche de tête>`, et noter ici la nouvelle branche.
Avant, regarder `git worktree list` et `git -C <worktree> status -sb` de chaque worktree : une session coupée peut y
avoir laissé du travail non commité (c'est arrivé pour U2).

### 2.2 Avoir l'environnement

- **Python 3.15.2, exactement.** La garde compare du bytecode : avec une autre version elle refuse (code de sortie 2).
- `pip install --require-hashes -r requirements.lock`, puis `pip install pytest-xdist` (hors du verrou ; 3.8.0 ici).
- Versions de ce PC : ruff 0.16.9, pytest 9.1.1, numba 0.68.0, numpy 2.5.3, PyQt6 6.11.0, pyqtgraph 0.14.0, pydantic
  2.14.1 ; Windows 11, Git Bash.
- Le dépôt est en *sparse-checkout* (`docs/ETAT.md`, section 0) : rien à y changer pour ce chantier.

### 2.3 Vérifier qu'on est au bon endroit — quatre commandes, dans l'ordre, une à la fois

```bat
python scripts\preflight.py
python scripts\orient.py
python reports\refactor_corridors_2026-11-11\tools\guard.py
python reports\refactor_corridors_2026-11-11\tools\lot.py
```

Attendu : `PREFLIGHT=GO` ; arbre propre et aucun autre processus python ; `problems=0` et `GUARD=OK` ; le lot sans
échec (plusieurs centaines de tests, 2 à 4 minutes ; le premier passage sur un arbre neuf compile Numba et dure plus). Si la garde
ou le lot ne rendent pas cela sur un arbre propre, **s'arrêter et le dire** : tant qu'on n'a rien modifié, c'est
l'environnement, pas le code.

### 2.4 Si la coupure a eu lieu au milieu d'une étape

`git status -sb` et `git log --oneline -n 8`, à comparer aux sections 4 et 5. Des fichiers modifiés non commités
appartiennent à l'étape « En cours ». Ne pas les commiter de confiance : rejouer le test de l'étape sur le code d'avant
(il doit échouer), puis après, puis ruff, la garde et le lot. C'est ainsi que U2, reprise d'une session coupée, a montré
un rouge que personne n'avait encore vu.

## 3. Consignes de 👤 — elles ne sont écrites nulle part ailleurs sur un autre PC

- **Enchaîner en boucle**, sans s'arrêter entre les étapes : un travail soigné mais rapide (2026-11-11). Ne pas finir
  un tour pour annoncer une étape finie ni pour attendre un accord.
- **Trancher soi-même** les questions de conception, le plus intelligemment possible, et consigner la décision et sa
  raison (plan, section 4). Cela ne couvre ni un push, ni une suppression dans `reports/`, ni un arrêt que les règles
  du dépôt imposent, ni une décision que le plan réserve à 👤 (§6).
- **Tout inscrire ici** : tâche faite, en cours, à faire — une coupure de courant ne doit rien faire perdre. Et ce
  fichier doit tout contenir pour une reprise sur un autre PC.
- **Viser une UX « top 1 % mondial »** : audit fait (plan, section 5), feuille de route U1 à U13.
- Nuit du 2026-11-11 : « tourne en mode 100 % autonome, je te donne toute autorisation ». Lu comme : tout enchaîner et
  commiter sans demander. Rien n'est poussé pour autant.
- Les règles du dépôt sont dans `CLAUDE.md` et `AGENTS.md`, à lire en premier. Celles qui comptent le plus ici : ne
  jamais pousser sans ordre ; jamais `ruff check --fix` ; une seule mesure ou validation à la fois ; un commit par
  chose ; un test ajouté pour un correctif doit échouer sur le code d'avant ; ne jamais affirmer un résultat non mesuré ;
  pas de français dans les commentaires et docstrings de `certus/`.

## 4. Fait

| Quoi | Commit |
|---|---|
| Audit statique et plan (`REFACTOR_PLAN.md`), arbitrages Q1 à Q5 et Q16 | dans `211d561b` |
| Correctif ruff B905, `zip(..., strict=False)` dans un script de campagne | `9d011d68` |
| Correctif échappement invalide, chaîne brute dans un script de campagne | `15d518aa` |
| **Phase 0** : `scripts/refactor_guard.py`, ses 13 tests, instantané de référence, plan déplacé ici | `211d561b` |
| **Phase 1** : état déclaratif, contrats, 52 tests, manifeste ; toutes les questions ouvertes tranchées (plan, section 4) | `0e3d4b57` |
| **Audit UX** complet des 11 modules : plan, section 5 (constats A, B, C et feuille de route U1 à U13) | `74de941e` |
| **Phase 2a** : les trois constantes corridor n'ont plus qu'une définition | `bea41352` |
| **Phase 2b** : `_apply_fixed_log_k_axis` et ses deux bornes n'ont plus qu'une définition | `4be1b0af` |
| **Phase 2c** : les 16 constantes de fenêtre n'ont plus qu'une définition, dans le cœur spline | `133becde` |
| **Phase 2d** : les deux clés du smart-init n'ont plus qu'une définition, dans `common` | `d16346d9` |
| **Phase 2e** : les trois classes du smart-init n'ont plus qu'une définition, dans `state_ui` | `de79f62e` |
| **Validation complète de la phase 2** : rien de plus que l'état connu (plan, Phase 2) | sur `de79f62e` |
| Garde étendue : une méthode peut quitter une classe pour une tranche dont elle n'hérite pas, si le manifeste le dit | `85e5d24f` |
| **Phase 3a** : `_CorridorRunMixin`, 15 méthodes dans `certus_index_spline_corridor_run.py` | `cdc5ce24` |
| **Phase 3b** : `_CorridorRmseViewMixin`, 9 méthodes dans `certus_index_spline_corridor_rmse_view.py` | `32e5d038` |
| **Phase 3c** : `_CorridorIntervalMixin`, 11 méthodes dans `certus_index_spline_corridor_interval.py` | `9c4720cd` |
| Outils d'extraction d'une tranche (`tools/`, six étapes, mode d'emploi en tête de chaque fichier), Q18, Q20, Q21 tranchées, 3d préparée | `24dc5a0b` |
| **Phase 3d** : `_CorridorNkMixin`, 7 méthodes dans `certus_index_spline_corridor_nk.py` | `d3118167` |
| **Validation complète de la phase 3** : un rouge réel dû à 3a (`test_progress_imports.py`, liste de modules), corrigé (Q22) ; le reste est l'état connu (plan, Phase 3) | sur `d3118167`, correctif au commit suivant |
| **Phase 4** : `_CorridorRmsePlotMixin`, 10 méthodes dans `certus_index_spline_corridor_rmse_plot.py` ; `rendering.py` sous 1 000 lignes | `7db3b42a` |
| **Validation complète de la phase 4** : rien de plus que l'état connu (plan, Phase 4) | sur `7db3b42a` |
| **Phase 5a** : les trois fonctions de calcul des corridors dans `certus_index_spline_corridor_jobs.py` | `2d8cc760` |
| **Phase 5b** : le mandataire paresseux de la fenêtre dans `certus_index_spline_lazy_app.py` | `7198ce64` |
| **Phase 5c** : `_start_curve_minimum_deep_refit` dans `_CorridorRunMixin` ; Q23 tranchée | `44b24b2a` |
| **Phase 5d** : les 8 méthodes statiques sont des fonctions de `certus_index_spline_statics.py`, 8 commits, plus le test | `bdba59cb` à `d7b068d7`, test `55f2d194` |
| **Validation complète de la phase 5** : rien de plus que l'état connu (plan, Phase 5) | sur `55f2d194` |
| **Phase 6a** : garde-fous d'héritage étendus aux huit autres fenêtres, plus celui de F11 (aucun nom masqué par Qt) | `18be2a5b` |
| Garde : une classe sortie des bases d'une fenêtre reste en tête de son propre MRO | `ab7f6884` |
| **Phase 6b** : `_UIMixin` hors des bases de la fenêtre | `a0150bc9` |
| **Phase 6c** : le constructeur donne à tout l'état corridor sa valeur par défaut, depuis la table | `fce0ee90` |
| **Phase 8, clôture** : registre de dette exact, garde finale `GUARD=OK` avec les 17 manifestes, relevé des 56 imports sans lecteur | `9c57ffd8` |
| **Validation complète des phases 6 et 8** : rien de plus que l'état connu (plan, Phase 6) | sur `9c57ffd8` |
| **Phase 9** : les deux tests de `test_mwir_gui_flow.py` remplacent `GenericWorker` là où la méthode le lit ; preuve faite que le vrai était construit | `8088dc4c` |
| **Phase 10a** : une courbe RMSE(d) vide écrit `-1`, plus `None`, dans `_corridor_rmse_best_idx` (Q17) ; test rouge avant (`8 failed`) | `43d48d3f` |
| **Phase 10b** : la branche morte de `_plot_result` est retirée, `NEVER_ASSIGNED` est vide (Q13) ; test rouge avant (`1 failed`) | `82007a4a` |
| **Phase 10c** : `_load_defaults` remet les huit attributs corridor écrits pour un échantillon (Q11) ; test rouge avant (`2 failed`) | `5b801bf5` |
| **Phase 10e** (Q24, trouvée par la mesure de 10c) : `_load_defaults` oublie aussi `_last_worker_result` et `_last_run_cfg` ; avant, « Recalculate RMSE(d) » après un reset relançait la grille sur l'échantillon oublié ; test rouge avant (`4 failed`) | `0267b135` |
| **Phase 10d** : le `2e-4` de l'intervalle robuste s'appelle `_DEFAULT_CORRIDOR_ROBUST_RMSE_DELTA`, lu aux six endroits (Q12) ; test rouge avant (`3 failed`) | `e9f68946` |
| **Validation complète de la phase 10** : rien de plus que l'état connu ; un rouge dû au cache Numba de l'arbre neuf, vert sur cache vierge ([note](cache_numba_arbre_neuf.md)) | sur `e9f68946` |
| **Phase 7a** : `_resolve_strat_indices_db_path` descend dans `certus/core/certus_indices_db.py` ; FIELD n'importe plus rien de STRAT ; test rouge avant (`4 failed`) | `37c9ca26` |
| **Phase 7b** (Q25) : `spectral_rmse_weights` descend dans `certus/domain/spectral_weights.py` ; DESIGN, RE et le gradient analytique la prennent là ; oracle avant/après verts, `c1_diff HEAD` : C1 TENU (9 092 tableaux) ; test rouge avant (`7 failed`) | `aa75be4f` |
| **Validation complète de la phase 7** : rien de plus que l'état connu, et le même test « au bit » rouge sur le cache de l'arbre, vert sur cache vierge (deuxième occurrence, mêmes valeurs : [note](cache_numba_arbre_neuf.md)) | sur `aa75be4f` |
| **U1a** : les unités inverses (`nm⁻¹`, `nm⁻²`) et le `ξ` que le code prouve reviennent dans dix chaînes et une infobulle d'INDEX SPLINE ; test rouge avant (`2 failed`) | `0b3fc350` |
| **U1b** : huit « ? » des phrases de l'onglet RMSE(d) deviennent `≈` (valeur), `∈` (intervalle) et `—` (titre) : un choix, l'historique n'a pas l'original ; attendus de `test_rmse_tab_summary.py` mis à jour (`5 failed` avant) | `561bff95` |
| **U1c** : les trois chaînes françaises d'INDEX SPLINE sont en anglais ; cliquets : aucun « ? » à la place d'un symbole dans l'interface, pas de français dans les sources de la fenêtre INDEX SPLINE (`2 failed` avant) | `cddf791a` |
| **U2** : un format de titre, `CERTUS-MODULE — ce que fait le module`, écrit en un endroit ; commencée par la session de nuit, coupée, reprise et vérifiée de bout en bout ; un rouge réel trouvé et corrigé (le fichier long de METAL grandissait de 2 lignes) ; test rouge avant (`3 failed`) | `bf5cda14` |
| Ce fichier refait pour suffire sur un autre PC ; `docs/ETAT.md` à jour | `b5c75869` |
| **U3, la mesure** : l'audit UX voit un texte coupé ou à l'étroit ; départ : 19 coupés à 1440×900, 20 à 1366×768 | `cb3d79ec` |
| **U2, suite** : le cliquet UX de RE était rouge depuis U2 (panneau gauche 336 px pour 315) ; sous-titre d'en-tête corrigé, test rouge avant | `07b2867e` |
| **U3, composants partagés** : le titre d'une carte passe à la ligne, la barre de progression a une forme empilée ; test rouge avant (`3 failed`) | `ee1a6c22` |
| **U3, INDEX SPLINE** : 8 textes coupés avant, 0 après, aux deux tailles ; questions réservées à 👤 tranchées (Q26 à Q29) | `82534c96` |
| **U3, DESIGN, RE, STRAT** : 2, 1 et 9 textes coupés avant, 0 après ; mesure corrigée pour les en-têtes sur deux lignes | `cca0fe0e`, `abf44f99`, `5f169971`, `de4eb0d3` |
| **U3, le cliquet** : 0 texte coupé dans les 11 fenêtres à 1366×768 et à 1440×900 | `3b84ff56` |
| **Validation complète de U1 à U3** : rien de plus que l'état connu ; un rouge de l'étape corrigé (liste des tests lents) | sur `82534c96` et les fichiers de U3 |
| **U4a** : un seul indicateur de zoom, dans la barre d'état (DESIGN, STRAT, RE en montraient deux, INDEX SPLINE un en haut à gauche) ; test rouge avant (`4 failed`) | `1c274e3a` |
| **U4b** : chaque compteur de barre d'état porte son mot, sans pictogramme (DESIGN, STRAT, METAL, INDEX) ; la remise à zéro garde les mots et remet les nombres à 0 (elle écrivait trois pictogrammes partout, RE comprise) ; tests rouges avant (`5 failed`, `3 failed`) | `df4a70d5` |
| **U5** : un message déjà à l'écran n'est pas affiché deux fois (pile de toasts) ; DESIGN ne redemande plus `Ctrl+S` ; test rouge avant (`2 failed`) | `8e3a2c0f` |
| **Validation complète après U4 et U5** : rien de plus que l'état connu ; un test de l'étape, fragile sous la charge, rendu robuste | sur `8e3a2c0f`, correctif `93d8706d` |
| **U1d, traduction** (Q26) : INDEX SPLINE (4 chaînes sans accent que l'ancien test ne voyait pas), DESIGN (2), RE (1), SUBSTRATE (1, et les trois références UX qui l'enregistrent), HUB (1 message d'erreur), STRAT (bandeau d'état, panneau de la Phase A, en-tête de la Phase B, infobulles, avertissement multi-graines ; quatre tests qui lisaient le bandeau suivent les mots). Les états d'un calcul multi-graines restent en français : ce sont des jetons, traduits à l'affichage | `2e5c5978`, `1a6a50e3`, `10274ad6`, `4488c9dd`, `8b946a2f`, `cac0a5e3` |
| **U1d, le cliquet** : aucune chaîne visible en français dans les 11 fenêtres, accents ou non ; rouge avant (49 chaînes trouvées sur le code d'avant la traduction) | `32569315` |
| Ce fichier et le plan à jour après U1d ; `docs/ETAT.md` à jour | `9bb4999b` |
| **Validation complète après U1d** : l'état connu seul (plan §5.6) ; **poussé sur `master`** sur ordre de 👤 | sur `9bb4999b` |
| Rangement sur ordre de 👤 : copie périmée du plan supprimée à la racine ; worktrees anciens retirés ; le travail non commité du checkout principal (recherche locale de STRAT, campagne RICL) mis de côté sur la branche locale `wip/strat-local-search-ricl-2026-11-11` (`f81bb45d`, non validé, non poussé) ; `master` local avancé | — |

| **U6, système d'actions** (Q30) : mesure `action_buttons` ; Reset au rôle destructif, plus de brun ; « Stop » partout et casse de phrase ; une action principale dans DESIGN, RE, STRAT, INDEX SPLINE, aucune dans le HUB ; cliquet `test_ux_one_action_system.py` (`21 failed` avant) ; `ux_` : `1166 passed` | `4eef2a9b` à `ac03ad10` |
| **U7** : FIELD installe la feuille de la suite (régression de U6 corrigée, rôle vérifié sur le pixel peint) ; glyphe du bouton de thème partout (A10) ; un seul guide de déroulé (B1) ; correctif U1 | `055b6c76` à `7f6f529e` |
**Dernière validation complète** : le 2026-11-12 vers 20 h 35, sur `9bb4999b` (plan §5.6).

## 5. En cours

**U8, fait** (Q32, Q35) : mesure `emoji_labels` ; `set_themed_icon` (boutons et libellés) ; boutons et titres sans emoji
(`626d84b8`) ; garde-fou SVG borné à PyQt6 < 6.11 (`13868e1c`, suite UI entière `1512 passed` icônes visibles) ; dix
icônes sur les tuiles du HUB (`7a072ee3`) ; lignes d'état de l'accueil de STRAT (`08ac066c`). Les six slogans de
l'accueil de STRAT gardent leurs emojis : U10 les remplace par des actions (Q37) ; le cliquet U8 garde STRAT en `xfail`
jusque-là. **U9, fait** : plancher de l'en-tête (`b695fe80`) ; corps à 10 pt dans DESIGN et RE (`242ec1c4`) ; Reset à
10 pt (`2a8c2922`) ; cliquet `test_ux_one_type_scale.py` (`bd033b7c`, `2 failed` avant) ; `ux_`, DESIGN, RE : `1905 passed`.
**En cours : U10.**

## 6. À faire, dans l'ordre

2. **U9 à U11** — échelle typographique, états vides actionnables, messages (Q33) (plan §5.5). **U12** (reprise d'un calcul après coupure) est à spécifier avant tout code : elle
   touche au calcul. **U13** (écran réel, HiDPI, lecteur d'écran, essais avec des utilisateurs) n'est pas à la portée
   d'une IA.

**Tranché le 2026-11-12, sur consigne (« autonomie totale, réponds-toi aux questions ») — plan, section 4**

- Q26 : le français visible de STRAT, RE et du HUB **est traduit** en anglais (U1d, fait le 2026-11-12).
- Q27 : les signes de U1b (`≈`, `∈`, `—`) restent.
- Q28 : le test « au bit » du noyau STRAT reste tel quel ; un rouge se rejoue sur cache Numba vierge (§8).

**Tranché par 👤 le 2026-11-12 au soir** (plan, section 4) : Q30, l'action principale de DESIGN est PGLOBAL ; Q31, un
guide de déroulé statique unifié ; Q32, U8 avec les icônes SVG du projet (`certus_icon`) ; Q33, U11 : les informations
en toast, avertissements et erreurs restent modaux, réécrits (cause et geste). Le 2026-11-13 : Q34, le corps de texte est 10 pt partout ; Q35, le garde-fou SVG est levé à partir de PyQt6 6.11. Puis Q36, Reset à 10 pt (remplace D58) ; Q37, accueils de STRAT et du HUB : fichiers récents et exemple ; **Q38, pousser sur `master` après la validation complète finale si seuls les rouges connus restent (ordre de 👤)** ; Q39, U12 : une spécification, pas de code.

**Garde-fou SVG** : tranché par 👤 le 2026-11-13 (Q35), voir le plan.

**Ce qui reste à 👤 — des gestes, pas des arbitrages (Q29)**

- **Pousser** ce qui suit `9bb4999b` (U6 et la suite) : seulement sur son ordre, le dépôt est public.
- **Reprendre** sa branche `wip/strat-local-search-ricl-2026-11-11` (dans le checkout principal, pas dans un worktree
  de session) ; un seul conflit attendu avec `master` : `reports/RICL_ultimate_2026-11-05/exhaustive_clean_bs.py`.

## 7. Recettes

**Une étape UX (U3 et suivantes)** — elle change un comportement visible, donc :

1. Inscrire l'étape au §5.
2. Écrire d'abord le test cliquet, et le voir échouer sur le code d'avant ; noter le compte (`N failed, M passed`).
3. Modifier ; une chose par commit. Un fichier listé dans `tests/architecture_debt.json` ne doit pas grandir d'une
   ligne (le cliquet de dette est dans le lot).
4. Écrire `manifests/phase_<étape>.json` : `changed_code` pour chaque fonction dont le corps change, `added_attributes`
   pour une méthode nouvelle héritée par les fenêtres, `rebound` pour une constante de classe changée ; une `note` dit
   ce qui change hors de ce que l'instantané regarde.
5. `python -m ruff check .` ; le test ; `python reports\refactor_corridors_2026-11-11\tools\guard.py` (attendu
   `GUARD=OK`) ; `python reports\refactor_corridors_2026-11-11\tools\lot.py <tests de l'étape et tests voisins>`.
6. Consigner : plan §5.6 (chiffres mesurés), §4 à §6 de ce fichier, commit en anglais.

**Une extraction de tranche** (si le geste revient) : les six outils de `tools/` dans l'ordre `plan_move`, `move`,
`manifest`, `contracts`, `protocols`, `born_in`, mode d'emploi en tête de chaque fichier, modèles dans `tools/specs/` ;
`tools/static_to_function.py` pour une méthode statique ; `tools/unread_imports.py` pour le relevé de clôture. Leçon à
ne pas réapprendre (plan, Q18) : sous Python 3.15, un nom lié par `import` et un nom affecté ne donnent pas le même
bytecode pour `nom.methode(...)` ; un module nouveau lie `logger` comme le module d'origine.

## 8. Validation complète, et son état connu

`python scripts\validate_parallel.py` — environ 25 minutes, **rien d'autre en même temps** (ni test, ni garde, ni
script python). La lancer en arrière-plan et attendre sa fin ; sa sortie n'apparaît qu'à la fin.

**Rouges connus, qui ne sont pas des régressions** — la commande affiche donc `VALIDATION=NO-GO` :

- `coherence_md` sort en erreur sur 3 commandes mortes de documents de campagne (`cissoid_metal_trade.py`,
  `take_record.py`, `hidden_resonances.py`, dossier `envelope_v2`) : laissé tel quel sur décision de 👤. Sa section F
  signale aussi des renvois `fichier.py:N` du plan qui ne pointent plus sur leur symbole : les numéros de ligne du plan
  sont ceux du relevé de Phase 0, et chaque déplacement en a décalé.
- Un test peut tomber en parallèle et passer seul (artefact de charge) : vu sur
  `tests/property/test_physics_properties.py::test_bare_substrate_transmission_bounds` et sur des tests qui
  chronomètrent. La commande le rejoue seule et le classe `ARTEFACT`.
- **Le test « au bit » du noyau STRAT, rouge même seul sur un arbre dont le cache Numba vient d'être rempli par
  plusieurs processus** (deux occurrences, mêmes valeurs ; écart de 10⁻¹⁰ nm, sans effet physique). Avant de conclure,
  le rejouer avec `NUMBA_CACHE_DIR` sur un dossier neuf : [`cache_numba_arbre_neuf.md`](cache_numba_arbre_neuf.md). Un
  arbre neuf, ou un autre PC, recompile tout à froid : s'y attendre.

Tout autre rouge est nouveau : s'arrêter, le rejouer seul, le signaler.

## 9. Où sont les choses

| Quoi | Où |
|---|---|
| Plan, phases cochées avec leurs chiffres, arbitrages Q1 à Q26 (section 4), audit UX et avancement (section 5) | `REFACTOR_PLAN.md` |
| Instantané de référence de la garde (Phase 0, `15d518aa`, Python 3.15.2) — il reste (Q20) | `reference_snapshot.json` |
| Ce que chaque phase ou étape a le droit de changer | `manifests/phase_*.json` |
| Outils : `guard.py`, `lot.py`, et ceux des extractions | `tools/`, `tools/specs/` |
| Notes de mesure : cache Numba d'un arbre neuf ; imports laissés sans lecteur par les déplacements | `cache_numba_arbre_neuf.md`, `imports_sans_lecteur.md` |
| La garde elle-même et ses tests | `scripts/refactor_guard.py`, `tests/unit/test_refactor_guard_compares_two_class_surfaces.py` |
| L'audit UX | `python scripts/audit_ux_certus.py` ; sonde des libellés : `scripts/sonde_libelles_visibles.py` |
| État général du projet | `docs/ETAT.md`, section 0 |

## 10. Pièges rencontrés sur ce PC (Windows, Git Bash)

- Les fichiers de l'arbre sont en CRLF (`core.autocrlf=true`) : un script qui réécrit un fichier doit rendre des CRLF.
- Python sous Windows ne connaît pas `/tmp` : lui passer des chemins Windows ou relatifs.
- Dans un *heredoc* Git Bash, `\\n` devient un vrai saut de ligne : écrire le code à générer dans un fichier.
- Une sortie de commande se paie (`AGENTS.md`) : `| tail`, `--output-format concise` pour ruff.
- Le dossier de travail d'une session est son worktree : ne pas écrire dans le checkout principal ni dans le worktree
  d'une autre session ; y lire est permis.
