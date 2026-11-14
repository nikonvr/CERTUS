# Gradient de l'objectif FIELD

Le [profilage du worker](../../scripts/probe_field_polish.py) porte sur le miroir d'exemple à 14 couches,
trois longueurs d'onde et 45° en polarisation P. Le calcul complet à la graine 42 prend 2,22 s.
Ses trois descentes locales prennent 0,46 / 0,72 / 0,71 s. L'évaluation de l'objectif y absorbe environ 91 %
du temps des descentes. L'amorçage de Numba est extérieur à cette mesure.

## Dérivation et périmètre

FIELD fournit des indices réels au calcul de champ. Le gradient dérive directement les traces de champ
produites par `_calculate_field_single_pol`. Il utilise leurs admittances et leurs amplitudes aux interfaces.
Le calcul du champ conserve son implémentation d'origine. Le gradient des épaisseurs est converti en gradient
des facteurs QWOT. Le préalable D113 cité dans l'audit concerne un gradient absorbant externe au calcul du champ.

Les pics échantillonnés et les maxima internes d'onde stationnaire suivent les mêmes branches que le calcul
primal. Pour la lumière non polarisée, les valeurs et dérivées S/P sont moyennées avant de chercher le maximum
par matériau. La dérivée de l'objectif conserve la longueur d'onde active, la pénalité de réflexion et le
mode de seuil ou de minimisation du champ. À une égalité entre maxima, elle retient un sous-gradient actif.
Aux singularités de représentation, le polissage utilise des différences finies.

Le fichier FIELD accepte le booléen `analytic_gradient`, faux par défaut. Il se transmet à la descente locale,
à la synthèse et au nettoyage après suppression et fusion de couches. Reset le remet à faux.

## Comparaison appariée

La sonde impose une graine NumPy et ajoute une seconde descente avec gradient sur chaque départ du worker.
Le parcours principal garde le résultat en différences finies. Les trois départs de chaque paire sont donc
identiques. Les noyaux sont amorcés avant le chronométrage du gradient.

| Graine | Somme des descentes numériques (s) | Somme avec gradient (s) | Accélération locale |
|---:|---:|---:|---:|
| 42 | 1,894 | 0,322 | ×5,89 |
| 77 | 3,282 | 0,582 | ×5,64 |
| 202 | 1,324 | 0,431 | ×3,07 |

Trois parcours complets vérifient aussi le chargement de l'option depuis la configuration de la fenêtre
et sa transmission aux appels de polissage.

| Graine | Meilleur coût numérique | Meilleur coût avec gradient | Calcul complet avec gradient (s) |
|---:|---:|---:|---:|
| 42 | 0,183493 | 0,197879 | 0,600 |
| 77 | 0,197879 | 0,197879 | 0,854 |
| 202 | 0,197879 | 0,197879 | 0,818 |

Les maxima de champ et le maximum sur les longueurs d'onde rendent l'objectif non lisse. L'accord des
dérivées hors des égalités garantit une direction locale, tandis que les descentes peuvent atteindre des
minima différents. Le coût de la graine 42 augmente de 7,8 % à l'activation. Le gain de temps mesuré accompagne
donc un compromis de convergence. L'option reste un choix de recherche.

## Vérification

Les tests comparent les pics et la réflexion aux différences finies pour S, P et la lumière non polarisée,
à deux angles, deux longueurs d'onde et deux densités d'échantillonnage. Ils couvrent aussi l'objectif complet,
les deux modes de champ, les bornes de réflexion et un nettoyage qui fusionne les couches restantes.
La suite FIELD passe avec 93 tests avant l'ajout du dernier cas de nettoyage. Le fichier de gradient et les
garde-fous d'architecture passent ensuite avec 120 tests. Les 14 épaisseurs du parcours par défaut à graine 42
sont identiques au bit au profil enregistré avant raccordement.
L'oracle passe avec 1 205 tests. Le [corpus C1](c1.json) conserve ses 9 092 tableaux identiques au bit.

[Mesures individuelles](results.json).
