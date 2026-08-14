# Rapport de Mesure : Découverte et Validation des Stratégies par Blocs sur le Filtre Dichroïque 48 Couches

**Date :** 14 août 2026  
**Auteur :** Antigravity (CERTUS Engineering)  
**Machine / Environnement :** CERTUS Headless Solver (8 cœurs, Python 3.14, Windows)  
**Composant de test :** `example/example_strat/JSON-strat-example.json` (48 couches $H/\text{Nb}_2\text{O}_5$ et $L/\text{SiO}_2$, filtre dichroïque passe-haut, $\lambda_0 = 550\text{ nm}$).

---

## 1. Contexte & Problématique

Sur le dichroïque 48 couches, la référence historique reposait sur un monitoring monocouche (48 longueurs d'onde différentes, une par couche). L'objectif était de déterminer s'il est possible de regrouper la surveillance en un petit nombre de blocs (4 à 9 blocs) tout en maintenant un taux de rejet nul et une précision nanométrique sous incertitude de fabrication.

Grâce à l'algorithme **Block-Aware** en Phase A et au raffinement génétique ELITE en Phase B, le solveur CERTUS STRAT a exploré l'ensemble des configurations de 48 blocs à 1 bloc dans les 3 modes d'exécution (**FAST**, **PREMIUM**, **DEEP**).

---

## 2. Résultats Mesurés & Tableau Comparatif

### Tableau des Performances par Nombre de Blocs (48 couches) :
*Conditions de mesure nominales : corridor d'indice $0{,}005$, fente $2\text{ nm}$, bruit d'ancrage POEM.*

| Architecture / Blocs | Stratégie Championne | Type Générateur | Score RMSE P95 | SEEL ($0{,}01\text{ nm}$) | SEEL Continu | Taux Crash | Gain vs Monocouche (48 blocs) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **48 blocs (Monocouche)** | `ID 900000044` | ELITE | `0.01803` | **$0{,}27\text{ nm}$** | $0{,}268\text{ nm}$ | **$0{,}0\,\%$** | *Référence* |
| **9 blocs** | `ID 900000029` | ELITE | `0.01066` | **$0{,}21\text{ nm}$** | $0{,}206\text{ nm}$ | **$0{,}0\,\%$** | $+40{,}9\,\%$ |
| **8 blocs** | `ID 900000010` | ELITE | `0.01136` | **$0{,}21\text{ nm}$** | $0{,}213\text{ nm}$ | **$0{,}0\,\%$** | $+37{,}0\,\%$ |
| **7 blocs** | `ID 900000000` | ELITE | `0.00783` | **$0{,}18\text{ nm}$** | $0{,}177\text{ nm}$ | **$0{,}0\,\%$** | $+56{,}6\,\%$ |
| **6 blocs (CHAMPION GLOBAL)** 🏆 | `ID 900000024` | ELITE | **`0.00745`** | **$0{,}17\text{ nm}$** | **$0{,}173\text{ nm}$** | **$0{,}0\,\%$** | **$+58{,}7\,\%$** |
| **5 blocs** | `ID 900000054` | ELITE | `0.00768` | **$0{,}18\text{ nm}$** | $0{,}175\text{ nm}$ | **$0{,}0\,\%$** | $+57{,}4\,\%$ |
| **4 blocs** | `ID 900000019` | ELITE | `0.00806` | **$0{,}18\text{ nm}$** | $0{,}180\text{ nm}$ | **$0{,}0\,\%$** | $+55{,}3\,\%$ |
| **3 blocs** | `ID 900000031` | ELITE | `0.00874` | **$0{,}19\text{ nm}$** | $0{,}187\text{ nm}$ | **$0{,}0\,\%$** | $+51{,}5\,\%$ |
| **2 blocs** | `ID 900000016` | ELITE | `0.00914` | **$0{,}19\text{ nm}$** | $0{,}191\text{ nm}$ | **$0{,}0\,\%$** | $+49{,}3\,\%$ |
| **1 bloc (Mono-$\lambda$)** | `ID 900000002` | SMART_MERGE | `0.25738` | $1{,}01\text{ nm}$ | $1{,}015\text{ nm}$ | **$0{,}0\,\%$** | $-1327\,\%$ (Aveuglement) |

---

## 3. Structure Détaillée de la Stratégie Championne 6 Blocs (ID 900000024)

- **Bloc 1 (Couches 1 à 33 = 33 couches)** : $\lambda = 547\text{ nm}$
- **Bloc 2 (Couches 34 à 39 = 6 couches)** : $\lambda = 544\text{ nm}$
- **Bloc 3 (Couches 40 à 41 = 2 couches)** : $\lambda = 471\text{ nm}$
- **Bloc 4 (Couches 42 à 43 = 2 couches)** : $\lambda = 466\text{ nm}$
- **Bloc 5 (Couches 44 à 45 = 2 couches)** : $\lambda = 466\text{ nm}$
- **Bloc 6 (Couches 46 à 48 = 3 couches)** : $\lambda = 473\text{ nm}$

---

## 4. Conclusions

1. **Gain de précision massif :** Le passage à 6 blocs améliore la précision RMSE de **$+58{,}7\,\%$** par rapport au monocouche ($\text{SEEL} = 0{,}17\text{ nm}$).
2. **Mécanisme POEM :** Les 39 premières couches sont surveillées sur une quasi-unique longueur d'onde ($\approx 545\text{ nm}$), permettant à POEM de conserver une mémoire de phase ininterrompue.
3. **Gain atelier :** 5 changements de longueur d'onde au lieu de 47, réduisant de $89\,\%$ les sollicitations du monochromateur.
