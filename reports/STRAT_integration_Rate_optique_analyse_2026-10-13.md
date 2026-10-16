# STRAT — mieux chercher l'alternance Rate / optique (2026-10-13)

La première amélioration à essayer est **de répartir le budget de recherche entre les formes de mouvements Rate**.
La suivante est **d'ouvrir une fenêtre optique en choisissant aussi sa longueur d'onde**. Le noyau permet déjà
l'alternance ; la recherche la parcourt avec un ordre et des voisinages qui peuvent la limiter.

Analyse du code `da1af082`, de deux artefacts existants et des générateurs de listes de candidats. Aucun nouveau
calcul de croissance, aucun rejeu Monte-Carlo, aucun test concurrent à A2. Les propositions ci-dessous n'ont
pas de gain scientifique mesuré et aucun réglage de production n'est modifié.
La précision de 👤 sur les variations de vitesse est consignée dans [ETAT §0](../docs/ETAT.md).

## 1. Ce qui fonctionne déjà

- [`_rate_layer_thickness`](../certus/physics/certus_strat_growth.py) estime séparément les deux matériaux
  H/L, représentés par la parité des couches : moyenne de `d_nominal / d_real` sur les couches antérieures
  du même matériau déposées sous contrôle optique. Les couches Rate sont exclues de cette moyenne.
- Chaque tirage possède son propre historique d'épaisseurs dans
  [`simulate_stack_robustness_batch`](../certus/physics/certus_strat_batch.py). L'estimation utilise les
  couches de ce dépôt ; elle ne reprend pas la calibration d'un autre tirage.
- Une couche Rate efface l'historique optique empruntable par la suivante : `block_start[i] = i` après
  du Rate, même si la longueur d'onde reste identique. Le retour à l'optique est possible, mais son premier
  arrêt doit fonctionner avec les informations disponibles depuis cette reprise.
- Une nouvelle couche optique entre ensuite dans l'estimation Rate de son matériau. Une fenêtre de deux
  couches consécutives apporte une référence H et une référence L ; une couche seule n'en apporte qu'une.
- [`_elite_rate_moves`](../certus/core/certus_strat_robustness_rate.py) agrandit ou raccourcit les paquets,
  ferme des trous d'optique, ouvre des fenêtres de 2 ou 4 couches et insère des paquets Rate de ces largeurs.
  Les positions d'ouverture sont espacées de 3 couches. `elite_rate_moves` est actif par défaut.

Le noyau garde le niveau d'arrêt calculé sur le nominal et les défauts de production. Optimiser la reprise
ne doit pas donner au contrôleur les épaisseurs réelles que seul le simulateur connaît, ni lui restituer
les extrema traversés pendant une couche non observée.

## 2. Deux plans existants éclairent la recherche

Les couches ci-dessous sont numérotées à partir de 1. Les deux composants ont des épaisseurs différentes :
leurs SEEL ne se comparent pas entre eux.

| artefact et provenance | meilleur plan déposable | références H/L avant chaque paquet Rate |
|---|---|---|
| [`r75x0.5`, deep, graine 101, `cea0db66`](STRAT_ELITE_couches_Rate_2026-10-12/blocs_vs_plantage_r75x0.5_deep_s101_ratemoves_cea0db66.json) ; id `900951015`, SEEL 0,396715 nm | Optique L1–6 à 630 nm → Rate L7–10 → Optique L11–12 à 451 nm → Rate L13–34 → Optique L35–36 à 706 nm → Rate L37–75 | 3/3 → 4/4 → 5/5 |
| [`r75x1.5`, deep, graine 42, `da1af082`](STRAT_ELITE_couches_Rate_autres_composants_2026-10-13/r75x1.5_deep_s042_avec_da1af082.json) ; id `901550854`, SEEL 0,471784 nm | Optique L1–11, à 562 puis 571 nm → Rate L12–52 → Optique L53 à 651 nm → Rate L54–75 | 6/5 → 7/5 |

