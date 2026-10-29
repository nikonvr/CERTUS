# envelope_v2 — enveloppe RMSE*(N) du 50/50, filtre trois raies, antireflet (2026-10-26 → 28)

Juge : oracle indépendant `tests/oracle/tmm_reference.py` ; résidus et jacobien : noyau CERTUS
`_res_jac_lossless_normal_kernel`. Journal daté de chaque lancement : `campaign.log`.

## Scripts

| script | rôle |
|---|---|
| `search.py` | recherche à N fixé (élites par N, aiguilles, couches épaisses, suppressions) ; cibles `SEARCH_TARGET` = `bs5050` (défaut), `threeline`, `ar` ; options inactives par défaut : `SEARCH_STARTS=none`, `SEARCH_RANDOM`, `SEARCH_TOT` (TOT imposée), `SEARCH_WORKERS` (processus) |
| `gradual.py` | évolution graduelle à TOT imposée depuis le substrat nu, aiguilles par fonction P exacte (un appel du noyau) ; `GRAD_DEEP` (K), `GRAD_DTOT`, `GRAD_RESUME`, `GRAD_WORKERS`, `GRAD_TAG`, `GRAD_CLEAN` (nm : retrait des couches plus fines après chaque convergence, gardé s'il n'empire pas ; 0 = inactif), `GRAD_GROW=1` (pas de Trubetskov 2020 : une couche épaissie jusqu'au minimum suivant ; 0 = inactif) |
| `qwstart.py` | départs quart d'onde perturbés à TOT imposée, puis aiguilles et nettoyage (prêt, non lancé) |
| `grid_test.py` | grille du trois raies : Fig. 3 de 2012 polie sur 277/270/263 points contre la Table 1 |
| `fig4_2020_extract.py` | lecture des designs de la Fig. 4 de Trubetskov 2020 dans l'image (`fig4_2020_designs.csv`) |
| `design_distance.py` | distance d'alignement entre designs de N différents (aiguilles et fusions, extrémités libres plafonnées) |
| `barrier.py` | barrière de MF le long du chemin d'alignement (string method) ; borne supérieure |
| `seed.py` | germe d'un design : réduction par retraits (faisceau), puis jugement des redéploiements |
| `compare3line.py` | MF contre TOT face à Trubetskov 2020 Fig. 5 (`trubetskov2020_fig5_digitized.csv`), nettoyage à 5 nm |
| `descent.py` | descente en TOT depuis le bassin à 0,065 % (échec, voir plus bas) |
| `diag5050.py` | pourquoi l'évolution graduelle perd sur le 50/50 (H1 axes, H2 convergence, H3 reprise) |
| `constrained.py` | N fixé, épaisseurs optiques bornées à 100–350 nm : trois raies à 51 couches, miroir chaud à 40 couches (2012, Sec. 2), leur procédure stochastique ; `CONSTRAINED_RESUME` (reprise d'un csv) |
| `cissoid_opt.py` | OIC 2016 B1 (cissoïde), aiguilles sur 9 matériaux dont 3 métaux, nettoyage ≤ 50 couches ≥ 3 nm ; cible `cissoid_target_b1.csv` |
| `ef2012.py` | EF1–EF10 (Amotchkina 2012) : reproduction de la Table 3, robustesse |
| `catalog.py`, `ar_robust.py` | antireflet robuste aux erreurs aléatoires d'épaisseur optique (hors bilan de l'article : problèmes trop simples, décision de 👤) |
| `monotone.py`, `check6401.py` | réparation de RMSE*(N) non monotone ; contrôle sur 6401 points |

## Filtre trois raies (Tikhonravov & Trubetskov, AO 51, 7319, 2012, éq. 1)

Grille : 277 points (pas de 1 nm, bornes incluses). MF = 100 × RMSE. Mesures du 2026-10-28, MF oracle.

| méthode | 9 700 nm | 11 000 nm | 80 couches | 90 couches |
|---|---|---|---|---|
| évolution graduelle classique | 0,215 (N 80) | 0,163 (N 90) | 0,215 | 0,163 |
| évolution graduelle deep K=4 | 0,216 (N 77) | 0,148 (N 90) | — | 0,148 |
| graduelle puis N fixé (essai A, TOT libre) | — | 0,158 (10 800 nm, N 85) | 0,121 (TOT 11 407) | 0,121 (TOT 11 118) |
| Trubetskov 2020, deep (numérisé) | 0,192 | 0,058 | — | — |
| Tikhonravov 2012 | 0,191 (N 75, 9 687,5 nm) | — | — | — |

- Le bassin à 0,064–0,069 % n'apparaît qu'à TOT ≈ 11 600 nm et N ≥ 92 (essai A) ; une descente en TOT par pas de
  50 nm le perd en 250 nm (0,077 % à 11 400 → 0,196 % à 11 150, `descent.log`) ; à TOT imposée 11 000 nm, la recherche
  à N fixé plafonne vers 0,144 % pour N = 80–90 (essai C, arrêté).
- Trubetskov 2020 Fig. 4 (barres comptées dans l'image) : 104 couches (classique) et 101 (deep), TOT ≈ 14 000 nm,
  ≈ 138 nm d'épaisseur optique par couche.
- Temps publiés (Trubetskov 2020, Xeon W-2155 10 cœurs) : 3 min 03 s classique, 7 min 51 s deep. Les nôtres (un
  cœur, OpenBLAS multithread) : 1 h 44 classique jusqu'à 11 000 nm, ≈ 6 h 30 deep.
- OpenBLAS multithread ralentit la recherche : `OPENBLAS_NUM_THREADS=1` la rend ≈ 2,5× plus rapide en série
  (169 s contre ≈ 7 min pour la même étape, `parallel_check_*`). En parallèle, 7 processus à un fil chacun.

- Grille : **277 points, bornes des bandes comprises** (`grid_test.py`, 2026-10-29) : les 10 designs de la Fig. 3 de
  2012, polis sur chaque grille, redonnent la Table 1 à 0,007 près (rms, max 0,016) sur 277 points ; sur 270 ou 263
  points ils tombent à 0,24–0,40, 0,17–0,24 sous la Table 1, ce qu'un optimum de leur MF ne ferait pas. Sans réoptimisation, nos designs perdent 20 à 30 % de MF sur
  270 ou 263 points (bornes des zones exclues) : 0,215 → 0,176 → 0,149 à 9 700 nm, 0,148 → 0,124 → 0,107 à 11 000 nm.
- Problème contraint de 2012 (51 couches, épaisseur optique 100–350 nm) : 10 solutions publiées, MF 0,464–0,599.
- Résultats du 2026-10-29 (51 couches battu, course contre 2020, germes, miroir chaud) : `AUDIT_2026-10-28.md`, section 7.

## Enseignements de méthode (2026-10-26 → 29)

Chiffres et preuves : `AUDIT_2026-10-28.md` (sections 1, 2 et 7) et `campaign.log`.

1. **Définir le problème avant de chercher.** Chaque comparaison commence par redonner un nombre publié avec leur
   design : grille du trois raies à 277 points, bornes comprises (Table 1 à 0,007 près) ; Table 3 des EF à 45° seul ;
   cible de la cissoïde à 14 chiffres. Une grille de 270 points abaisse la MF de 20 à 30 % : sans ce contrôle, on
   « bat » Trubetskov à tort.
2. **Leur pas d'évolution graduelle n'est pas le nôtre.** Trubetskov 2020 (Sec. 2) épaissit **une couche** jusqu'au
   minimum suivant de la MF à un paramètre et garde la moins mauvaise ; le nôtre étirait tout le design ou ajoutait
   une couche extérieure à TOT + 100 nm. Avec leur pas (`GRAD_GROW`), nos points tombent sur les leurs (3 802 nm,
   6,293 contre 3 804 nm, 6,298 dans leur Fig. 5) ; verdict au-delà de 8 800 nm en cours.
3. **Pas de design de départ chez eux.** 2012 et 2020 partent du substrat nu ; les cavités (couches proches de la
   demi-onde dans un empilement quasi quart d'onde à 550 nm) apparaissent pendant l'évolution. Seules les couches de
   moins de 5 nm sont retirées à la fin (2020) ; une couche fine retirée prend l'indice de sa voisine, TOT inchangée (2007).
4. **Nos aiguilles fabriquent des couches minces.** Leurs designs ont 1–2 couches sous 20 nm d'épaisseur optique, les
   nôtres 12–17, même partis de leur design. Le nettoyage après chaque convergence (`GRAD_CLEAN` 2 nm) gagne 25–30 % et
   20 couches près de leur bassin, presque rien depuis nos propres designs.
5. **Le deep bat le classique à départ égal** (germe à 89 couches : 0,018 contre 0,034).
6. **Germes** : seul un germe très proche de leur design (89 couches sur 101) redescend vers leur bassin ; à 79
   couches ou moins, on retombe au plateau. Réduire en laissant la TOT libre fausse le test : la TOT doit remonter.
7. **Optimiseur local** : trf avec jacobien exact pour le miroir chaud (L-BFGS-B : 1,05 contre 0,865) ; L-BFGS-B
   pour le trois raies contraint à 51 couches (trf ne converge pas depuis des départs aléatoires bornés).
8. **Paysage** : leurs 10 designs à 51 couches sont à 21–31 % de TOT l'un de l'autre ; notre 0,4597 est séparé de
   leur meilleur par une barrière de MF ≈ 29 (borne supérieure) : leurs sauts de 3 % ne passent pas d'un bassin à l'autre.
9. **Calcul** : un fil OpenBLAS par processus et 7 processus (sinon ×1,6 seulement) ; une campagne à la fois, et
   `TaskStop` ne tue pas les enfants : arrêter par PID.

## Définitions retrouvées

- **EF1–EF10** (Amotchkina et al., AO 51, 8677, 2012) : leur Table 3 est la MF à 45° seul, points R et T en une seule
  moyenne, et non leur Eq. 2 à 43/45/47°. Rapport à la Table 3 : 0,976 ± 0,012 (`ef2012_check.out`).
- **Cissoïde OIC 2016 B1** : (R − 0,5)² = k² s³ / (2a − s), s la distance en nm au croisement R = 0,5 (400, 500, 600,
  700 nm), 2a = 100 nm, |R − 0,5| = 0,3 à s = 50 nm, arrondie à 4 décimales (`cissoid_target_b1.csv`). Ajustée sur le
  tracé vectoriel de la Fig. B.1 de l'énoncé, elle redonne la MF de leur design d'exemple à 14 chiffres (0,89721320429466).
  À battre : 0,0139 (Trubetskov, vainqueur du concours, 3 diélectriques et 2 métaux) et 0,0238 (Trubetskov 2020).
- **Miroir chaud** (2012, Sec. 2) : T = 100 % à 400–690 nm, 0 % à 710–1200 nm, pas de 2 nm (392 points), 40 couches
  d'épaisseur optique 100–350 nm : design A 0,865, design B 0,913.

## 50/50 : évolution graduelle contre enveloppe

Évolution graduelle deep K=4, pas de 50 nm (`gradual_bs5050_deep4.csv`) : meilleure RMSE 6,7e-6 à TOT 4 600 nm
(N 44) ; enveloppe : 5,5e-6 à N 37 (TOT 4 280 nm, `curve_mono_free.csv`). À N égal l'enveloppe gagne d'un facteur
≈ 10, à TOT égale de ≈ 1,6.
