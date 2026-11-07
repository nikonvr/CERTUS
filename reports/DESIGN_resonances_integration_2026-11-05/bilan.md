# Intégration native des résonances dans CERTUS DESIGN — 5 novembre 2026

## État et demande

L'auteur autorise l'intégration de la méthode du manuscrit soumis à Optics Express,
pour que le nouvel article RICL présente un outil utilisable dans CERTUS DESIGN.
Le manuscrit soumis A1 reste intact. Le code natif et l'interface optionnelle sont
implémentés ; le pilote final v3 et son témoin nominal ont terminé avec un contrôle
indépendant. **Relais immédiat demandé par l’auteur : validation générale encore en cours. Aucun GO global final ne doit être revendiqué.**

Les sources de production, les tests et les deux pilotes utilisés ici sont figés dans
`sources_et_interfaces_finales.zip`, avec leurs empreintes dans
`sources_et_interfaces_finales_sha256.json`. `sources_natives_v3.zip` conserve
l'état avant l'exécution du pilote final. Aucun commit ni push n'a été effectué.

## Architecture et domaine

- `certus/physics/design_resonances.py` : localisation et comptage des pôles,
  recherche des maxima réels, analyse et raffinement explicite.
- `certus/core/certus_design_resonances.py` : validation de l'entrée DESIGN,
  copie des épaisseurs physiques, indices des couches variables et bornes.
- `certus/ui/certus_design_resonances_dialog.py` : travail dans un QThread,
  progression, annulation, aperçu puis application explicite.
- `certus/ui/certus_design_ui_layout.py` : ajout du seul onglet `Resonances`.

Les noyaux historiques ne sont pas modifiés. Le dénominateur complexe réutilise
`oblique_front_char_matrix_single`, à incidence normale, puis
`reflection_amplitudes`. Les résidus réels et Jacobiennes proviennent du noyau
`design_fast_gauss_newton`. La production n'importe aucun pilote de `reports/`,
aucun nouvel algorithme TMM n'est recopié et les modules core/physics n'importent pas Qt.
L'essai initial du dénominateur à quatre longueurs d'onde réelles ou complexes donne
un écart relatif maximal de 1,77 × 10⁻¹³ avec le Code 1 indépendant de A1
(`probe_matrice_complexe.json`).

Le domaine accepté est : incidence normale depuis l'air, substrat et couches à
indices constants réels positifs, aucune face arrière, cible de transmission constante
dans chaque bande. Les bandes sont disjointes, ont un pas uniforme commun et au moins
cinq points. L'adaptateur exige des poids de cible égaux et un véritable modèle
constant (`Material.n4 == Material.n7`), sans prolonger artificiellement une dispersion.
L'outil a sa propre grille uniforme équipondérée ; il ne remplace pas la quadrature
spectrale de DESIGN ordinaire. Les scores de cette grille sont des fractions dans
l'API et sont affichés en pour cent dans l'interface et les résultats de l'article.

## Cohérence de la charge et contrôles

Le plan complexe sert à détecter et suivre les pôles ; la pénalité est évaluée au
maximum réel de l'erreur associé. Chaque pic actif a le poids d'un point nominal,
avec la même normalisation 1/J que l'objectif nominal. La localisation est contrôlée
avant sélection des hauteurs par le nombre de zéros dans le même rectangle de chaque
bande. Le contour en lambda est entre Im(lambda) = -largeur_max/2 et +gamma.
Le comptage vérifie son caractère entier et sa convergence pour les pas 0,02 et
0,01 nm ; un désaccord localisation/comptage provoque une erreur explicite.
Cela n'est pas une preuve de complétude dans tout le plan complexe.

Pour les indices constants, T dépend de d/lambda. L'identité
`lambda * T_lambda = -sum(d_i * T_di)` fournit la dérivée spectrale à partir du
Jacobien analytique existant, en incluant les couches fixes. Le maximum est affiné
par un zéro de cette dérivée. Au sommet stationnaire intérieur, le terme dû au
mouvement de la longueur d'onde s'annule dans la dérivée de la hauteur. Le test
comparant ce Jacobien à des différences finies du maximum mobile est conservé.

Durant une salve, un pôle peut sortir de sa fenêtre initiale de détection. Le suivi
le permet et conserve la cible constante de sa bande d'ancrage jusqu'à la détection
suivante. Les analyses entre salves réappliquent les bandes et les seuils. Cette
convention aux limites de bandes doit être examinée lors de l'audit de reprise.
Un pôle utile situé sur un minimum d'erreur peut être compté sans être chargé.

Les couches fixes et bornes individuelles sont préservées. Le budget OT sélectionne
les états retenus entre salves, y compris le tour zéro ; il ne contraint pas chaque
itération interne du solveur. Le meilleur tour minimise son propre objectif chargé,
pas un score défini différemment après coup. Une annulation rend l'entrée initiale.

