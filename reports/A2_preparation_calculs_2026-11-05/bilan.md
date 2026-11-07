# RICL — corrections et premier calcul contrôlé, 5 novembre 2026

## 1. Blocage technique levé

Ruff échouait sur deux erreurs B905 dans les copies historiques
`hidden_resonances_code1_2026-11-02_before_localmax.py` et
`hidden_resonances_code1_2026-11-03_before_top.py`. L'avertissement sur Python 3.15,
affiché à la fin du diagnostic de démarrage, masquait cette cause.

Les deux appels utilisent désormais `zip(..., strict=False)` : le comportement de
troncature antérieur est explicitement conservé, y compris pour des listes de
longueurs différentes. Aucune formule optique n'est modifiée. Ruff passe et le
précontrôle renvoie `PREFLIGHT=GO`.

Les originaux de six fichiers sont conservés dans
[`sources_avant_correction.zip`](sources_avant_correction.zip), avec leurs
[`empreintes SHA-256`](sha256_avant.json). Le diff antérieur des trois fichiers
`search.py`, `cissoid_opt.py` et `cissoid_islands.py` est également conservé dans
[`modifications_preexistantes.diff`](modifications_preexistantes.diff). Ces trois
fichiers ne sont ni réinitialisés, ni incorporés à un commit. Leur présence est un
avertissement non bloquant du précontrôle. Aucun push n'est effectué.
Leurs empreintes après intervention sont identiques aux empreintes initiales
([contrôle](sources_preexistantes_preservees.json)).

## 2. Incohérence de méthode corrigée

Dans `threeline_track.track`, l'option `TRACK_PEAK=top` applique maintenant au
classement des tours la même évaluation au sommet réel que celle employée par
`polish`. Les hauteurs rapportées et l'échantillonnage du champ suivent également
ce sommet. L'estimation de longueur d'onde issue du pôle reste utilisée pour
initialiser sa recherche, conformément à A1.

Le score chargé vaut, en pour cent,

