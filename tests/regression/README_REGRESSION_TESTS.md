# CERTUS — tests de convergence (Golden Master)

Ce dossier vérifie que le code **converge toujours aussi bien** sur des exemples réels : la
RMSE obtenue par chaque module ne doit pas dépasser sa référence de plus de **1 %**.

🔑 **Ce n'est pas ce que fait `tests/oracle/`.** L'oracle vérifie que la *physique* est juste,
contre une réimplémentation indépendante. Celui-ci vérifie que l'*optimiseur* arrive toujours
au même endroit. Un refactor peut laisser l'oracle vert et dégrader la convergence.

## Lancer

```bat
python -m pytest tests/regression/ -q --no-cov
```

Les contrôles rapides tournent en moins d'une seconde ; les mesures de convergence portent le
marqueur `slow` et lancent un vrai pipeline par module, en sous-processus.

```bat
python -m pytest tests/regression/ -q --no-cov -m "not slow"    # les contrôles seuls
python tests/regression/test_convergence.py                     # le rapport lisible
```

📏 **Durée mesurée le 2026-09-08** : moins de **8 minutes** pour l'ensemble.

---

## 🔴 État réel, mesuré le 2026-09-08 — lis-le avant de faire confiance à ce dossier

Ce README annonçait *« les 7 modules principaux »* et une **règle absolue** : *« toute
modification de code DOIT être validée par une passe de cette suite »*. Trois faits mesurés
contredisaient cette phrase.

### 1. La suite ne collectait aucun test

`pytest tests/regression/` rendait **`collected 0 items`**. `test_convergence.py` porte un nom
que `pytest` ramasse, mais c'est un **script** : il n'expose que `main()`. La règle « passe
obligatoire » désignait donc une suite qui, dans la suite de tests, **n'existait pas**.

🟢 **Corrigé** : `test_convergence_guard.py` expose de vrais tests. Il n'est pas une copie du
script — il **appelle** ses fonctions, donc il suit ses évolutions. **8 tests collectés.**

### 2. Deux modules sur sept mesuraient un **mock**

`tests/headless/test_design.py` et `test_strat.py` remplacent le calcul par un mock — ce que
`CLAUDE.md` §4 dit depuis longtemps, et que ce harnais ignorait. Le mock de STRAT émet
`{"strategies": []}` : sans stratégie, la RMSE vaut l'infini.

🔴 **Sa référence `0.01706` était donc inatteignable par construction** — un fossile d'avant le
mock, qui produisait un rouge que personne ne pouvait corriger. *Une entrée qui ne peut pas
passer apprend à ignorer la suite.* **Retirée.** DESIGN n'avait déjà pas de référence.

### 3. INDEX était déclaré mesurable et ne rendait jamais rien

Son script cherchait un attribut `rmse_final` que l'objet de résultats **ne porte pas** — il
porte `final_mse`. Il retombait donc silencieusement sur l'infini, et le harnais le sautait
faute de référence.

🟢 **Corrigé**, et la conversion n'est pas une supposition : `spline_workers.py` calcule sa
RMSE finale par `sqrt(max(final_mse, 0))`. **MSE et RMSE sont deux grandeurs**, et les
confondre sur un logiciel de métrologie serait pire que ne rien afficher.
📏 INDEX rend désormais **0,00257**.

---

## La couverture, honnêtement

| module | état | référence |
|---|---|---|
| RE | ✅ mesuré | 0,014588 |
| SPLINE | ✅ mesuré | 0,003393 |
| METAL_SINGLE | ✅ mesuré | 0,008111 |
| METAL_BILAYER | ✅ mesuré | 0,015018 |
| **INDEX** | ✅ **mesuré depuis le 2026-09-08** | **0,00257** |
| DESIGN | 🔴 **non mesurable** | son script mocke le calcul |
| STRAT | 🔴 **non mesurable** | son script mocke le calcul |

⚠️ **La référence d'INDEX a été CAPTURÉE, pas validée.** C'est la valeur du 2026-09-08, posée
comme cliquet de non-régression — elle dit *« pas pire qu'aujourd'hui »*, elle ne dit pas
*« c'est la bonne valeur »*. `scripts/collect_rmse.py` la régénère.

🔵 **Ce qui rendrait DESIGN et STRAT mesurables** est un script headless qui exécute vraiment
le pipeline. C'est un chantier, pas une correction : le mock a probablement été mis là pour
rendre le script rapide, et le retirer change ce que le script coûte.
