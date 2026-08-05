# Reprise — modèle de monitoring de STRAT

Écrit le 2026-08-04 pour la session suivante, **y compris sous un autre compte**.
Autonome : tout ce qui suit est vérifiable dans le dépôt, chaque chiffre a été
mesuré.

> 🔴 **Lance Claude Code depuis `C:\dev\CERTUS\0108`**, pas depuis un autre dossier.
> Sinon chaque commande repart du répertoire de lancement et il faut un `cd`
> systématique.

À lire avec [`REPRISE_SESSION_2026-08-03.md`](REPRISE_SESSION_2026-08-03.md) §0,
qui couvre l'environnement, les pièges de mesure et l'outillage.

---

## 0. L'objectif, en une phrase

Rendre le simulateur d'arrêt de couche **fidèle au réel**, pour que le classement
des stratégies de dépôt produit par STRAT ait un sens. Pas d'optimisation de
performance : une correction de **modèle**.

---

## 1. Ce qui a été fait — cinq mécanismes, chacun mesuré

| # | Mécanisme | Commit | Effet mesuré |
|---|---|---|---|
| 1 | **Cible figée sur le nominal** | `b58e7aa` | la compensation d'erreur existe enfin |
| 2 | **POEM** (Arsac eq. 2.2) | `4b8b3c5` | gain 1,15-2,30 → **0,73-0,78** |
| 3 | **Historique du bloc** | `87bb056` | facteur **3,6** sur couches minces |
| 4 | **Détection de plantage** | `932c744` | 35 % de runs perdus à 600 et 800 nm |
| 5 | **Élimination sur crash ≥ 5 %** | `457be8a` | `rmse_p95` y était aveugle |

### 1.1 La cible était recalculée sur l'empilement réel

`target_T_noisy = T_mono[4] + bruit`, où `T_mono[4]` est calculé sur le
`M_before` **réel**. Or la parabole d'inversion interpole exactement ce même
point : la résolution donnait `Δd = bruit / P′` et **rien d'autre**. À bruit nul,
une couche ressortait nominale quelles que soient les erreurs amont.

**La plomberie séquentielle était correcte** — `certus_strat_batch.py` passe bien
les épaisseurs réellement déposées — **mais son effet était neutralisé au moment
de l'arrêt.** Aucune compensation ne pouvait apparaître ni être mesurée.

En salle, le niveau est **figé avant le dépôt** sur la conception nominale. C'est
le fait de viser une cible périmée sur un empilement erroné qui engendre l'erreur
de signe opposé. Le noyau accumule désormais la matrice nominale en parallèle du
réel et calcule la cible sur elle.

### 1.2 POEM — le point d'arrêt est une fraction, pas une valeur

```
T_POEM = (T_trigger − T_prev_TP) / (T_last_TP − T_prev_TP)
```

Fraction **pré-calculée sur le nominal et figée**, reportée à l'exécution sur les
extrema **réellement observés**. Si le signal réel subit une distorsion affine
`T_réel = a·T_nom + b`, les deux ancrages la subissent identiquement et le niveau
reporté vaut `a·T_trigger_nom + b` : l'arrêt tombe à l'épaisseur voulue.

**La compensation est obtenue par changement de variable, pas par un coefficient.**

Balayage à **64 points** sur 3× l'épaisseur nominale pour disposer des *virtual
next turning points* quand la couche en contient moins de deux, comme le prescrit
Arsac. Repli sur la cible absolue sous 4 % d'amplitude (Zideluns et al.).

### 1.3 L'historique du bloc

À λ **inchangée** le signal est **continu** : les extrema traversés pendant les
couches précédentes restent des mesures valides. Au changement de λ, tout est
perdu. Le balayage porte donc sur **toute la longueur du bloc** — 16 points par
couche d'historique, retour en arrière borné à 4 couches, `block_start_layer`
calculé dans `simulate_stack_robustness_batch`.

**Mesuré, couche de 30 nm à 500 nm** : erreur `−5,4757 → −1,4463` nm pour +2 nm
amont. **Facteur 3,6**, et un cas divergent (gain 3,30) devenu stable (0,92).

Sur une couche **épaisse** l'écart est **nul**, et c'est correct : quand la couche
contient déjà deux extrema, ce sont eux les deux derniers. **La valeur des blocs
monochromatiques est concentrée sur les couches minces.**

### 1.4 Le plantage — mode de défaillance discret

Si l'arrêt tombe **juste avant** un point tournant, une erreur amont peut faire
tourner le signal avant d'atteindre la valeur visée : la machine attend un niveau
qui ne viendra jamais. **Ce n'est pas une perte de précision, c'est un run perdu.**

S'arrêter **après** un point tournant est sûr : l'extremum est compté, le signal
s'en éloigne monotonement. ✅ **C'est la justification de l'asymétrie 3×/1× de
`check_extrema_proximity`**, que j'avais eu tort de croire arbitraire.

Deux détections, pénalité `1e6` :
- le niveau visé n'est pas encadré par le signal réel entre le début de couche et
  le prochain extremum ;
- le **nombre d'extrema comptés diverge** entre nominal et réel — la machine ancre
  alors POEM sur les mauvais points tournants.

⚠️ **Les extrema sont détectés sur le signal RÉEL**, celui que la machine mesure.
La *fraction* POEM vient du nominal. Détecter les ancres sur le nominal doterait le
simulateur d'une connaissance que la machine n'a pas.

### 1.5 Élimination sur risque de plantage

`rmse_p95` est un 95ᵉ percentile : il est **structurellement aveugle** à tout
événement survenant dans moins de 5 % des runs. Un taux de plantage de 2 % passait
inaperçu. D'où `CRASH_RATE_TOLERANCE = 0.05` dans
`certus/core/certus_strat_robustness.py` : au-delà, `robustness_score = inf` et la
stratégie sort du classement. Le taux est exposé sous la clé `crash_rate`.