Les artefacts portent `git_dirty=false`, un cache Numba identifié et régi par les sources, et un taux de
plantage nul aux trois niveaux de bruit pour ces meilleurs plans. Le premier est un résultat antérieur ;
le second est la première exécution terminée d'A2. Sa comparaison avec `elite_rate_moves=false` reste en cours
au moment de cette analyse.

Ces formes donnent deux pistes, sans isoler leur contribution au SEEL : la reprise optique peut compenser
une partie de l'erreur amont et elle ajoute des références à la calibration du Rate suivant. Le nombre de
références augmente effectivement ; une amélioration de la précision de leur moyenne n'est pas garantie,
car les erreurs des couches optiques peuvent être biaisées ou corrélées. Le plan à L53 montre aussi qu'une
fenêtre d'une seule couche peut être retenue : imposer systématiquement des paires H/L serait prématuré.

## 3. Premier point concret : le plafond coupe les formes dans un ordre biaisé

Dans `_elite_rate_moves`, l'ordre est : extrémités de tous les paquets, fermeture des trous, fenêtres de
2 couches, fenêtres de 4 couches, puis insertion de Rate dans l'optique. `_elite_rate_candidates` alterne
les parents, mais conserve cet ordre à l'intérieur de chacun. Le plafond de 120 candidats supplémentaires
dans [`_generate_elite_candidate_strategies`](../certus/core/certus_strat_consensus.py) coupe cette liste.

**Comptage structurel effectué le 2026-10-13**, avec les fonctions de listes extraites par AST, sans importer
CERTUS ou Numba. Deux ensembles de couches Rate, 75 couches, dix parents distincts par leur longueur d'onde,
120 candidats. Ces parents sont des exemples construits ; ils ne reproduisent pas la sélection des parents
d'une passe réelle. Une liste finale d'artefact ne permet pas de reconstituer cette sélection.

| ensemble Rate du parent | mouvements disponibles par parent | mouvements retenus sur dix parents avec le plafond de 120 |
|---|---|---|
| queue L15–75 | 3 changements d'extrémité ; 20 fenêtres optiques de 2 couches ; 19 de 4 ; 6 insertions de Rate | 30 changements d'extrémité + 90 fenêtres de 2 couches ; **aucune fenêtre de 4, aucune insertion de Rate** |
| L7–10, L13–34, L37–75, masque du meilleur `r75x0.5` | 11 changements d'extrémité ; 2 fermetures ; 20 fenêtres de 2 ; 18 de 4 ; 1 insertion de Rate | 110 changements d'extrémité + 10 fermetures ; **aucune ouverture optique** |

Dans l'exemple de queue, les neuf ouvertures explorées par parent vont de L16–17 à L40–41. Les ouvertures
plus profondes restent au-delà du plafond. Les doublons, le nombre de parents et leurs masques peuvent
changer ce bilan dans une vraie passe ; le biais de troncature, lui, est présent dans le générateur.

**Changement proposé en premier, à budget constant :** faire alterner les types de mouvements et leurs
largeurs, en plus des parents ; répartir les premières positions entre le début, le milieu et la fin de
chaque paquet. Conserver les mouvements d'extrémité. Une option expérimentale inactive par défaut doit
laisser exactement l'ordre actuel lorsqu'elle est éteinte, selon C1.

Il faut compter, pour chaque type, les candidats disponibles, proposés après déduplication, évalués à fond
et retenus. Le journal actuel `[ELITE-RATE]` donne le total, pas cette répartition. Augmenter seulement le
plafond est un autre essai, déjà prévu en A5 ; il ne teste pas le même changement.

## 4. Deuxième point : chercher ensemble la fenêtre et sa longueur d'onde

