# Recommandations techniques d'alignement physique : Simulation STRAT vs Machine Réelle

Document rédigé à l'attention de Claude et de l'équipe scientifique.

---

## 1. Analyse comparative : Machine Réelle vs. Kernel STRAT

La simulation du dépôt dans `certus_strat_growth.py` (`simulate_growth_kernel`) est **extrêmement performante et fidèle dans ses principes fondamentaux** (auto-compensation de Macleod, calcul POEM, bruit photométrique et bruit de volet).

Toutefois, une analyse physique et numérique approfondie révèle **4 écarts précis entre le contrôleur physique en laboratoire et le noyau de simulation** :

---

### Écart 1 — Absence de bruit d'indice de réfringence ($\sigma_n$ / Fluctuations de stœchiométrie)

* **Physique Machine** : Lors du dépôt sous vide réel (évaporation E-beam, pulvérisation IAD), la densité de tassement (*packing density*) et la stœchiométrie des matériaux (ex. $\text{TiO}_x$, $\text{SiO}_x$) varient légèrement d'un run ou d'une couche à l'autre, entraînant une fluctuation de l'indice réel $n(\lambda)$ de $\Delta n / n \approx \pm 1\%\text{ à }\pm 3\%$ ($\Delta n \approx \pm 0,01 - 0,03$).
* **Kernel STRAT** : Dans la version actuelle, les tirages stochastiques Monte-Carlo de Phase B injectent du bruit photométrique ($\sigma_T$) et du bruit de volet ($\sigma_d$), **mais considèrent les indices $n_H(\lambda)$ et $n_L(\lambda)$ comme 100 % déterministes** (issus des courbes de la base de données).
* **Impact physique** :
  - *Sur les points tournants ($\lambda/4$)* : Le suivi par point tournant auto-compense partiellement l'erreur d'indice (si $n$ est plus faible, la couche s'arrête physiquement plus épaisse $d \cdot n = \lambda/4$, préservant l'épaisseur optique).
  - *Sur POEM et hors-$\lambda/4$* : La variation d'indice modifie l'amplitude photométrique du swing, ce qui décale la cible POEM et peut induire une erreur d'arrêt si le bruit d'indice n'est pas modélisé.
* **Solution préconisée pour Claude** :
  Ajouter un paramètre facultatif de bruit d'indice relatif `index_noise_scale` ($\sigma_n \approx 0,01$) dans `_prepare_robustness_inputs` et `simulate_growth_kernel` :
  $$n_{\text{sim}}(\lambda) = n_{\text{nom}}(\lambda) \cdot (1 + \delta n), \quad \delta n \sim \mathcal{N}(0, \sigma_n^2)$$

---

### Écart 2 — Sous-échantillonnage spatial sur les longs blocs monochromatiques

* **Physique Machine** : Le spectrophotomètre échantillonne le signal à temps fixe ($\Delta t = 100\text{ ms}$), soit un pas spatial constant $\Delta d = v \cdot \Delta t \approx 0,1\text{ nm}$ quelle que soit la longueur du bloc ou le nombre de couches.
* **Kernel STRAT** : `simulate_growth_kernel` évalue la grille de recherche d'extrema sur une taille fixe de **64 points répartis sur l'ensemble du bloc monochromatique** (ligne 436).
* **Le problème** :
  $$\Delta d_{\text{grille}} = \frac{\sum_{k \in \text{bloc}} d_k}{64}$$
  - Sur 1 couche de $40\text{ nm}$ : $\Delta d = 0,625\text{ nm}$ (très bon).
  - Sur un bloc de 10 couches ($600\text{ nm}$) : $\Delta d = 9,375\text{ nm}$ !
  Avec un pas de $9,375\text{ nm}$, deux points tournants proches (ex. séparés de $15\text{ nm}$) sont mal résolus. L'ajustement parabolique à 3 points (`fit_parabola_vertex_3points`) subit une distorsion et peut décaler le point tournant détecté de $1\text{ à } 2\text{ nm}$.