### 1.6 Deux coefficients supprimés

`non_monotonic_factor` et `wavelength_change_penalty` étaient les formes réduites
de mécanismes que le modèle ne pouvait pas produire. Ils sont neutralisés : le
modèle produit maintenant leurs effets **là où ils existent physiquement**.

---

## 2. 🔴 LE RÉSULTAT LE PLUS IMPORTANT

> 🔴 **LES CHIFFRES DU TABLEAU CI-DESSOUS SONT PÉRIMÉS — mesure à refaire.**
> Ils sont faux **deux fois, et dans le même sens** : ils sous-comptent les plantages.
> 1. Établis **avant** le dégagement de la garde `poem_ok`, qui désactivait la détection
>    précisément quand POEM est mal conditionné. Repli muet sur le sommet de la parabole :
>    6,68 % → 0,04 % ; non-terminabilité signalée : 0,21 % → 7,26 %. **Facteur ~30.**
> 2. Mesurés à `trigger_tolerance = 0.5`, soit σ = 0,5 point de T, alors que le bruit réel
>    de l'OMS 5100 est de l'ordre de **0,05 point** (physicien, 2026-08-05). **Cinq à dix
>    fois trop de bruit.** Voir [`REPRISE_STRAT_BLOCAGE.md`](REPRISE_STRAT_BLOCAGE.md) §2.1.
>
> **L'énoncé qualitatif, lui, reste vrai et c'est ce qu'il faut retenir : les deux critères
> sont orthogonaux et il faut les deux.** Seules les valeurs sont à refaire.

**Deux critères orthogonaux, et il faut les deux.**

| λ | Gain de compensation | Taux de plantage |
|---|---|---|
| 420 nm | **6,56** ⚠️ amplifie | 0 / 17 |
| 500 nm | 0,96 | 0 / 17 |
| **600 nm** | **0,02** ✅ excellent | **6 / 17 — 35 %** ⚠️ |
| 780 nm | **0,00** ✅ | 0 / 17 |
| 800 nm | — | **6 / 17 — 35 %** ⚠️ |

> **600 nm est excellent en précision et catastrophique en opérabilité.**
> Une sélection fondée sur un seul des deux critères se trompe.

Le gain de compensation se mesure **sans Monte-Carlo** :
`scripts/check_compensation_gain.py`.

---

## 3. Ce qui reste à faire, par priorité

1. **Intégrer les deux critères à la Phase A.** Elle ne classe aujourd'hui que sur
   `P95(|Δd|)`, l'erreur **locale**. Le gain de compensation et le taux de plantage
   sont orthogonaux et se calculent presque gratuitement. C'est l'action à plus
   fort effet.
2. **A/B sur STRAT en lecture de CLASSEMENT**, pas de temps :
   ```bash
   bash scripts/ab_compare.sh "certus/physics/certus_strat_growth.py,certus/physics/certus_strat_batch.py,certus/core/certus_strat_robustness.py" "b58e7aa^" strat 4 --auto-yes
   ```
   Attendu : les blocs longs remontent sur les designs à couches minces.
3. **Vérifier le coût.** Le balayage est passé de 8 à ~64-128 évaluations de T par
   couche et par run. **Non mesuré.** STRAT valait 130 s avant.
4. **`probe_offset`** — jamais examiné. Biais systématique ou décalage de sonde ?
5. **Verres témoins multiples** — absents du modèle. Zideluns et al. les utilisent
   pour *réinitialiser* l'accumulation d'erreur et posent explicitement le problème
   ouvert : *« the exact definition of when to change the witness glass remains a
   challenge »*. **La DP sur les blocs est structurellement le bon outil pour ça** —
   décider où couper est exactement ce qu'elle sait faire. Contribution possible.

---

## 4. Sources

- **Arsac**, thèse 2025, `C:\Users\Fabien\Lucas_Arsac_thesis_final.pdf`.
  §2.3.1.2 Level Cut · **§2.3.2.2 POEM et Quasi-Swing, éq. 2.2 à 2.4** · chap. 3 PM
  · chap. 4 P-PM. Encadrée par Julien Lumeau et **Fabien Lemarchand**.
- **Zideluns, Lemarchand, Arhilger, Hagedorn, Lumeau**, *Opt. Express* **29**,
  33398 (2021). Trigger entre **15 et 85 %** de l'amplitude · amplitude de départ
  ≥ 4 % · *« self-compensation operates only at the monitored wavelength »*.
  ⚠️ Son équation 3 (fonction de mérite) a été **écartée** : pas nécessairement
  exacte, ne pas l'implémenter.
- Bruit OMS5100 : **essentiellement additif**, le multiplicatif est 1 à 2 décades
  plus faible, et il **dépend de λ** (fort vers 400 et 1100 nm). Le modèle utilise
  un σ constant — écart connu, non traité.
- Repères expérimentaux pour calibrer : erreurs d'épaisseur moyennes **0,4 nm** en
  PM (51 couches), **0,3 nm** en P-PM (75 couches).

---

## 5. Garde-fous

- 🔴 **Les scores de robustesse ne sont PAS comparables** à ceux d'avant `b58e7aa`.
- Valider par `pytest tests/oracle/ -q --no-cov` (552 tests) **et**
  `tests/unit/test_certus_strat_coherence.py` (53 tests).
- 🔴 Le hook `post-commit` pousse vers le dépôt **public** `nikonvr/CERTUS`.
- Ne jamais mesurer avec autre chose en vol : facteur 6,6 constaté.
- Éditer avec un outil à ancre exacte, **pas** un script de recherche-remplacement :
  deux fichiers ont été corrompus ainsi dans cette session.
