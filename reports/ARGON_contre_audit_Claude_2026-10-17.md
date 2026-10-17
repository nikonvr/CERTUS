# Contre-audit des deux audits `*argon*.md`, vérifié par tests rouges puis verts (2026-10-17)

Portée : `designargon.md` (algorithmes de DESIGN) et `UXargon.md` (interface de la suite). Les deux contiennent déjà un contre-audit de Codex du 2026-10-16
(preuves dans `reports/ARGON_contre_audit_2026-10-16/`, dossier non suivi). Je ne refais pas ce recueil : chaque constat que j'ai retenu a été **reproduit par un
test qui échoue sur le code d'avant**, puis corrigé, un commit local par défaut (non poussé). Choix de départ : l'intégrité des données d'abord, aucun changement
numérique de physique.

## Constats confirmés et corrigés
| constat | audit | verdict | commit |
|---|---|---|---|
| Lire la configuration de DESIGN nettoie et modifie la pile (`_collect_config` appelle `smart_cleanup`, lu à l'ouverture et à la fermeture) | UX 4.3-1 | **confirmé** (lecture du code et test rouge : 2 échecs sur 3) | `868db8c9` |
| Le SMOOTHER arrondit l'axe des longueurs d'onde à 0,1 nm dans le tableau enregistré | UX 11.2-1 | **confirmé** (2 échecs sur 4 : grille à 0,05 nm détruite, longueurs répétées) ; le bruit de virgule flottante reste nettoyé | `8c6d951b` |
| La règle des 5 nm et `smart_cleanup` suppriment des couches fixes | designargon 7.1 (D08, U01) | **confirmé** (2 échecs sur 4) | `bdcae9ed` |
| Les budgets PGLOBAL affichés ne sont pas ceux exécutés quand la croissance est cochée | UX 4.3-4 | **confirmé comme défaut d'affichage seulement** : le plafonnement est une décision que vous avez acceptée le 2026-09-29 ; le journal dit maintenant « affiché -> appliqué » | `7f3edea8` |
| Un plan injecté perd `rate_layers`, la fente et les témoins | rapport d'expertise Rate (hors audits), utile à A9 | **confirmé** (4 échecs sur 8) ; mêmes clés que les enfants d'ELITE | `c25937b3` |

## Constaté à la lecture, non corrigé (travail de physique ou décision)
- **ALG-02**, `_evaluate_test_stack` de `_prune_to_target` : l'évaluation lit `t.val` et `t.weight` alors que les cibles portent `tmin`, `tmax`, `w` partout ailleurs, et un `except Exception` renvoie `inf` : le choix du retrait retombe toujours sur la couche la plus fine. Corriger demande de valider le tuple de préparation, la signature du gradient et la sélection sur de vrais designs : session dédiée.
- **ALG-01** (normalisation `count` contre `sum_w` du coût Needle), **ALG-03** (configurations obliques périmées), ALG-04 à ALG-11 : **non examinés par moi** (noyaux et workers numériques ; tout changement de nombres demande oracle et C1). Les sondes de Codex les étayent sur des fonctions extraites, sans parcours complet.
- `export_excel` exécute encore `smart_cleanup` par effet de bord (appel à `certus_design_ui_export.py`) : non touché.
- Non retenus pour décision d'interface : conflit `Ctrl+E` (Évaluer contre Exporter), libellés d'axe noirs en thème sombre, fenêtre Pareto sans parent, 9 boutons « primaires », colonne `Preset`, onglet par défaut.

## Remarques sur les audits eux-mêmes
- Ils sont déjà corrigés par Codex (diagnostics erronés retirés : solveur « maison », absence de `jac` dans l'élagage, rayon PGLOBAL). Aucun constat que j'ai testé ne s'est révélé faux.
- Le plafonnement PGLOBAL est présenté comme « écrasement silencieux » : c'est une décision documentée, seul l'affichage manquait.
- Les deux fichiers sont à la **racine** du dépôt (non suivis) alors que CLAUDE.md §3.10 range les sorties dans `reports/` ; les déplacer casserait leurs liens relatifs.

## Validation (CLAUDE.md §2, état `7f3edea8`, 2026-10-17, une étape à la fois)
- oracle **1146 passed** ; unité **5504 passed, 7 skipped** (5475 avant, 29 de plus) ; UI **1324 passed, 12 skipped, 2 xfailed** ; reste **359 passed** ; `coherence_md`, `check_claude_md`, `check_docs` : codes de sortie 0.
- `ruff check .` sort en **échec (34 infractions)**, **uniquement** à cause de deux scripts non suivis de Codex, `reports/ARGON_contre_audit_2026-10-16/probe.py` (26) et `pass02.py` (8) : PT018, I001, E731, PT017, RUF059, RUF005. Sur les 1 169 fichiers Python **suivis**, ruff passe (`All checks passed!`). Je n'ai pas touché à ces deux scripts : ils font partie des preuves de Codex et les deux audits les lient. Remède habituel du projet : les garder en `.py.txt` (octets conservés), ce qui casse ces liens à mettre à jour, ou corriger leur lint ; décision de 👤.
- Aucun `--fix`, aucun `extend-ignore` agrandi. Cinq commits locaux (`868db8c9`, `8c6d951b`, `bdcae9ed`, `c25937b3`, `7f3edea8`), rien de poussé.