* **Solution préconisée pour Claude** :
  Rendre le nombre de points de grille adaptatif au nombre de couches du bloc :
  $$\text{GRID\_SIZE} = \max(64, 32 \times N_{\text{couches\_dans\_bloc}})$$
  Ceci garantit un pas spatial $\Delta d < 1,0\text{ nm}$ en toutes circumstances sans dégradation mesurable des performances.

---

### Écart 3 — Échelle du signal pour les seuils absolus ($T_{\text{front}}$ vs $T_{\text{mesuré}}$)

* **Physique Machine** : Le spectrophotomètre mesure la transmission totale à travers le substrat, incluant la réflexion de la face arrière :
  $$T_{\text{mesuré}} = \frac{T_{\text{front}} \cdot T_{\text{sub}}}{1 - R_{\text{prime}} \cdot R_{\text{back}}} \approx 0,92 \cdot T_{\text{front}}$$
* **Kernel STRAT** : `simulate_growth_kernel` calcule $T_{\text{front}}$ uniquement (sans face arrière) pour des raisons de vitesse heuristique.
* **Le problème** :
  Pour POEM ($p_{\text{poem}}$), l'invariance affine $a T + b$ garantit que $T_{\text{front}}$ donne l'arrêt exact au nanomètre près. En revanche, les **seuils photométriques absolus** comme `SWING_MIN = 0.04` (amplitude minimale de $4\%$) ou `tp_hysteresis` s'appliquent sur un signal $T_{\text{front}}$ surévalué d'environ $+4\%$ par rapport à ce que lit le contrôleur physique.
* **Solution préconisée pour Claude** :
  Appliquer le facteur d'échelle de transmission du substrat nu $T_{\text{sub\_bare}} = \frac{4 n_{\text{sub}}}{(n_{\text{sub}} + 1)^2}$ au signal heuristique avant l'évaluation de `SWING_MIN` et de `tp_hysteresis`.

---

### Écart 4 — Quantification d'échantillonnage temporel ($\pm \Delta d_{\text{sample}} / 2$)

* **Physique Machine** : La décision de fermeture du volet (*shutter*) par le contrôleur physique se fait lors de la réception d'une mesure discrète. Si la condition d'arrêt est franchie entre deux mesures (ex. à $t = 10,04\text{ s}$ alors que les mesures ont lieu à $10,00\text{ s}$ et $10,10\text{ s}$), le volet ne peut être déclenché qu'au point discret suivant, introduisant une incertitude de quantification d'au plus $\pm \frac{\Delta d}{2} \approx \pm 0,05\text{ nm}$.
* **Kernel STRAT** : STRAT calcule la racine continue exacte $d_{\text{stop\_exact}}$ par interpolation quadratique sans discrétisation.
* **Solution préconisée pour Claude** :
  Pour reproduire la quantification d'échantillonnage temporel de la machine réelle, ajouter un bruit uniforme de discrétisation $\delta d \sim U\left(-\frac{\Delta d_{\text{sample}}}{2}, +\frac{\Delta d_{\text{sample}}}{2}\right)$ avec $\Delta d_{\text{sample}} = 0,10\text{ nm}$ lors des tirages stochastiques de Phase B.

---

## Plan d'action synthétique pour la suite

1. **Modélisation du bruit d'indice ($\sigma_n$)** : Injecter la fluctuation d'indice relatives $\Delta n / n \sim \mathcal{N}(0, \sigma_n^2)$ dans les tirages Monte-Carlo (Écart 1).
2. **Ajustement de la grille spatiale** : Rendre `GRID_SIZE` proportionnel à la longueur du bloc dans `simulate_growth_kernel` ($\Delta d < 1,0\text{ nm}$) (Écart 2).
3. **Étalonnage des seuils absolus** : Appliquer le facteur de transmission substrat $T_{\text{sub\_bare}}$ sur les tests d'amplitude `SWING_MIN` et `tp_hysteresis` (Écart 3).
4. **Bruit de discrétisation** : Injecter l'incertitude de quantification temporelle $\pm 0,05\text{ nm}$ dans les tirages Monte-Carlo (Écart 4).
