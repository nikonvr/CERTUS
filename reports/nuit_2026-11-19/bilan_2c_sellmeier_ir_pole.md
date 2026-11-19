# Lot 2c — `sellmeier_ir_pole` sur des indices de substrat mesurés (2026-11-19)

Suite du [chantier 05](../chantier05_2026-11-18/bilan.md), qui n'avait mesuré que des courbes de catalogue synthétiques.
Option allumée par défaut depuis le 2026-11-19 (exception C1, `docs/ETAT.md` §3). Code : `4fd783cb`.

## Mesure

[`p2c_ir_pole_measured.py`](p2c_ir_pole_measured.py) ([sortie](p2c_ir_pole_measured.txt)) : `IndexCore.fit_sellmeier`
(`sellmeier3poles`, réglages par défaut), option éteinte puis allumée, à chaud ; écart rms aux **données** (pas de courbe
vraie : le bruit de mesure y est compris).

| données | plage (nm) | ancien défaut : rms, source | option : rms, source | max \|on − off\| plage / tout |
|---|---|---|---|---|
| n de T, Al2O3 (`exemple_substrate_index.xlsx`) | 400–900 | 1,53e-2 standard | identique | 0 / 0 |
| n de T, HPFS 7980 | 300–2500 | 3,13e-2 standard | identique | 0 / 0 |
| n de T, B270 | 350–2500 | 2,11e-2 3 pôles A | identique | 0 / 0 |
| n de T, saphir 7157 | 300–5000 | 3,82e-2 standard | identique | 0 / 0 |
| n de T, silicium | 1300–5200 | 8,55e-2 standard | identique | 0 / 0 |
| **NAVG** HPFS 7980 | 300–2500 | 2,10e-3 standard | **9,23e-4 pôle IR** | 5,2e-3 / 6,4e-2 |
| **NAVG** B270 | 350–2500 | 1,22e-3 standard | identique | 0 / 0 |
| **NAVG** saphir | 300–5000 | 1,78e-2 standard | **2,61e-3 pôle IR** | 4,4e-2 / 9,4e-2 |
| **NAVG** silicium | 1300–5200 | 8,55e-2 standard | identique | 0 / 0 |

Durées : 0,2 à 1,9 s, inchangées à ±0,2 s, sauf NAVG B270 (0,57 → 2,05 s, même courbe).

## Lecture

- **n tiré de T seul** (`n_from_tnu2f`) : dispersion de 1,5e-2 à 8,5e-2 rms (dT/dn ≈ −0,24 : 0,5 % de T donne 0,02 sur n).
  Un pôle IR pèse ~1e-3 sur 300–2500 nm : invisible ; le candidat converge sans terme IR (B3 = 0, vérifié sur HPFS,
  wrmse 0,0317) et perd. **Courbes identiques au bit** : l'option est sans effet sur ces données.
- **NAVG** (n moyenné de T et R par l'auteur du classeur, 10 fois moins dispersé) : l'option **retient le pôle IR** et
  divise l'écart aux données par 2,3 (HPFS) et 6,8 (saphir sur 300–5000 nm) ; ailleurs, rien ne change.
- Hors de la plage ajustée (extrapolation jusqu'à 250 et 5200 nm), les deux courbes diffèrent jusqu'à 9,4e-2 : aucune
  des deux n'y est contrainte ; les pôles de l'option sont bornés par toute la plage évaluée (aucun pôle dans la courbe).
- `7315` : n tiré de T aberrant (rms 20) : verre absorbant, la formule de lame transparente ne s'applique pas ; écarté.

**Conclusion** : sur indices mesurés, l'option ne dégrade aucun cas et améliore nettement les deux où les données sont
assez précises pour voir la dispersion IR (saphir jusqu'à 5 µm, silice). Activation par défaut confirmée.
