# Pistes de réflexion et propositions pour la suite de CERTUS

Document rédigé à l'attention de Claude et de l'équipe scientifique.
Ces propositions sont des **hypothèses de travail soumises à vérification empirique**. Elles n'ont aucune valeur d'autorité et doivent être mesurées avant toute décision d'implémentation, conformément aux principes de méthode de `AGENTS.md`.

---

## 1. Filtrage en Phase A par la courbure au point tournant ($d^2T/dd^2$)

### Constat et hypothèse
Lors de la Phase A de STRAT, une longueur d'onde de contrôle est jugée admissible si le signal présente un extremum (point tournant). Cependant, si la courbure au sommet de l'extremum est très faible ($d^2T/dd^2 \approx 0$), la parabole photométrique locale s'applatit. 

Sous bruit de mesure photométrique $\sigma$, cette faible courbure entraîne une forte incertitude sur la position exacte du sommet $d_{\text{vertex}}$, ce qui déstabilise le calcul des niveaux POEM et augmente le risque de comptage erroné de points tournants (plantage `CRASH_TP_MISCOUNT`).

### Proposition d'action
- Exploiter le formalisme des gradients analytiques (Lot B) pour dériver analytiquement la seconde dérivée $\frac{d^2T}{dd^2}$ aux points tournants.
- Éliminer en Phase A les longueurs d'onde dont la courbure absolue au point tournant est inférieure à un seuil $\epsilon_{\text{courbure}}$.

### Évaluation et nuances
- **Intérêt** : Élevé. Renforce la sélectivité de la Phase A sur des critères de stabilité numérique directe.
- **Risque** : Faible. S'appuie sur le noyau analytique existant.
- **Prudence** : Le seuil $\epsilon_{\text{courbure}}$ doit être calibré empiriquement sur le cas de référence (`JSON-strat-example.json`) pour éviter de rejeter des longueurs d'onde valides.

---

## 2. Étude de la stabilité du classement Monte-Carlo vs. Accélération native (Rust/C++)

### Constat et hypothèse
La Phase B simule le rendement stochastique $P(\text{conforme})$ sur $N = 200$ tirages Monte-Carlo. On pourrait être tenté de réécrire la boucle interne de croissance en Rust (via PyO3) ou C++ pour exécuter $N = 5\,000$ tirages à grande vitesse.

### Proposition de méthode
Avant d'introduire une dépendance de compilation native (qui complexifie la chaîne de build), la démarche scientifique exige d'évaluer si $N = 200$ pose un réel problème de variabilité.

### Protocole de mesure préalable
1. Lancer la Phase B 10 fois avec $N = 200$ (graines différentes).
2. Lancer la Phase B 10 fois avec $N = 1\,000$.
3. Comparer si le **Top-5 des meilleures stratégies** change entre $N=200$ et $N=1000$.

### Évaluation et nuances
- **Si le Top-5 est strictement stable à $N=200$** : Une réécriture native est inutile. Le niveau d'échantillonnage actuel suffit pour classer correctement.
- **Si le Top-5 varie** : Alors et seulement alors, l'accélération native de la boucle Monte-Carlo devient justifiée.

---

## 3. Prise en compte de la rugosité d'interface (Modèle Nevot-Croce / Stearns)

### Constat et hypothèse
Dans les filtres multicouches réels (ex. 48 couches), la rugosité géométrique des interfaces ($\sigma_{\text{rms}} \approx 0,5 - 1,5\text{ nm}$) induit une diffusion qui atténue les franges d'interférence aux courtes longueurs d'onde.

### Analyse comparative (DESIGN vs STRAT)
- **Dans CERTUS DESIGN** : Le facteur de Nevot-Croce $w_j = \exp\left(-2 \left(\frac{2\pi \sigma_j n_j}{\lambda}\right)^2\right)$ peut améliorer la concordance entre le spectre mesuré au spectrophotomètre et le modèle théorique.
- **Dans CERTUS STRAT** : Les stratégies sont comparées **relativement les unes aux autres** sur le même empilement nominal. Si la rugosité décale la réflectance de manière uniforme pour toutes les stratégies, le classement relatif des stratégies reste inchangé.

### Évaluation et nuances
- **Prudence** : Ne pas sur-complexifier le noyau `simulate_growth_kernel` avec un modèle de rugosité tant qu'il n'est pas prouvé qu'il modifie le classement relatif des stratégies de suivi.

---

## 4. Prise en compte de la dérive thermique ($\partial n / \partial T$)

### Constat et hypothèse
La température du substrat peut varier au cours d'un dépôt sous vide de plusieurs heures, modifiant l'indice de réfringence des couches déposées via le coefficient thermo-optique $\frac{\partial n}{\partial T}$.

### Analyse des risques (Règle de méthode n° 1)
Sans mesures expérimentales in-situ de la température en chambre pendant le run :
- Ajouter $\frac{\partial n}{\partial T}$ introduirait des variables libres non contraintes.
- Risque majeur de créer des **artefacts de simulation** qui semblent physiques mais ne correspondent pas à la dynamique réelle de la machine sous vide.

### Évaluation et nuances
- **Recommandation** : **Ne pas implémenter** ce modèle en l'absence de télémétrie thermique réelle mesurée en laboratoire. Se conformer à la règle : *« Si on ne peut pas mesurer le bruit/paramètre réel, ne pas ajouter de complexité spéculative. »*

---

## Synthèse des priorités suggérées

1. **Priorité 1** : Expérimenter le filtre de courbure $d^2T/dd^2$ en Phase A (Hessienne analytique).
2. **Priorité 2** : Mesurer la stabilité du Top-5 Monte-Carlo à $N=200$ vs $N=1000$.
3. **Priorité 3** : Réserver les modèles de rugosité (Nevot-Croce) aux modules de caractérisation d'indice (DESIGN/INDEX).
4. **Priorité 4** : Surseoir à tout modèle thermo-optique en l'absence de données de laboratoire.