## Pilote final à 109 couches

Entrée : `A2_preparation_calculs_2026-11-05/pilote_109/initial_design.json`, inchangée.
Indices H = 2,35, L = 1,45, substrat = 1,52. Sept bandes, pas nominal 1 nm,
gamma = 1 nm, seuil d'erreur 0,001 en fraction, largeur estimée < 0,5 nm.
Les 109 couches varient avec un plancher physique de 0,1 nm et un budget de
15 000 nm OT. Les deux branches ont 40 salves de limite prescrite 30 évaluations,
ce qui n'égale ni le temps consommé ni le nombre réel d'évaluations.
Le témoin désactive les charges dans le même moteur ; il est recalculé, pas recopié.

| État | MF nominal (%) | MF résolu (%) | MF contrôle (%) | OT (nm) |
|---|---:|---:|---:|---:|
| Initial | 0,014511475 | 0,377693098 | 0,377696948 | 14 200,0 |
| Témoin nominal natif v3 | 0,014359441 | 0,382927201 | 0,382931105 | 14 198,7766 |
| Charge native v3 | 0,035728665 | 0,032430984 | 0,032427622 | 14 009,8181 |

Résolu : pas de 0,001 nm ; contrôle : 0,0002 nm. Le tour retenu est 40 dans les
deux branches. Le Code 1 indépendant retrouve le MF nominal chargé à environ
1,3 × 10⁻¹⁴ point de pourcentage près et les comptes `[0,0,0,3,0,1,0]`.
Les quatre pôles du domaine audité sont retrouvés avant et après, dont trois
maxima d'erreur chargés. L'amélioration du MF résolu est un facteur d'environ 11,65.

| Maximum chargé après traitement (nm) | Transmission (%) | Plus grand champ normalisé à cette longueur d'onde |
|---|---:|---:|
| 400,357962346 | 0,232314048 | 560,8593 |
| 416,912172389 | 0,271362067 | 2,3223 |
| 426,708116703 | 0,308349173 | 1,6216 |

Le plus haut pic de transmission n'est pas celui au champ interne le plus élevé.
Ces champs sont échantillonnés aux trois sommets, et ne sont pas un maximum sur
toutes les longueurs d'onde. Une amélioration spectrale ne garantit pas un faible champ.

Bruts définitifs : `pilote_natif_109_v3/` et `pilote_natif_109_temoin_v3/`.
Chaque dossier contient le manifeste, les épaisseurs à pleine précision, l'historique
des états et des scores, les audits et le résumé. Le pilote `pilote_natif_109.py`
refuse de remplacer un dossier existant. `preparer_figures_article.py` convertit
uniquement les métadonnées vers `pour_article/`, sans calcul optique ni recherche.
Le script de figures RICL lit ensuite ces données ; les anciennes campagnes restent intactes.

## Historique à ne pas confondre avec le résultat final

1. Le premier pilote dans les scripts donnait MF résolu 0,0539145 % et champ 794,27
   à un sommet. Il reste archivé dans la préparation ; il n'est plus présenté comme
   résultat natif final dans RICL.
2. La première tentative native a échoué quand un maximum mobile quittait sa
   fenêtre de détection. Le suivi à l'intérieur d'une salve est corrigé et testé.
3. Le prototype natif v2 donnait 0,0697821 % avec un champ échantillonné de 934,27.
   Un nouveau test du Jacobien mobile a montré que sa recherche du sommet par
   différences spectrales finies ne donnait pas une stationnarité suffisante.
   Le test a été gardé et le calcul du maximum corrigé avec la dérivée analytique.
   Les sorties v2 restent conservées. Sa source physique a été reconstruite et
   son empreinte vérifiée contre son manifeste dans `sources_v2/`.
4. Seul v3 est retenu pour le tableau et la figure de traitement du manuscrit.
   Une trajectoire non convexe ne doit pas être forcée à reproduire les chiffres
   d'un prototype avec d'autres détails numériques.

## Interface et sécurité de l'application

Onglet `Resonances` puis ouverture de l'outil. `Analyze` ne modifie pas le design ;
`Refine` prépare un résultat ; `Apply` l'applique explicitement et réévalue le score
DESIGN ordinaire. Les épaisseurs physiques restent à pleine précision.
L'outil refuse un résultat périmé si le design source a changé et revérifie les
limites actives du fichier. Les minima d'OT par couche sont combinés avec le plancher
physique, et la limite OT du fichier ne peut pas être desserrée par la boîte de dialogue.
Le plancher GUI par défaut est 5 nm ; le pilote libre utilise explicitement 0,1 nm.
Il ne faut donc pas prétendre que ce pilote respecte le réglage manufacturable de 5 nm.

