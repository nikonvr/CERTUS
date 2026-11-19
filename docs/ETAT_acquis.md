# CERTUS — acquis et vocabulaire du Rate

> Fait autorité. `§N` = sections de [`ETAT.md`](ETAT.md). Travaux ouverts : [`CHANTIERS_RESTANTS.md`](CHANTIERS_RESTANTS.md).

## Vocabulaire du Rate

*Rate* : couche posée au temps, à la vitesse estimée sur les couches du même matériau contrôlées optiquement (pas un quartz). *Paquet de Rate* : couches consécutives au Rate. *Fenêtre d'optique* : couches contrôlées optiquement entre deux paquets. *Queue* : Rate continu jusqu'à la dernière couche. *Plan mixte* : optique après du Rate. *Plan optique pur* : aucune couche au Rate. *Déposable* : plantage < 5 % au pire des 3 bruits (`0,5×`, `1×`, `2×`). *SEEL* = `2·√score` (nm), rapporté avec graine et mode. Couches indexées dès `0` dans les artefacts, dès `1` dans l'UI et les rapports (« L18-L75 » = indices `17..74`).

## Correctifs d'audit — 2026-11-19

- `abc759f5` (C1) : découpage de `n_back_T` par configuration oblique DESIGN et affichage `_n_back_T_disp`.
- `2edea243` (C3) & `38b7610f` (C2) : profil FIELD Substrat→Superstrat, champ total `|Ex|²+|Ez|²` en `p`-pol oblique, profil non polarisé `0,5·(s+p)` et gradient exact des pics.
- `3fe548de` (C4/M2) : pas de division par `T_sub` sur verre dépoli dans INDEX, rejet `NaN`, dénominateur `w_sum`, `FASTMATH_SAFE`.
- `212dbae5` (C5) : `t_tgt` et `rb_tgt` évalués indépendamment dans `METAL SINGLE` (`_single_RTRback_mse`).
- `698148c8` & `22309e44` (M1/D71, m5, M6b) : limite continue Tauc-Lorentz en `E = Eg`, rejet `NaN`/`Inf` sans course `prange` dans `epsilon_to_nk`, garde pôles Sellmeier, copies isolées Cauchy.
- `bdfdf86b` (M3) : séparation séquentielle avant/arrière dans `sigma_knots_decode`.
- `d067c2a9` & `b3f4dfdb` (M4, m1, m3) : chemin TMM anti-débordement isolé C1 (`0` diff bit), `float64` dépoli, commentaire `compute_complex_phase_components`.
- `6a4ffd8c` & `c2ca68d2` (M5) : dérivées de pénalité alignées dans `gradient_oblique` et `gradient_metal`.
- `30a26eb9` (M6, m6) : `optimize_smart_init_thickness` extrait hors `certus.ui` ; base spline mise en cache et sensibilités vectorisées dans `gradient_function_fixed_eM`.