Une mutation Rate garde les blocs et leurs longueurs d'onde. Une mutation de longueur d'onde garde le
masque Rate. Une reprise optique est donc d'abord essayée à la longueur d'onde héritée du parent.
Si elle échoue à cette longueur d'onde, son éventuelle amélioration à une autre longueur d'onde peut
rester inaccessible à une recherche qui ne conserve que les étapes intermédiaires assez bonnes.
L'importance de cet effet n'est pas mesurée.

**Voisinage proposé ensuite :** dans un bloc entièrement au Rate, proposer ensemble une fenêtre optique
et quelques longueurs d'onde de la grille de contrôle existante. Le nombre et les bornes des blocs peuvent
rester inchangés dans ce premier cas. Les couches réouvertes sont alors les seules du bloc à utiliser la
nouvelle longueur d'onde. Une extension aux fenêtres traversant plusieurs blocs est une action séparée.

Le choix doit regarder la capacité d'arrêter la première couche après la coupure d'historique, puis la
fenêtre complète et le dépôt qui suit. Le swing nominal de Phase A peut aider à proposer des candidats,
mais ne suffit pas à prédire la reprise sur un empilement dont les couches Rate ont accumulé de l'erreur.
La robustesse complète conserve le dernier mot : SEEL, plantage au pire bruit, même fente et mêmes tirages.
Il ne faut pas remplacer cette évaluation par une somme de coûts locaux supposés indépendants.

## 5. Éviter de dépenser la recherche sur des longueurs d'onde non utilisées

Les blocs restent présents même lorsqu'ils sont entièrement au Rate. Dans les deux meilleurs plans lus :

| plan | blocs entièrement Rate / blocs totaux | mutations de longueur d'onde ±1 portant sur ces blocs / toutes les mutations de longueur d'onde |
|---|---:|---:|
| `r75x0.5`, graine 101 | 6/9 | 12/18 |
| `r75x1.5`, graine 42 | 12/15 | 24/30 |

`_elite_moves` propose ces mutations. Pour une couche effectivement au Rate, le noyau retourne son
épaisseur avant de simuler le signal optique. Un changement de longueur d'onde sur un bloc entièrement
Rate consomme donc du voisinage sans réouvrir le contrôle optique de ce bloc.

Une réduction de ces candidats demande toutefois une vérification complète :
[`_calculate_strategy_spectral_resolution`](../certus/core/certus_strat_robustness_slit.py) parcourt encore
toutes les couches, sans consulter `rate_layers`. Sa limite intervient dans les propositions de fente et
dans un critère de classement. Une longueur d'onde non observée peut ainsi changer un diagnostic ou la
recherche. Avant de définir une signature des seules couches optiques ou de supprimer ces mutations,
il faut vérifier cette route et distinguer le profil nécessaire à une future réouverture de la limite
de fente applicable au plan actuel. Aucun candidat n'a été supprimé dans cette analyse.

La diversité des parents mérite également une mesure par masque Rate et par fenêtres optiques effectives.
La diversité actuelle par `_origin_family` classe les descendants Rate d'ELITE comme `ELITE` ; cette étiquette
ne décrit pas la forme de l'alternance. Des masques distincts ne garantissent cependant pas des résultats
meilleurs : il faut compter la couverture obtenue avant de réserver un quota.

## 6. Calibration propre au dépôt et rôle des fenêtres

Avec un écart de vitesse entre dépôts, la logique recherchée est : établir la vitesse de chaque matériau
à partir des couches optiques du dépôt courant, traverser au Rate les couches moins favorables, reprendre
l'optique là où un arrêt fiable peut corriger l'erreur accumulée, puis utiliser les nouvelles références
pour le Rate suivant. Le code possède déjà cet historique propre à chaque tirage.

Sous l'hypothèse d'une vitesse constante pendant un dépôt, sa valeur apparaît à la fois dans les tours
mesurés sur les couches de calibration et dans la croissance des couches Rate. Dans le modèle décrit
au-dessus de `_rate_layer_thickness`, elle se compense dans la commande non arrondie. Ajouter un bruit
indépendant seulement aux couches Rate ne représenterait donc pas cet écart entre dépôts. Une éventuelle
extension physique devra distinguer vitesse réelle, estimation issue des observations et variation durant
le dépôt ; aucune amplitude ou loi temporelle nouvelle n'est choisie ici.

