# Rapport de Mesure : Découverte et Validation des Stratégies par Blocs sur le Filtre Passe-Bande 35 Couches (3 Cavités)

**Date :** 14 août 2026  
**Auteur :** Antigravity (CERTUS Engineering)  
**Machine / Environnement :** CERTUS Headless Solver (8 cœurs, Python 3.14, Windows)  
**Composant de test :** `example/example_strat/JSON-strat-bandpass-3cav.json` (35 couches $H/\text{SiO}_2$ et $L/\text{Ta}_2\text{O}_5$, 3 cavités Fabry-Pérot à 633 nm).

---

## 1. Contexte & Problématique

Jusqu'alors, sur le composant passe-bande résonant 35 couches, le solveur nominal CERTUS STRAT produisait une stratégie de surveillance optique nécessitant **35 longueurs d'onde différentes** (une longueur d'onde par couche, soit 35 blocs de 1 couche). 

L'intuition de la recherche était qu'il devait être physiquement possible de regrouper la surveillance en **blocs de plusieurs couches sur une même longueur d'onde**, réduisant drastiquement les mouvements mécaniques du monochromateur en atelier tout en conservant une précision sub-nanométrique.

Grâce au bonus **Block-Aware** intégré en Phase A ($C = C_{\text{local}}/\sqrt{\text{streak}}$), le solveur a pu explorer l'intégralité du spectre des blocs de 35 à 1 à travers les 3 modes (**FAST**, **PREMIUM**, **DEEP**).

---

## 2. Résultats Mesurés & Tableau Comparatif

### Tableau des Performances par Nombre de Blocs (35 couches) :
*Conditions de mesure nominales : bande $600-660\text{ nm}$ (61 points), corridor d'indice $0{,}005$, fente $2\text{ nm}$, bruit d'ancrage POEM.*

| Architecture / Blocs | Stratégie Championne | Type Générateur | Score RMSE P95 | SEEL ($0{,}01\text{ nm}$) | SEEL Continu | Taux Crash | Gain vs Monocouche (35 blocs) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **35 blocs (Monocouche)** | `ID 35961` | ELITE | `0.08496` | **$0{,}58\text{ nm}$** | $0{,}583\text{ nm}$ | **$0{,}0\,\%$** | *Référence* |
| **7 blocs** | `ID 900000023` | ELITE | `0.06005` | **$0{,}49\text{ nm}$** | $0{,}490\text{ nm}$ | **$0{,}0\,\%$** | $+29{,}3\,\%$ |
| **6 blocs (CHAMPION GLOBAL - DEEP)** 🏆 | `ID 900000040` | ELITE | **`0.05819`** | **$0{,}48\text{ nm}$** | **$0{,}482\text{ nm}$** | **$0{,}0\,\%$** | **$+31{,}5\,\%$** |
| **5 blocs (PREMIUM)** | `ID 900000000` | ELITE | `0.06201` | **$0{,}50\text{ nm}$** | $0{,}498\text{ nm}$ | **$0{,}0\,\%$** | $+27{,}0\,\%$ |
| **4 blocs** | `ID 900000013` | RATE_L11 | `0.06431` | **$0{,}51\text{ nm}$** | $0{,}507\text{ nm}$ | **$0{,}0\,\%$** | $+24{,}3\,\%$ |
| **3 blocs** | `ID 900000039` | ELITE | `0.07087` | **$0{,}53\text{ nm}$** | $0{,}532\text{ nm}$ | **$0{,}0\,\%$** | $+16{,}6\,\%$ |
| **2 blocs** | `ID 990000002` | ELITE | `0.08026` | **$0{,}57\text{ nm}$** | $0{,}567\text{ nm}$ | **$0{,}0\,\%$** | $+5{,}5\,\%$ |
| **1 bloc (Mono-$\lambda$)** | `ID 900000002` | SMART_MERGE | `0.37429` | $1{,}22\text{ nm}$ | $1{,}224\text{ nm}$ | **$0{,}0\,\%$** | $-340\,\%$ (Aveuglement) |

---

## 3. Structure Détaillée de la Stratégie Championne 6 Blocs (ID 900000040)

- **Bloc 1 (Couches 1 à 10 = 10 couches)** : $\lambda = 521\text{ nm}$ (Miroir d'entrée et 1ère cavité)
- **Bloc 2 (Couches 11 à 12 = 2 couches)** : $\lambda = 450\text{ nm}$ (Couplage inter-cavité 1-2)
- **Bloc 3 (Couches 13 à 17 = 5 couches)** : $\lambda = 484\text{ nm}$ (2ème cavité centrale)
- **Bloc 4 (Couches 18 à 22 = 5 couches)** : $\lambda = 462\text{ nm}$ (Couplage inter-cavité 2-3)
- **Bloc 5 (Couches 23 à 29 = 7 couches)** : $\lambda = 454\text{ nm}$ (3ème cavité)
- **Bloc 6 (Couches 30 à 35 = 6 couches)** : $\lambda = 461\text{ nm}$ (Miroir de sortie)

---

## 4. Conclusions

1. **Preuve physique :** La surveillance par blocs multi-couches fonctionne avec un taux de plantage nul ($0{,}0\,\%$) et surpasse le monocouche de **$+31{,}5\,\%$** en précision RMSE ($\text{SEEL} = 0{,}48\text{ nm}$).
2. **Adéquation structurelle :** Les blocs épousent naturellement la structure des 3 cavités Fabry-Pérot.
3. **Gain atelier :** 5 changements de longueur d'onde au lieu de 34, divisant par 7 les mouvements mécaniques du monochromateur.
