# Audit d'expertise — simulation du signal de transmission de l'OMS 5100 dans STRAT (2026-11-15)

Tête `b281ec95`. Audit **par lecture du code et calcul à la main** : aucune mesure n'a été lancée (une mesure longue
occupait la machine). Chaque constat porte son statut : **[lu]** dans le code, **[calcul]** analytique refait ici,
**[rapport]** chiffre d'un rapport existant, **[avis]** jugement d'expert non vérifiable sans la machine. Rien n'est
**mesuré** par cet audit ; les gains de vitesse sont des comptages d'opérations, à confirmer par un profil.

**Révision du même jour** : 👤 n'a pas accès à la salle avant plusieurs mois. Les essais en salle sortent du plan ; ils
sont remplacés par les données publiées du constructeur (§6, **[constructeur]**), par les journaux de dépôts passés
s'il en existe, et par une analyse de sensibilité. Le plan concret est au §8.

Code lu : `certus/physics/certus_strat_growth.py` (`simulate_growth_kernel`, `detect_turning_points`,
`_read_poem_anchors`, `_level_reachability`), `certus/physics/certus_strat_readings.py` (signal, grille machine,
inversion, ancres exactes, armement), `certus/physics/certus_strat_math.py` (`_seeded_noise_sample`),
`certus/core/certus_strat_robustness_task.py` et `certus_strat_robustness_slit.py`, `ETAT.md` section 3 (modèle de
lecture figé), `reports/STRAT_modele_d_arret_D96_D98_2026-10-12.md`.

## 1. Réponse courte

| question | réponse |
|---|---|
| Est-ce bien codé ? | **Oui pour la physique du signal** : la forme fermée `T(d) = 4 n_s / (P + Q cos 2δ + R sin 2δ)` est exacte (redémontrée, §2), le bruit est une fonction pure de (graine, couche, tirage, point), les causes de plantage sont séparées. **Deux faiblesses de structure** : le noyau reconstruit les matrices de l'empilement à chaque couche et à chaque tirage (coût en N²), et il recalcule pour chaque tirage tout ce qui est nominal, donc identique d'un tirage à l'autre (§5). |
| Les extrema sont-ils bien détectés ? | **Le détecteur à hystérésis est correct**, et c'est la même fonction pour le signal réel et le nominal. Cinq réserves (§3), dont deux de fond : le **début de fenêtre compté comme point tournant** sur la grille de production, et le **compte comparé à l'indice de l'arrêt nominal** au lieu de l'arrêt réel. |
| Le raisonnement tient-il ? | **Oui sur le cœur** : niveau figé sur le nominal, fraction POEM reportée sur les ancres lues, invariance affine, nombres aléatoires communs. **Trois points ne tiennent pas ou restent des paris** (§4) : le seuil `SWING_MIN = 0,04` contredit la règle gravée « jamais un couperet » ; l'« attente sans fin » (D98) est l'hypothèse la plus coûteuse du modèle et la moins étayée ; le modèle cumule une approximation optimiste (grille grossière) et une pessimiste (une seule lecture par ancre) dont le solde n'est écrit nulle part. |

## 2. Ce qui est juste

- **Forme fermée** [calcul]. Pour une couche d'indice `n` posée sur la matrice `M`, le dénominateur vaut
  `C cos δ + i S sin δ` avec `X = M00 + n_s M01`, `Y = M10 + n_s M11`, `C = X + Y`, `S = Y/n + nX`, d'où
  `|dén|² = (|C|²+|S|²)/2 + (|C|²−|S|²)/2 · cos 2δ + Im(C·S̄) · sin 2δ`. `layer_scan_coeffs` rend exactement ces trois
  coefficients. La garde `k < 1e-4` est explicite et le chemin matriciel prend le relais, sans repli silencieux [lu].
- **Loi du bruit** [lu]. Somme de 12 uniformes centrée, divisée par 3, bornée à ±1 : gaussienne σ = A/3 tronquée à 3 σ,
  conforme à `ETAT.md` section 3.
- **C2** [lu]. Les tirages sont indexés par la physique (couche, point), jamais par la stratégie ; le facteur de fente
  multiplie l'échantillon, pas la graine.