Pour comprendre les fenêtres existantes, un futur rejeu diagnostique peut comparer : le plan avec sa fenêtre,
le plan qui remet cette fenêtre au Rate, et le plan qui garde la fenêtre optique mais exclut ses nouvelles
références de la calibration Rate. Ce dernier est une ablation de recherche, pas une règle de production.
Il faut conserver les mêmes tirages et rapporter les effets conditionnels : compensation et calibration
sont couplées, leur apport ne se somme pas en général.

## 7. Mise en œuvre et mesure après A2

1. Terminer A2 sur son code figé. Elle établit le comportement actuel et ne doit pas recevoir ces propositions
   pendant son exécution.
2. Essayer d'abord la répartition des mouvements à 120 candidats, séparément des changements de longueurs
   d'onde. Garder le chemin inactif identique, les interdits L1/L2, la dernière couche autorisée, la provenance,
   les mêmes tirages C2, le biais de fente et tous les défauts de production.
3. Faire la validation complète du projet, la revue de code et les tests de routage ; respecter les plafonds
   de taille de `certus_strat_consensus.py`. Aucun test nouveau ne doit seulement recopier le nouvel ordre :
   vérifier la couverture des familles sous plafond, la déduplication et l'inertie du chemin éteint.
4. Mesurer une seule variante à la fois, sur `r75x0.5` aux graines 42/101/202, puis le juge de paix et les
   composants d'A2. Consigner SEEL, RMSE par bruit, déposables, forme des fenêtres, compteurs par mouvement
   et durée ; rejouer les plans retenus sur des graines de validation distinctes de celles de recherche.
5. Essayer ensuite le voisinage conjoint fenêtre/longueur d'onde, avec le même protocole et un budget borné.
   Aucun défaut nouveau n'est activé sur la seule base de cette analyse.

## Reproduction du comptage structurel

Le comptage n'appelle que des fonctions produisant des listes. Extrait suffisant pour retrouver les deux
budgets et voir les fenêtres qui passent ; à exécuter depuis la racine du dépôt avec le code `da1af082` :

```python
import ast
import itertools
from pathlib import Path
from typing import Any

path = Path("certus/core/certus_strat_robustness_rate.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
names = {
    "RATE_MIN_LAYER", "ELITE_RATE_WINDOWS", "ELITE_RATE_STEP", "ELITE_RATE_FILL_MAX",
    "_rate_runs", "_elite_rate_moves", "_elite_rate_candidates",
}
nodes = [
    node for node in tree.body
    if (isinstance(node, ast.FunctionDef) and node.name in names)
    or (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        and node.target.id in names)
]
scope = {"Any": Any, "itertools": itertools}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), scope)

for rates in [list(range(14, 75)), [*range(6, 10), *range(12, 34), *range(36, 75)]]:
    parents = [{"strategy": {
        "strategy_id": rank,
        "blocks": [{"start": 0, "end": 75, "wavelength": 500.0 + rank}],
        "rate_layers": rates,
    }} for rank in range(10)]
    available = scope["_elite_rate_moves"](rates, 75)
    selected = scope["_elite_rate_candidates"](parents, 75)[:120]
    print("available per parent:", len(available), "selected:", len(selected))
    print("first parent removals:", [
        sorted(set(rates) - set(new))
        for sid, _, _, new in selected if sid == 0
    ])
```

Sortie observée : 48 puis 52 mouvements disponibles par parent, 120 sélectionnés dans chaque exemple.
Le second ne retire à chaque parent que les extrémités des trois paquets, jamais une fenêtre intérieure.
SHA256 du texte source lu en UTF-8 :
`39eeeddc551fd7acb8d68daff255190d95337dbbcb327c446608393ed0e0809a`.
