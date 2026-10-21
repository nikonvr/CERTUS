# A3 — Conditions lues et limites du dépouillement

Lecture statique du 21 octobre, tête `85a9e82f`. Aucun résultat supplémentaire produit.
Source des réglages : `params_effectifs.json`, capturé par le vrai chargeur avant la campagne.

| profil | mode | fente de base (nm) | recherche de fente |
|---|---|---:|---|
| 48 couches | premium | 2 | oui |
| 75 couches livré | fast | 2 | non |
| vrai 35 couches dérivé | deep | 2 | oui |
| 36 couches deep livré | deep | 2 | oui |
| r75x2 natif | deep | 1 | non |
| r75x2 avec rampes livrées | deep | 2 | non |

Les six profils ont les graines collectées robustesse 42 et phase A 42. La recherche de fente active
interdit de décrire la fente de base comme une largeur imposée à tous les candidats ; la sortie officielle
`RANK00` ne donne pas la largeur propre du plan. Ne pas l'inventer à partir de ses longueurs d'onde.

Le banc extrait `RESULT` avec `certus_strat_service.extract_best_rmse`, puis imprime les dix premiers
résultats du classement reçu. Conserver séparément ce minimum, le score arrondi et l'identité de `RANK00`.
Le banc n'exporte pas les métadonnées de consensus et les frontières complètes de chaque plan : ne pas
présenter sa liste de longueurs d'onde comme un plan de fabrication complet ou une preuve de population optique pure.
Le consensus est appliqué aux candidats sélectionnés ; une population retournée n'est pas, par elle-même,
une preuve que chaque ligne porte un score de provenance homogène.

Les recherches locales acceptées repassent par `run_final_simulation_block` avec `refine=False` :
cela coupe ELITE, mais pas le classement de consensus pré-ELITE. Ne pas confondre ce drapeau avec une
désactivation du consensus. Les métadonnées effectivement exportées restent nécessaires à une comparaison homogène.
Les tableaux d'A5 devront les vérifier sur chaque meilleur plan.

Ces précautions ne changent aucun résultat officiel. Les scores de classement des bancs et le P95 spectral
du 99 couches assemblé restent des objets distincts. Les recherches ne constituent pas une confirmation indépendante.
