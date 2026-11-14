# Polissages du modèle infrarouge INDEX

Le chantier 12 porte sur les L-BFGS-B des étapes 0 et 2, autour de la recherche PGLOBAL. La correction
D112 du centre de bande est vérifiée dans le [bilan des dérivées](../audits_2026-11-13/bilan.md).

## Mesure appariée

Le [script](../../scripts/probe_index_ir_polish.py) prend les deux départs effectivement produits par
le parcours INDEX du classeur `H400-RTNBrel-sapphire.xlsx`. Sur chacun, il compare différences finies et
gradient avec les mêmes bornes, tolérances et budget. Les noyaux sont amorcés avant la mesure.
Le calcul principal garde le résultat du bras en différences finies, donc chaque paire partage son départ.

| Graine | Étape | Différences finies (s) | Gradient (s) | Accélération | Variation de RMSE |
|---:|---:|---:|---:|---:|---:|
| 42 | 0 | 0,6896 | 0,0754 | ×9,15 | +0,00024 % |
| 42 | 2 | 0,4718 | 0,0350 | ×13,49 | < 0,000001 % |
| 77 | 0 | 3,1183 | 0,2569 | ×12,14 | +0,1963 % |
| 77 | 2 | 0,7022 | 0,0872 | ×8,05 | < 0,000001 % |
| 202 | 0 | 0,7704 | 0,1148 | ×6,71 | < 0,000001 % |
| 202 | 2 | 0,1577 | 0,0030 | ×53,10 | < 0,000001 % |

Le temps cumulé des deux polissages passe de 0,93–3,82 s à 0,11–0,34 s. Il s'agit du coût local.
Le parcours comprend aussi le calcul TLU, les amorces Sellmeier, PGLOBAL, les splines et la réduction des nœuds.
Le résultat ne mesure donc pas cette accélération sur toute l'application. Un minimum local légèrement
différent est observé sur la graine 77.

## Raccordement et activation

Le fichier de configuration INDEX accepte `optimization.ir_analytic_polish`, booléen faux par défaut.
Le champ est transmis au worker, conservé lors de l'enregistrement et réinitialisé par Reset.
À l'activation, les deux appels L-BFGS-B reçoivent `IRGlobalObjective.polish_gradient`. Ce dernier fournit
la dérivée nulle du coût constant de rejet, y compris pour les pôles interdits. Dans le domaine admissible,
il réutilise le gradient existant.

Le mode `--analytic` de la sonde charge ce réglage depuis le format de configuration de la fenêtre,
contrôle sa transmission au worker et vérifie la présence du Jacobien aux deux appels. Les trois parcours
complets aboutissent. Ils vérifient l'intégration de l'option. Le tableau ci-dessus porte la comparaison
appariée des polissages.

Les différences finies couvrent transmission, réflexion, données combinées, normalisation, substrat absorbant
et verre dépoli. Les 64 tests ciblés couvrent aussi le centre de bande et le plateau de rejet.
L'oracle passe avec 1 204 tests avant et après raccordement.
[Mesures individuelles et résultats des parcours](results.json).
