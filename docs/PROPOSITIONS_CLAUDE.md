# Pistes de réflexion et propositions pour la suite de CERTUS

Document rédigé à l'attention de Claude et de l'équipe scientifique.
Ces propositions sont des **hypothèses de travail soumises à vérification empirique**, ajustées en fonction des règles de pertinence physique et opérationnelle de `AGENTS.md`.

---

## 1. Filtrage en Phase A par la courbure au point tournant ($d^2T/dd^2$) — *Recommandé*

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

## 2. Étude de la stabilité du classement Monte-Carlo vs. Accélération native — *Sous réserve de mesure*

### Constat et hypothèse
La Phase B simule le rendement stochastique $P(\text{conforme})$ sur $N = 200$ tirages Monte-Carlo. Réécrire la boucle interne de croissance en Rust (via PyO3) ou C++ pour exécuter $N = 5\,000$ tirages ne se justifie que si $N=200$ induit de l'instabilité dans le classement.

### Proposition de méthode
Avant d'introduire une dépendance de compilation native (qui complexifie la chaîne de build), mesurer si $N = 200$ pose un réel problème de variabilité.

### Protocole de mesure préalable
1. Lancer la Phase B 10 fois avec $N = 200$ (graines différentes).
2. Lancer la Phase B 10 fois avec $N = 1\,000$.
3. Comparer si le **Top-5 des meilleures stratégies** change entre $N=200$ et $N=1000$.

### Évaluation et nuances
- **Si le Top-5 est strictement stable à $N=200$** : L'échantillonnage actuel suffit amplement et l'accélération native est superflue.
- **Si le Top-5 varie** : L'accélération native de la boucle Monte-Carlo devient justifiée.

---

## 3. Propositions écartées (Non retenues)

* **Rugosité d'interface (Nevot-Croce)** : Écartée. L'évaluation des stratégies STRAT étant relative sur un même empilement nominal, l'introduction de la rugosité n'apporte pas de gain sur le classement et alourdirait inutilement les calculs.
* **Dérive thermique ($\partial n / \partial T$)** : Écartée. En l'absence de télémétrie thermique mesurée en laboratoire pendant le dépôt, ajouter ce paramètre introduirait des variables libres non contraintes et risquerait de créer des artefacts virtuels non représentatifs de la physique réelle.

---

## Synthèse des priorités

1. **Priorité unique d'expérimentation** : Tester le filtre de courbure $d^2T/dd^2$ en Phase A.
2. **Mesure préalable** : Vérifier la stabilité du Top-5 Monte-Carlo à $N=200$ vs $N=1000$.
