# Chantier 44, étape 1 — profil du noyau STRAT par poste (2026-11-15)

`python scripts/probe_strat_kernel_profile.py` sur `c0dc68c9` + sonde non commitée, Windows, Python 3.15.2. Juge de
paix (`JSON-strat-example.json`, 48 couches), plan synthétique : blocs de 6 couches alternant 550 et 600 nm. Chemin de
production : grille grossière, lissage 1, arrêt parabolique, `arming` = 2, bruit de lecture à A = 5e-4, seuil 1,66 A.
Sorties : `console.txt`, `profil.json`, `batch_1fil.json`, `batch_16fils.json`.

## Mesures (µs par appel, meilleur de 5 × 2 000 appels)

| couche | matrices | niveau | balayage | bruit | détection | inversion | noyau entier | somme des postes |
|---|---|---|---|---|---|---|---|---|
| 3 (historique 3 couches) | 0,39 | 0,78 | 4,13 | 1,98 | 0,39 | 0,30 | 6,08 | 7,99 |
| 12 (début de bloc) | 3,14 | 0,76 | 2,11 | 0,99 | 0,26 | 0,30 | 5,27 | 7,57 |
| 24 (début de bloc) | 6,48 | 0,76 | 2,07 | 1,02 | 0,25 | 0,30 | 6,83 | 10,88 |
| 36 (début de bloc) | 9,60 | 0,76 | 2,05 | 1,03 | 0,24 | 0,30 | 8,61 | 13,99 |
| 47 (historique 4 couches) | 12,16 | 0,77 | 4,36 | 1,99 | 0,58 | 0,30 | 13,09 | 20,15 |

Options hors production : inversion exacte (D97) 0,81 à 1,44 ; ancres exactes (D96) 0,01 à 1,78 (0,01 = POEM ne tient
pas à cette couche, l'option n'a rien à lire).

Batch de production (`simulate_stack_robustness_batch`, 2 000 tirages × 48 couches) : **8,27 µs par appel sur un fil**
(0,794 s), 0,98 µs par appel sur 16 fils (0,094 s), soit 8,4 fois plus vite.

## Lecture

- **Le §5 de l'audit est confirmé pour les matrices** : leur coût croît linéairement avec la profondeur (~0,26 µs par
  couche sous la couche courante) et représente environ 60 % de la somme des postes dès la couche 24.
- **Le commentaire D94 n'est pas confirmé** : le bruit coûte environ la moitié du balayage (15 ns par point contre 32 ns
  pour les deux signaux), pas davantage que la trigonométrie d'une lecture.
- Détection et inversion parabolique pèsent peu (≤ 0,6 µs). Le niveau figé coûte 0,77 µs à toute profondeur.
- **La somme des postes dépasse le noyau entier de 30 à 50 %** : mesurés seuls, les postes ne profitent pas du code
  partagé et compilé ensemble dans le noyau. Leurs valeurs sont des majorants ; les proportions restent indicatives.
- Le batch sur un fil (8,27 µs) correspond à la moyenne du noyau sur les 48 couches : le noyau est l'essentiel du coût.

## Ce que cela dit des leviers (estimations, non mesurées)

- **V1** (matrices portées d'une couche à l'autre dans un bloc) supprime la part linéaire en profondeur, sauf au début
  de chaque bloc. C'est le plus gros levier, croissant avec le nombre de couches.
- **V2** (nominal hors de la boucle Monte-Carlo) supprime environ la moitié des matrices, la moitié du balayage et le
  niveau figé.
- Leurs gains se recouvrent sur les matrices.
- Risque de bits : `_stack_matrix_pair` fusionne réel et nominal dans une seule boucle, exprès (« two loops moved the last
  bits »). 👤 accepte un écart au dernier bit (2026-11-15) ; `c1_diff` en donnera la taille.
