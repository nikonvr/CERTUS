# U12 — reprise d'une session et d'un calcul après coupure : spécification

Rédigée le 2026-11-13 sur décision de 👤 (Q39 du plan : une spécification, aucun code). Constat C7 de l'audit UX : rien
ne survit à une coupure, ni la session, ni un calcul en cours.

## 1. Ce qui existe

| Quoi | Où | Survit à une coupure ? |
|---|---|---|
| Retour au point de contrôle d'une optimisation DESIGN | `certus_design_ui_optimization.py::_revert_to_checkpoint` | non, en mémoire |
| Point de contrôle de synthèse FIELD | `certus_field_state_mixin.py::_revert_to_synthesis_checkpoint` | non, en mémoire |
| Fichiers récents (DESIGN, RE… ; STRAT depuis U10) | `certus/ui/certus_recent.py`, QSettings | oui, la liste seule |
| Disposition des fenêtres, en-têtes de tables | QSettings | oui |
| Campagnes de 👤 (RICL) | `reports/RICL_ultimate_2026-11-05/queue.txt`, `queue_done.txt` | oui : file d'attente sur disque, une ligne par calcul fait |

Le dernier motif est le bon modèle : l'unité de travail est écrite quand elle est finie, et la reprise saute ce qui est
écrit. Il n'existe nulle part dans l'interface.

## 2. Deux niveaux, à séparer

**A. Reprise de session** — l'état de la fenêtre : configuration chargée, paramètres modifiés non sauvegardés, onglet.
Ne touche à aucun calcul. Mécanisme : la sauvegarde que chaque fenêtre sait déjà écrire (`save_config`), faite toute
seule toutes les N secondes dans un dossier de session, et proposée à l'ouverture suivante par l'accueil (U10 :
« Reprendre la session du … »). Risque faible.

**B. Reprise d'un calcul interrompu** — STRAT (Monte-Carlo de robustesse, multi-graines), DESIGN (PGLOBAL multi-départs),
INDEX SPLINE (grille RMSE(d) des corridors). **Touche au calcul** : c'est ici que tout se joue.

## 3. Contraintes non négociables pour B

1. **C1** : tout est inactif par défaut ; le chemin inactif rend les mêmes bits (`scripts/c1_diff.py HEAD`).
2. **C2** : un tirage est une fonction pure de (graine, tirage, index physique). Une reprise **ne retire jamais** un
   tirage : elle saute les indices faits et calcule les autres avec les mêmes graines.
3. **L'identité au bit** : un calcul interrompu puis repris rend **exactement** les mêmes bits qu'un calcul d'une traite.
   C'est le critère d'acceptation, pas une propriété souhaitée.
4. **Refuser plutôt que se tromper** : un journal dont la configuration, la version du code ou la clé du cache Numba
   (`numba_cache_key`) diffère est refusé, avec un message qui dit pourquoi. Un résultat repris faux et qui a l'air
   juste est le pire cas possible (`CLAUDE.md`, préambule).

## 4. Proposition pour B, par moteur

Un journal par calcul, JSON Lines, en ajout seul, écrit par `atomic_open` (une ligne par unité finie) :

- en-tête : version du format, empreinte SHA-256 de la configuration, révision git, `numba_cache_key`, graine ;
- une ligne par unité finie : son indice et son résultat, sérialisé sans perte (`float.hex` pour les réels).

| Moteur | Unité naturelle | Ce que la reprise saute |
|---|---|---|
| STRAT robustesse | un tirage Monte-Carlo (indice, graine) | les tirages déjà écrits |
| STRAT multi-graines | une graine (déjà orchestrée par `scripts/orchestre_multigraine.py`) | les graines finies |
| DESIGN PGLOBAL | un départ (indice du départ) | les départs finis ; le regroupement se refait sur l'ensemble |
| INDEX SPLINE corridors | un point de la grille RMSE(d) | les points calculés |

Ordre de mise en œuvre conseillé : A, puis STRAT multi-graines (déjà découpé par graine), puis STRAT robustesse.

## 5. Tests d'acceptation (à écrire rouges d'abord)

1. Interrompre à mi-parcours puis reprendre rend les mêmes bits qu'une traite (par moteur, petit cas, graine fixe).
2. Un journal tronqué au milieu d'une ligne est lu jusqu'à la dernière ligne complète, et rien de plus.
3. Un journal d'une autre configuration, d'une autre révision ou d'un autre cache Numba est refusé.
4. Reprise désactivée : `c1_diff` rend C1 TENU.

## 6. Tranché par 👤 le 2026-11-13 (Q40 du plan)

1. **A seule d'abord** : la reprise de session, sans toucher au calcul.
2. Pour B, plus tard : **STRAT multi-graines** en premier.
3. Sessions et journaux dans le **dossier de configuration de CERTUS** (`sessions/`), rien dans les dossiers de travail.
4. La reprise est **proposée** par l'accueil (« Reprendre la session du … »), jamais automatique.

## 7. Estimation (jugement, non mesuré)

A : une journée. B : deux à trois jours par moteur, dont la moitié pour les tests au bit.
