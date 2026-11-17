# Chantier 40 — le TMM oblique de CERTUS contre `tmm` 0.2.0 (S. Byrnes), 2026-11-17

`tmm` installé hors du dépôt (`pip install --no-deps --target %TEMP%\certus_tmm_tiers tmm`) ; sonde
`probe_tmm_tiers.py`, sur `54f8f664`, résultat complet dans `tmm_tiers.json`.

```
CASES=384 MAX_DR=4.330e-15 MAX_DT=1.887e-15 -> tmm_tiers.json
```

384 cas : 3 empilements (sans perte, absorbant k ≤ 0,05, avec une couche métallique 0,2 − 3i) × 4 substrats (verre,
absorbant, semi-conducteur, métal) × 4 angles (0, 30, 60, 85°) × s et p × 4 longueurs d'onde. R va de 0,001 à 0,998 ;
R + T vaut 1 sans perte et descend à 0,93 avec absorption.

**La sonde détecte une erreur** : sans la conjugaison n − ik → n + ik, ou sans inverser l'ordre des couches,
l'écart sur R monte à 0,19 (empilement absorbant, 30°, p).

**Ce que cela ne couvre pas** : seul `calc_spectrum_oblique_vectorized` (face avant, substrat semi-infini) est
recoupé. La face arrière incohérente, la perte de la plaque et les gradients ne le sont pas ; `tmm` a aussi `inc_tmm` (incohérent), non utilisé par cette sonde (correction du 2026-11-17 : la version précédente disait le contraire, voir le [contre-audit](../audit_chantiers_2026-11-17_soir/contre_audit.md)) ;
la sonde n'appelle que `coh_tmm`, et la face arrière reste recoupée par `tests/oracle/tmm_reference.py`.