\[
100\sqrt{\frac{\sum_{i=1}^{277}(T_i-T'_i)^2+
\sum_{p}(T(\lambda_{p,\max})-T'(\lambda_{p,\max}))^2}{277}}.
\]

Le dénominateur reste celui de la grille nominale. Il faut distinguer ce score de
sélection du MF résolu utilisé pour comparer les sorties.

Deux tests échouaient sur l'ancien code : la hauteur et le champ étaient évalués
au mauvais endroit, et le mauvais tour était retenu dans un cas à deux sommets
décalés. Ils passent après correction. Trois autres contrôles couvrent le mode
historique, le témoin nominal et la restitution exacte des épaisseurs exportées.
Les journaux avant/après sont conservés.

Le comportement historique par défaut reste celui de l'estimation au pôle.
Les ajouts sont explicites : mode `nominal` pour le témoin et argument
`precise=True` pour conserver les épaisseurs et scores à 17 chiffres significatifs.
Les noyaux CERTUS ne sont pas modifiés.

## 3. Protocole exécutable

[`pilote_threeline.py`](pilote_threeline.py) fixe les options corrigées avant
l'importation des modules : détection complexe, maxima locaux du signal de phase,
départs multiples denses et charge au sommet réel. Il réutilise les noyaux CERTUS
existants et importe en lecture seule le Code 1 de l'article soumis, dans
`OE_resonances/code/hidden_resonances.py`, comme référence indépendante.

Constantes utilisées : γ = 1 nm, seuil de hauteur préliminaire 0,001 et largeur
de pôle inférieure à 0,5 nm pour la charge ; indice H = 2,35, L = 1,45,
substrat = 1,52 et milieu incident = 1. Les matériaux sont non dispersifs et sans
pertes. Le domaine spectral reste celui des sept bandes du problème trois raies.

Le pilote :

1. compare les transmissions, positions des pôles et sommets avec cette référence
   sur le design de 101 couches ;
2. vérifie le design initial propre à RICL ;
3. exécute séparément le raffinement nominal et le raffinement avec charge, depuis
   exactement les mêmes épaisseurs ;
4. retient, dans chaque branche, le tour de meilleur objectif propre parmi les
   états admissibles, en incluant le tour initial ;
5. vérifie indépendamment les deux sorties retenues.

Chaque branche reçoit 40 tours et la même limite de 30 évaluations par appel au
raffinement. Ce sont des limites prescrites identiques, pas une égalité des nombres
effectifs d'évaluations ou du temps de calcul.

Le comptage indépendant utilise les sept rectangles de bandes, avec
−0,25 < Im λ < 0 nm pour comparer les pôles physiques. La localisation de référence
est effectuée avant le filtrage de charge par hauteur et largeur ; le comptage
n'est donc pas comparé au seul nombre de pics chargés. Une discordance arrête le
pilote et les diagnostics sont conservés.

Les états retenus doivent avoir des épaisseurs finies ≥ 0,1 nm et une épaisseur
optique ≤ 15 000 nm. **Les trajectoires intermédiaires du raffinement ne sont pas
contraintes en OT** : les tours hors budget sont exclus de la sélection. Ce choix
doit être déclaré ; il ne faut pas le présenter comme un optimiseur sous contrainte
d'OT à chaque itération. Des tests couvrent le dépassement du plafond, les états
non finis, les couches trop minces et les longueurs de données incohérentes.

Le dossier de sortie doit être nouveau. Il contient les paramètres, les versions,
les empreintes des sources et entrées, tous les tours, les états retenus et les
audits. Aucun résultat ancien n'est écrasé.
Les sources effectivement utilisées ont été vérifiées contre le manifeste du
pilote et figées dans [`sources_calcul_pilote_109.zip`](sources_calcul_pilote_109.zip),
y compris la référence A1 lue sans modification.

Commande exécutée depuis la racine CERTUS :

```powershell
python reports/A2_preparation_calculs_2026-11-05/pilote_threeline.py --rounds 40 --out reports/A2_preparation_calculs_2026-11-05/pilote_109
```

## 4. Résultats mesurés sur le filtre de 109 couches

Entrée : meilleur `mf_oracle` de `gradual_deep2_cont_seed89_clean2.csv`. Les
[`résultats complets`](pilote_109/summary.json) et le
[`journal`](pilote_109.log) sont conservés.

| État | MF nominal (%) | MF résolu, 0,001 nm (%) | MF de contrôle, 0,0002 nm (%) | OT (nm) |
|---|---:|---:|---:|---:|
| Initial | 0,0145115 | 0,3776931 | 0,3776969 | 14 200,0000 |
| Raffinement nominal, tour 40 | 0,0143594 | 0,3829272 | 0,3829311 | 14 198,7766 |
| Charge corrigée, tour 40 | 0,0592200 | 0,0539145 | 0,0539098 | 14 144,9267 |

La charge abaisse le MF résolu d'environ un facteur 7 par rapport à l'état initial.
Le témoin nominal améliore légèrement le MF nominal tout en dégradant le MF résolu.
Ce cas permet donc de distinguer l'effet du traitement de celui d'un simple
raffinement nominal supplémentaire. Il ne suffit pas à généraliser l'effet à toute
la frontière.

Les deux sorties restent admissibles ; aucun tour n'est exclu pour dépassement
d'OT. Les écarts relatifs entre les deux grilles de jugement sont de 0,00102 % pour
le témoin et 0,00867 % pour la charge. Cela contrôle ici le MF intégré ; cela ne
constitue pas une borne universelle sur tous les maxima spectraux.

Les audits de référence et des trois états propres au pilote passent. Dans les
sept rectangles, les nombres localisés et comptés coïncident : quatre pôles pour
le design initial et le témoin, trois pour la sortie chargée. Le nombre de pics
effectivement chargés peut être inférieur au comptage avant filtrage.

## 5. Conséquence importante pour le champ interne

Au tour 40, les trois pics chargés ont les valeurs suivantes. La hauteur est une
fraction de transmission ; elle est convertie en pour cent dans le tableau.

| Sommet réel (nm) | Hauteur (%) | Maximum de \|E\|² dans l'empilement à ce sommet |
|---|---:|---:|
| 403,351674 | 0,625203 | 794,27 |
| 414,932800 | 0,414026 | 3,21 |
| 425,835179 | 0,544292 | 3,65 |

Le pic initial le plus élevé atteignait 55,2907 %, avec un champ de 5 299,77 à
son sommet. **Le nouveau résultat n'autorise pas à écrire que le champ est ramené
à 3.** Il reste proche de 794 au sommet du pic le plus élevé, malgré la très forte
baisse de transmission. La charge spectrale n'est pas un objectif de minimisation
du champ interne.

Le tour 37 illustre aussi la différence entre critères : MF résolu 0,0624558 % et
champ 3,93 au sommet du pic alors le plus élevé ; le tour 40 a un meilleur objectif
chargé mais un champ plus fort à son pic le plus élevé. Ces échantillonnages ne
déterminent pas le maximum global du champ sur tout le domaine spectral. On ne peut
pas davantage conclure que le champ maximal de tous les pics du tour 37 était 3,93.

Les zéros `highest`, `peaks` et `e2max` de la branche nominale des CSV historiques
de `track` sont des sentinelles : cette branche n'effectue pas ces diagnostics
pendant le raffinement. Ils ne prouvent ni absence de résonance ni champ nul.
L'audit indépendant de la sortie nominale retrouve notamment un pic de 55,24 % et
un champ de 5 165,74 à son sommet. Pour interpréter le champ, utiliser les listes
`charged_peaks` des fichiers d'audit et leur `field_scope`, pas ces sentinelles.

## 6. Portée et suite scientifique

Ce calcul corrige et valide le protocole sur un premier cas. Il ne met pas à jour
les 58 anciens traitements, ni les 232 candidats de l'union des frontières, ni le
Monte-Carlo. Les anciens résultats restent conservés et ne deviennent pas des
applications de la méthode finale par simple changement de légende.

La suite reste celle du
[plan de calcul RICL](../../../../RICL_article/besoin_nouveaux_calculs_2026-11-05.md) :
audit de l'union des frontières, traitement ciblé avec témoin, puis comparaisons
appariées avant/après sous erreurs d'épaisseur. Les classements doivent être
reconstruits à partir de ces sorties avant toute revendication générale.

Le manuscrit A1 soumis n'est pas modifié. Les corrections à reporter dans RICL,
dont la distinction entre baisse des pics et baisse du champ, sont consignées
dans son dossier d'audit.

## 7. Validation logicielle

Oracle avant correction : **1 165 tests passés**. Oracle après correction :
**1 165 tests passés**. Ruff : **All checks passed!**. Le pilote termine par
**PILOT=GO** ; ses accords de grille sont rapportés séparément ci-dessus.

La validation générale en série a été interrompue après un blocage prolongé dans
la préparation de
`test_design_restarts_from_its_best_design.test_no_restart_when_turned_off`.
Le diagnostic en lecture seule du processus identifie la phase `setup`
([trace](diagnostic_validation.txt)). Le fichier complet rejoué seul passe :
**4 passed in 4.74s** ([journal](diagnostic_design_restarts.txt)). Le journal de la
suite interrompue est conservé ; il ne prouve pas « 0 failed » pour la suite entière.

La reprise emploie le validateur existant `scripts/validate_parallel.py`, avec
15 workers, au plus 6 pour l'interface et rejeu isolé des échecs. Une seule étape
de validation est exécutée à la fois ; le pilote optique est déjà terminé. Un GO
de ce validateur ne sera pas présenté comme un passage complet en série.

La suite unitaire parallèle donne **5 765 passed, 7 skipped, 1 xfailed**, avec un
échec supplémentaire de `test_design_scheduled_tasks_run.test_a_scheduled_task_runs_after_its_delay`
pour la tâche `schedule_smart_decimation_remove_and_optimize`. Le rejeu de ce cas
seul donne **1 passed in 2.17s** : aucun échec unitaire persistant n'est établi par
ce passage. Les onze tests du protocole et de l'admissibilité font partie de cette
collecte. Les journaux sont dans `validation_parallele/`.

Bilan final : **VALIDATION=GO** du validateur parallèle. Les trois contrôles
documentaires passent. Interface : **1 349 passed, 12 skipped, 2 xfailed** ; reste
(hors performance) : **321 passed** ; performance, en série : **29 passed, 2 skipped**.
Le seul échec parallèle est le cas unitaire rejoué avec succès décrit ci-dessus.
Ce verdict ne remplace pas un passage intégral en série, interrompu sur le blocage
GUI documenté. Aucun noyau applicatif n'est modifié pour contourner ce blocage.