Le travail est asynchrone ; la fermeture attend l'arrêt du travail en cours.
L'ouverture seule n'exécute aucun calcul et ne change aucun bit des épaisseurs.
Le démarrage refuse les calculs concurrents et attend la fin du préchauffage initial.
Un essai sur la vraie fenêtre DESIGN, avec un Fabry--Perot constant de 31 couches,
a détecté un pic en laissant le design inchangé (`controle_gui_reel.txt`,
`interface_resonances.png`, `fabry_perot_gui.json`). Cet essai visuel précède
l'amélioration v3 de la stationnarité ; le contrôle final est distingué dans la reprise.

## Validation et limites de la preuve

- Contrôles ciblés finaux : **40 passés en 8,69 s**, y compris les frontières
  d'architecture, le Jacobien au maximum mobile, les bornes et les verrous, le
  refus des modèles hors domaine, l'absence de calcul à l'ouverture, l'application
  explicite, le refus d'un résultat périmé et un calcul asynchrone réel.
- Ruff final : tous les contrôles passent, avec l'avertissement général du support
  Python 3.15 en développement ; aucune règle assouplie, aucun `--fix`.
- Oracle final : **1 179 passés** ; la suite générale se poursuit dans
  `validation_finale/` et `validation_finale_execution.txt`.
- Avant intégration : oracle 1 165 avant/après préparation, validation parallèle GO.
  Un passage complet en série avait bloqué en préparation GUI ; le fichier concerné
  passait isolément. Cela reste une limite documentée, pas une preuve « tout en série ».
- Le validateur parallèle rejoue les échecs seuls. Son GO signifie absence d'échec
  persistant selon ce protocole ; il ne signifie pas une suite entière passée en série.
- Aucun noyau historique modifié et chemin optionnel inactif par défaut. Le corpus
  complet `c1_diff` de 9 092 tableaux n'est pas relancé ici ; aucun verdict C1 de ce
  corpus n'est revendiqué pour cette intégration.

Les trois fichiers suivis déjà modifiés par l'auteur (`search.py`, `cissoid_opt.py`,
`cissoid_islands.py`) sont identiques à leurs empreintes de début de travail.
La vérification, y compris la concordance source v3/manifeste, est dans
`preservation_verifiee.json`.

Ne sont pas réalisés : traitement des 232 candidats de l'union des frontières,
Monte Carlo apparié avant/après, extension de l'outil natif aux métaux, à la dispersion
ou à l'oblique. RICL ne tire aucune conclusion de tolérance du seul pilote traité.
La publication exige encore les métadonnées d'auteurs et le dépôt de l'archive et
d'un identifiant de version logicielle ; un fichier local figé n'est pas un dépôt public.

## État exact au relais immédiat demandé par l’auteur

La suite générale a passé 1 179 oracles et 1 355 tests d’interface (12 ignorés,
2 xfail). La suite unitaire a donné 5 770 succès, 7 ignorés, 1 xfail et deux
échecs réels du cliquet `test_ci_lambda_connect_audit.py` : trois nouvelles
connexions Qt anonymes dépassaient le plafond 44. Elles sont remplacées dans
le code par des slots nommés, sans modifier le plafond ni la physique.
Le test asynchrone clique maintenant le vrai bouton, et un test supplémentaire
vérifie les deux commandes et la libération du dialogue à la fermeture.
**Ces derniers changements des connexions restent à retester au relais.**
La capture et le contrôle ciblé à 40 succès précèdent ce correctif.

La suite `rest` est encore en cours et a signalé un échec, à examiner après son
rejeu automatique. La performance n’est pas encore clôturée. Le processus de
validation peut terminer après l’écriture de ce rapport : lire d’abord
`validation_finale/summary.txt` s’il existe et les journaux de rejeu.
Le journal général conservera le NO-GO du premier passage unitaire même après
correction des slots ; ne pas le remplacer ou l’étiqueter comme un simple artefact.

Reprise prioritaire, quand la validation en cours est terminée :

```powershell
python -m pytest tests/unit/test_ci_lambda_connect_audit.py tests/oracle/test_design_complex_wavelength_resonances.py tests/unit/test_design_resonances_input_boundary.py tests/ui/test_design_resonance_tool.py tests/unit/test_the_architecture_debt_only_shrinks.py -q --no-cov
python -m ruff check .
```

Utiliser le Python 3.15.2 explicitement identifié dans les manifestes. Le ZIP des
sources finales contient les corrections de slots ; sa version antérieure est
conservée avec le suffixe `avant_correction_signaux`. Le moteur physique reste
identique au manifeste du pilote v3. Le rapport complet de reprise figure dans
`RICL_article/REPRISE_OPUS_5_5_2026-11-05.md`.