- **Niveau figé + POEM** [lu]. Le niveau vient du nominal, la fraction est reportée sur les ancres lues ; l'inversion se
  fait en unités mesurées (dérive, courbure, biais de fente appliqués aux deux membres qu'il faut). C'est le mécanisme
  d'auto-compensation, correctement écrit.
- **Biais de fente variable le long de la couche** [lu] : c'est bien la partie que POEM n'absorbe pas.

## 3. Détection des extrema : cinq réserves

1. **Le début de fenêtre est compté comme point tournant en production** [lu]. Sur la grille grossière,
   `direction_at_window_start` est faux, donc `start_dir = 0` hors couche 0 : le détecteur déclare l'indice 0 dès que
   le signal s'en écarte du seuil, et ce niveau devient une ancre POEM sur les deux signaux. Au début d'un **bloc**,
   c'est une vraie lecture (la première après le changement de λ) : ancre défendable, mais ce n'est pas un extremum,
   elle dépend au premier ordre des erreurs d'épaisseur d'amont. Au début de la **fenêtre de 4 couches** d'un bloc plus
   long, c'est un artefact de la troncature (`MAX_LOOKBACK_VAL`) : la machine, elle, garde son vrai dernier extremum.
   Fréquence et effet : non mesurés.
2. **Le compte est arrêté à l'indice de l'arrêt nominal** [lu]. `n_tp_real` et `n_tp_nom` comptent les extrema situés
   avant `idx_nom_stop` sur les deux signaux. Un extremum réel que les erreurs d'amont font passer de l'autre côté de
   cet indice donne `CRASH_TP_MISCOUNT`, alors qu'un contrôleur causal compte ses extrema puis attend son niveau : pour
   lui il n'y a pas d'erreur de compte, seulement un arrêt près d'un extremum. Sur la grille grossière l'indice vaut
   1/21 de couche (≈ 5 nm pour 100 nm). L'artefact recouvre en partie la zone d'armement (§4.2) ; sa part propre n'est
   pas mesurée.
3. **`turning_point_margins` ne suit pas la même règle que le compte** [lu]. Elle reproduit le détecteur sans
   `start_is_tp` ni `start_dir` : sur la couche 0, la marge est calculée par un détecteur qui ne sait pas dans quel sens
   part le signal. Or une marge critique entre dans le classement final (`ETAT.md`, règles gravées) ; je n'ai pas
   vérifié que c'est celle-ci.
4. **`_exact_poem_anchors` retrouve l'échantillon d'une ancre par égalité de valeur** [lu] (`sig[k] == vals[a]`,
   première occurrence). Deux échantillons de même valeur (signal nominal symétrique, cavité) désignent la mauvaise
   couche. `_read_poem_anchors` connaît les indices `tp_a` et `tp_b` : les rendre supprime le risque et une recherche
   linéaire par ancre.
5. **Cosmétique** [lu] : la règle historique (`hysteresis = 0`) garde à 1e-15 dans `detect_turning_points` et à 1e-12
   dans `next_turning_point_after`, alors que la docstring exige « la même règle ». Hors production (plancher 4,15e-4).
   Le commentaire POEM annonce l'usage de « points tournants virtuels » après l'arrêt ; le code ne les utilise jamais
   pour POEM (il faut deux extrema avant l'arrêt nominal, sinon niveau absolu).

Biais de sélection [calcul] : l'ancre exacte (D96) garde le bruit de l'échantillon élu comme maximum ; choisir le plus
grand de deux échantillons presque égaux biaise ce bruit de +0,56 σ au pire, soit ~1e-4 en T : négligeable.

## 4. Le raisonnement

### 4.1 `SWING_MIN = 0,04` est un couperet [lu]

`_read_poem_anchors` coupe POEM et passe au niveau absolu dès que l'écart entre les deux ancres est sous 4 % de T, soit
**80 fois** l'amplitude du bruit. `ETAT.md` (règles gravées) dit que les heuristiques de la littérature sont « des
colonnes explicatives, jamais des couperets », et la docstring de `detect_turning_points` refuse d'emprunter ce même
4 % pour le seuil de détection. À 3,9 % de swing, POEM est parfaitement conditionné (ancres à ±1 A sur 78 A) et le
noyau l'abandonne pour un arrêt absolu, sensible à la courbure photométrique et au biais de fente. La loi d'arrêt
change donc de nature à 4 %, ce qui crée une marche dans le score en fonction de λ. Un seuil dérivé du bruit
(k × A, à balayer) serait cohérent avec le reste du modèle. Effet non mesuré.

### 4.2 L'attente sans fin (D98) : l'hypothèse la plus chère, la moins étayée

- [calcul] Le niveau est « franchi avant l'armement » s'il est à moins de `h` du dernier extremum. Près d'un extremum
  `T'' = (ΔT/2)(4πn/λ)²`, donc la zone interdite après l'extremum vaut `d_h = √(2h/T'')` : **3,4 nm** pour un swing de
  10 %, n = 2,35, λ = 550 nm, h = 1,66 A = 8,3e-4. En fraction de la demi-période : `(2/π)√(h/ΔT)` = **5,8 %**,
  indépendante de l'indice ; 9,2 % à 4 % de swing, 3,3 % à 30 %.
- [calcul + rapport] Sur 48 couches aux phases quelconques, la probabilité de n'en avoir aucune dans la zone est
  0,942⁴⁸ ≈ **6 %**. Le rapport du 12 octobre mesure 6 plans déposables sur 120, soit 5 %. L'hécatombe est donc une
  conséquence géométrique directe de `h`, pas une subtilité du composant.
- [calcul] Changer de détecteur ne réduit pas `d_h` : pour *savoir* qu'un extremum est passé il faut un bras de levier.
  Un ajustement parabolique glissant sur 64 lectures ne le déclare que ~4 nm après. La zone est physique.
- [avis] En revanche **« attendre sans fin » suppose un déclenchement sur l'événement de franchissement**. Sur un signal
  échantillonné (une lecture tous les 0,125 nm), un contrôleur ne peut pas attendre l'égalité : il teste « le signal
  est-il passé de l'autre côté du niveau ? ». À l'instant où il s'arme, ce test est déjà vrai et il coupe : c'est
  l'**arrêt tardif** (`oms_arming = 1`), en retard de `d_h` au plus. Par ailleurs un automate industriel a un critère
  de secours (quartz, épaisseur maximale) : une couche ne dure jamais indéfiniment, elle finit fausse. L'attente sans
  fin est donc la **borne pessimiste**, l'arrêt tardif le comportement le plus plausible. Le rapport chiffre l'enjeu :
  0 plan optique pur déposable contre 101, et le Rate devient une nécessité.
- [constructeur] Bühler présente le choix d'une stratégie avec des critères paramétrables de *swing-in* et de
  *swing-out* (distance de l'arrêt aux points tournants). Un arrêt collé à un extremum s'évite donc **à la conception**,
  ce que fait déjà la porte de plantage de STRAT. Sans salle, la question « tardif ou sans fin » ne se tranche pas :
  elle se **borne**. Noter chaque plan sous les deux comportements (§8, étape 3) dit si le classement en dépend.

### 4.3 Deux approximations de sens opposé, sans solde

`ETAT.md` l'écrit : la grille de production (≈ 21 points par couche) est **optimiste** sur les faux points tournants,
la machine lisant ~800 fois une couche de 100 nm. À l'inverse, chaque ancre et la lecture d'arrêt portent le bruit
d'**une** lecture, alors qu'à 4 Hz une cinquantaine de lectures entourent un extremum : un contrôleur qui lisse ou
ajuste connaît ses ancres 3 à 5 fois mieux [calcul : σ/√N sur la zone plate] ; le constructeur parle d'un « traitement
du signal par algorithme étendu ». Le modèle est donc **pessimiste** sur le bruit des ancres. Le modèle figé (grille
machine, lissage 8) s'accorde avec la machine séquentielle d'après la docstring de `scripts/probe_modele_lecture.py` ;
je n'ai pas trouvé de bilan qui chiffre l'écart de **classement** entre ce modèle et celui de production.

### 4.4 L'étalonnage du bruit : cohérent avec le constructeur, reste sa dépendance en T et en λ

Correction de la première version de cet audit, qui soupçonnait un bruit 1,7 fois trop fort. Le constructeur annonce
un rapport bruit sur signal **inférieur à 0,02 % efficace** sur le signal brut. Le modèle tire σ = A/3 = 0,0167 point
de transmission : à haute transmission c'est exactement cet ordre. L'étalonnage de A tient.

Ce que la phrase du constructeur laisse ouvert : un rapport bruit **sur signal** constant donne un bruit absolu
proportionnel à T (quatre fois plus faible à T = 20 % qu'à 80 %), alors que le modèle le garde constant. Le modèle est
alors pessimiste dans les bandes de réjection et juste en bande passante. Le constructeur ajoute « dépend du montage
et du détecteur » : la dépendance en λ (R1) est réelle, sa forme n'est pas publiée.

## 5. Levier 1 — aussi bien, plus vite

Comptage d'opérations sur le chemin de production (grille grossière, POEM, ancres et inversion exactes), couche `i` :

| poste | opérations par appel | remarque |
|---|---|---|
| matrices d'empilement | `_stack_matrix` réel (i couches) + nominal (i) + `_stack_matrix_pair` (≈ 2(i−4)) + `_exact_poem_anchors` (4 ancres × jusqu'à i) ≈ **8 i produits** à cos/sin complexes | croît avec la profondeur : ~190 produits à la couche 24, ~380 à la 48, ~790 sur un 99 couches |
| balayage du signal | (64 + 4×16) points × 2 signaux × 2 fonctions trigonométriques ≈ **512** | constant |
| bruit | 128 échantillons × 12 hachages ≈ **1 536** tours de hachage | le commentaire D94 note que le tirage coûte plus que les deux appels trigonométriques d'une lecture |
| inversion exacte | pas de recherche + **60** bissections × 2 fonctions trigonométriques | la bissection est stationnaire après ~46 pas |
| détection | 3 passes sur 128 points + la recherche linéaire des ancres | faible |

Leviers, du plus rentable au moins rentable (gains **non mesurés**) :

| | levier | bits | attendu |
|---|---|---|---|
| V1 | **Ne plus reconstruire les matrices** : table nominale par (λ, couche), calculée une fois par stratégie ; matrice réelle portée par tirage et mise à jour d'une couche à la suivante dans un bloc | mêmes produits dans le même ordre ; `c1_diff` dira si `fastmath` bouge les derniers bits | le poste dominant dès ~20 couches ; passe de N² à N |
| V2 | **Sortir le nominal de la boucle Monte-Carlo** : `Ts_n`, son compte d'extrema, ses ancres, `p_poem`, `target_nominal`, `start_dir` ne dépendent ni du tirage ni du bruit (le seuil ne dépend que du niveau de bruit : trois jeux) | identiques par construction | la moitié du balayage et une passe de détection sur trois |
| V3 | Rendre `tp_a`, `tp_b` au lieu de rechercher les ancres par valeur ; fusionner `turning_point_margins` dans la passe de détection | identiques | petit, et corrige les réserves 3 et 4 du §3 |
| V4 | Sortie anticipée de la bissection quand `mid` égale une borne | identiques (la suite est stationnaire) | ~25 % de l'inversion |
| V5 | Bruit en 1 hachage au lieu de 12 (somme de 4 uniformes de 16 bits, support ±3,46 σ, à peine plus large que la troncature à 3 σ) | **réalisations différentes** : inactif par défaut, validation statistique et non au bit | jusqu'au tiers du noyau si le commentaire D94 dit vrai |
| V6 | Récurrence d'angle pour cos/sin sur grille uniforme | derniers bits différents | utile seulement sur la grille machine (800 lectures) |

V1 à V4 ne changent pas le modèle : ce sont les candidats au « aussi bien, plus vite ». Protocole : un profil par poste
sur le juge de paix (sonde à écrire : aucune ne chronomètre le noyau STRAT par poste), puis V2 et V1 un commit chacun,
`python scripts/c1_diff.py HEAD --corpus strat` froid contre froid à chaque fois.

Levier de structure [avis] : sur la grille grossière, le bruit n'agit qu'en trois endroits (deux ancres, une lecture
d'arrêt) et dans deux tests (compte, atteignabilité). Les extrema d'une couche sont connus en forme fermée
(`tan 2δ = R/Q`) : un noyau **événementiel**, qui calcule les extrema au lieu de balayer 128 points, coûterait
O(nombre d'extrema), n'aurait plus d'artefact d'indice (réserve 2) et rendrait les ancres exactes sans D96. C'est un
autre modèle : à comparer à la référence séquentielle, pas à l'actuel au bit.

## 6. Levier 2 — coller à un OMS 5100 réel, sans la salle

### 6.1 Ce que le constructeur a publié

| donnée | valeur publiée | source | ce qu'elle dit du modèle |
|---|---|---|---|
| bruit sur signal du signal brut | < 0,02 % efficace, « dépend du montage et du détecteur » | JCMO 2016, « Typical performance data OMS 5000/5100 » ; SVC 2006 | σ = A/3 = 0,0167 point : cohérent (§4.4) |
| justesse en longueur d'onde | < 0,5 nm, « dépend de l'étalonnage du monochromateur » | JCMO 2016 | aucune erreur de λ dans le modèle (R8) |
| bande passante | 0,5 à 15 nm selon la fente ; 0,5 à 8,8 nm **à mi-hauteur** pour l'OMS 5100 | JCMO 2016 ; brochure Bühler | la résolution est une largeur à mi-hauteur ; le modèle intègre un créneau (R3). STRAT garde ses quatre valeurs, 5, 2, 1 et 0,5 nm (👤, 2026-11-15) |
| cadence | une lecture par tour, 15 à 250 tr/min | JCMO 2016 | la machine est un HELIOS 800 à 240 tr/min (👤, 2026-11-15) : les 4 Hz du modèle sont exacts |
| dérive du signal | « négligeable par auto-compensation » | JCMO 2016 | rien à modéliser |
| erreur d'étalonnage photométrique | < 1 %, « importance selon l'algorithme d'arrêt » | JCMO 2016 | `affine_scale_amp` vaut 0 en production : l'arrêt absolu y est jugé insensible à une erreur que le constructeur chiffre (R10) |
| algorithmes d'arrêt | point tournant ; point de déclenchement absolu ou relatif ; « correction en ligne des points de déclenchement » | JCMO 2016 ; SVC 2006 | POEM est bien la famille « relative » |
| retard de coupure | 0,5 s en moyenne, écart-type 0,1 (unité à lire dans le texte intégral), entre le signal d'arrêt et l'arrêt réel du dépôt | SPIE 2008 (résumé) | le modèle n'a aucun retard (R6) |
| vitesses de dépôt | 0,5 nm/s (TiO2) et 0,8 nm/s (SiO2) dans les essais publiés | SVC 2006 | une seule vitesse dans le modèle (R7) |
| optique | lampe quartz-halogène, monochromateur à réseau à fentes d'entrée et de sortie, détecteur Si ou InGaAs (400 à 1 700 nm), incidence normale | SVC 2006 | fonde R1 et R3 |

Sources : Zöller, « Direct optical monitoring in intermittent mode »,
[JCMO 2016](http://www.sfoptique.org/medias/files/jcmo2016-alfons-zoeller.pdf) ; Zöller et al.,
[SVC 2006](https://www.svc.org/clientuploads/directory/resource_library/06_229.pdf) ;
[brochure Bühler « Precision optics »](https://dam.buhlergroup.com/asset/5a2a255493ef47d49158daae54c1f037/Brochure_LO_Optics_Precision%20Optics.pdf) ;
Zöller, Boos, Hagedorn, Romanov,
[SPIE 2008](https://www.researchgate.net/publication/253589981_Computer_simulation_of_coating_processes_with_monochromatic_monitoring)
(résumé seulement : je n'ai pu lire ni le texte intégral ni son tableau de paramètres).

### 6.2 Les écarts, reclassés

Classé par effet attendu sur **ce que STRAT décide**. Tous inactifs par défaut (C1).

| | écart au réel | ordre de grandeur | fondé sur | réglable sans salle ? |
|---|---|---|---|---|
| R6 | **Aucun retard de coupure** | [calcul] si l'automate compense la moyenne, il reste la gigue : 0,1 s × 0,5 nm/s = **0,05 nm efficace par couche**, du même ordre que tout le bruit d'arrêt modélisé (σ / pente ≈ 1,7e-4 / 4e-3 par nm = 0,04 nm). S'il ne compense pas : +0,25 nm systématique | constructeur (résumé) | oui : un tirage par couche, borné |
| R10 | **Étalonnage photométrique supposé parfait** (`affine_scale_amp = 0`) | 1 % d'échelle ; POEM l'absorbe, l'arrêt absolu (sous `SWING_MIN`, ou sans deux ancres) non | constructeur | oui : le paramètre existe déjà |
| R4 | **Face arrière du témoin absente** | swing mesuré × 0,92 sur verre, × **0,85 sur saphir** à haute transmission ; modèle optimiste de 9 à 17 % sur le rapport signal sur bruit [calcul, couches sans pertes] | physique | oui : une division par point |
| R3 | **Fente en créneau** de largeur B | une fonction triangulaire de largeur à mi-hauteur B a une variance double : biais de fente × 2 au premier ordre [calcul] | constructeur (résolution à mi-hauteur) ; forme réelle inconnue | à borner : créneau et triangle |
| R8 | **Aucune erreur de calage de λ** | ±0,5 nm par changement de λ = 0,1 % d'échelle sur tout le bloc à 500 nm | constructeur | oui : un tirage par bloc |
| R1 | **Bruit indépendant de λ et de T** (figé) | forme inconnue ; pèse sur le choix des λ courtes (halogène faible, silicium moins sensible) | constructeur (« dépend du détecteur ») | à borner : modèle lampe × détecteur, déclaré comme hypothèse |
| R2 | **D98** : attente sans fin ou arrêt tardif | 0 ou 101 plans optiques purs déposables [rapport] | inconnu | à borner : noter sous les deux |
| R7 | **Vitesse unique** pour H et L | lectures deux fois moins denses sur la couche rapide | constructeur | oui |
| R9 | **Même lecture, deux bruits** (courante puis historique) | second ordre | code | oui, coût moyen |

Hors modèle, et à y laisser : la dérive lente, que le constructeur dit négligeable ; la grenaille, tant que rien ne la
chiffre.

## 7. Trois façons de remplacer la salle

1. **Les journaux de dépôts passés**, s'ils existent sur un disque : un export de l'OMS (signal en fonction du temps,
   instants de coupure, λ, fente) donne σ, sa dépendance en T et en λ, le retard de coupure et, avec de la chance, un
   arrêt proche d'un extremum. C'est la seule source de **mesures** accessible ; aucun journal n'est suivi dans le dépôt.
2. **Les documents** : le manuel de l'OMS (définition de la résolution, algorithmes de déclenchement, *swing-in* et
   *swing-out*) et le texte intégral de SPIE 2008 (les paramètres de simulation du constructeur lui-même).
3. **La sensibilité** : pour chaque écart non mesurable, noter la même population de plans sous les deux hypothèses
   extrêmes. Si le gagnant et le SEEL ne bougent pas plus que la dispersion Monte-Carlo, l'inconnue ne compte pas et se
   ferme avec un chiffre ; sinon elle devient une contrainte de robustesse, comme le sont déjà les trois niveaux de bruit.

## 8. Plan concret

Une étape, un commit (C3). « Fin » est le critère vérifiable.

| n° | étape | fichiers | fin | bits |
|---|---|---|---|---|
| 0 | 👤 cherche journaux OMS et manuel ; à défaut, on continue sans | hors dépôt | réponse oui ou non | — |
| 1 | **Sonde de profil du noyau STRAT par poste** (matrices, balayage, bruit, inversion, détection) sur le juge de paix | `scripts/probe_strat_kernel_profile.py`, sortie dans ce dossier | un tableau en µs par appel selon la profondeur de couche, qui confirme ou infirme le §5 | aucun code de calcul touché |
| 2a | **V2** : le nominal sort de la boucle Monte-Carlo | `certus_strat_growth.py`, `certus_strat_readings.py`, appelants | `c1_diff --corpus strat` identique au bit, oracle vert, gain mesuré par la sonde 1 | identiques |
| 2b | **V1** : matrices portées d'une couche à la suivante, table nominale | idem | idem ; si `fastmath` bouge des bits, arrêt et rapport de l'écart en ulp | identiques ou signalés |
| 2c | **V3 + V4** : indices d'ancres rendus, marges dans la passe de détection, bissection à sortie anticipée | idem | idem | identiques |
| 3 | **Sonde de sensibilité** : `probe_modele_lecture.py` reçoit les variantes R2 (tardif ou sans fin), R10 (échelle 1 %), `SWING_MIN` en multiples de A, bruit proportionnel à T | `scripts/probe_modele_lecture.py` | pour les 120 premiers plans du juge de paix : SEEL, plans déposables et corrélation de rang par variante, dans un bilan | noyau intact (paramètres existants) |
| 4a | **R6** retard de coupure : tirage par couche (moyenne, écart-type, vitesse), inactif par défaut | noyau, tâche de robustesse | test rouge d'abord ; inactif = mêmes bits ; effet mesuré par la sonde 3 | C1 |
| 4b | **R4** face arrière du témoin, inactif par défaut | noyau | recoupé contre `tests/oracle/tmm_reference.py` ; idem | C1 |
| 4c | **R3** fente triangulaire en option | `certus_strat_robustness_slit.py` | intégrale recoupée contre une quadrature fine ; idem | C1 |
| 4d | **R8** erreur de λ par bloc, **R7** vitesse par matériau | noyau, tâche | idem | C1 |
| 5 | **§4.1** : `SWING_MIN` remplacé par k × A, k balayé par la sonde 3 | noyau | la marche à 4 % disparaît du score en fonction de λ ; choix de k consigné | C1 (k par défaut = seuil actuel) |
| 6 | **§3, réserves 1 et 2** : fréquence mesurée contre `probe_oms_sequentiel.py`, puis correction si elle compte | sonde, puis noyau | un chiffre par réserve dans un bilan | C1 |
| 7 | **Décision de 👤** sur chiffres : quels leviers de l'étape 4 s'activent, et si le classement final prend le pire des hypothèses bornées (R2, R3, R1) | `ETAT.md` section 3 | modèle de lecture révisé, daté | changement voulu |
| 8 | **Fiche d'essais** prête pour le retour en salle : D98, σ selon λ et T, retard de coupure, profil de fente | ce dossier | une page, une heure de machine | — |

Ordre et dépendances : 1 avant 2 (il faut la mesure de départ) ; 3 avant 4 à 6 (elle dit quels leviers méritent le
code) ; 2 et 3 sont indépendants. Les étapes 1 à 3 ne changent aucun résultat de STRAT : elles peuvent partir tout de
suite. Rien ne s'active par défaut avant l'étape 7.

Ce que le plan ne fera pas : inventer une courbe de bruit en λ et l'activer. Sans mesure, R1 reste une hypothèse
bornée par la sonde 3, jamais un réglage de production.

## 9. Ce que cet audit ne dit pas

- Aucun chiffre de gain n'est mesuré ; le poste « matrices » domine d'après un comptage, pas d'après un profil.
- Je ne connais pas l'algorithme d'arrêt de l'OMS 5100 : §4.2 est un raisonnement d'automaticien.
- Les données du constructeur sont des plafonds de fiche technique (« < 0,02 % », « < 0,5 nm », « < 1 % »), pas des
  mesures de la machine de 👤. Le retard de 0,5 s vient d'un résumé de 2008 sur l'OMS 5000 ; je n'ai pas lu l'unité de
  son écart-type ni vérifié que l'automate le compense.
- R3 suppose des fentes d'entrée et de sortie égales ; R4 suppose des couches sans pertes (`R' = 1 − T`).
- La grille machine (`machine_sampling_dd`, lissage) n'est pas en production : je l'ai lue, pas auditée en détail.
