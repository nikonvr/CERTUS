# Mineurs de l'audit du 2026-11-15 — double vérification (2026-11-16)

Passe 1 (`mineurs_verification_1.md`) : relevés confrontés au code de `1210fd23`. Passe 2 (`mineurs_verification_2.md`) :
vérificateur indépendant, emplacement et question neutre seulement, sans les relevés. Lecture du code ; trois extraits
mesurés (L1-m1, L1-m6, L4-m1). Aucun mineur n'était emporté par les 27 corrections.

## À corriger : les deux passes d'accord (21)

L1-m1 cliquet TMM aveugle à `num = t1 - t2` · L2-m1 porte ELITE au mauvais niveau de bruit · L2-m2 marges normalisées par
le niveau du milieu · L2-m3 biais de fente perdu en silence · L2-m6 taux « nominal » affiché au mauvais niveau ·
L3-m2 RMSE 1e15 après arrêt · L3-m3 corridor hors du modèle affiché · L3-m4 except de `_polish_lbfgsb_chunked` ·
L4-m1 CSV français lu en 3 colonnes, premier point perdu · L4-m2 T tronqué à la plage de R · L4-m3 feuille en µm ·
L4-m6 et L5-m4 exports Excel non atomiques · L5-m3 synthèse FIELD bloquée · L5-m5 seuils LIDT 0,5/0,5 ·
L5-m7 couleurs hexadécimales · L5-m8 indices inventés contre D88 · L6-m1 boutons STRAT grisés · L6-m2 session STRAT ·
L6-m5 cibles RE (grille décroissante : toutes rejetées) · L6-m6 export METAL incomplet.

## À corriger : désaccord tranché par ma lecture (5)

| id | passe 1 | passe 2 | tranché |
|---|---|---|---|
| L1-m2 | NON | OUI | OUI : une cible sur une seule λ (raie laser) vaut 1e12 au coût seul, son vrai coût au chemin coût + gradient |
| L3-m1 | NON | OUI | OUI : l'avertissement SOL2/SOL3 sort toujours et désigne une fausse cause ; `ctx.obj(z0)` |
| L4-m5 | NON | OUI | OUI : les marches ±d du corridor tournent en 2 fils (`spline_profile_corridors.py`) à des d différents et écrivent toutes deux `_THICK_BUF` |
| L4-m7 | NON | OUI | OUI : une ligne (`<meta charset="utf-8">`) dans des rapports scientifiques |
| L6-m3 | NON | OUI | OUI : SUBSTRATE gèle la fenêtre pendant un ajustement DE (même classe que M-L6c) |

## Pas à corriger (3)

L2-m5 (tampon RE latent) et L5-m2 (sans effet) : NON des deux passes. L2-m4 : passe 2 OUI, tranché NON — l'échec
d'un TypeError dans ELITE est bruyant, pas faux, et aucun déclenchement n'est établi (la grille est filtrée sur les clés).

## Décidés par 👤 le 2026-11-16 (8)

L1-m3 avertir · L1-m4 épaisseur de substrat exposée, inactive par défaut · L1-m5 et L3-m6 graines DESIGN et FIELD ·
L1-m6 raccord d'Urbach (D71) · L3-m5 gestionnaire de journal racine · L3-m7 classement marqué incomplet ·
L5-m6 pas de lissage automatique.

## À décider par 👤 (3)

L4-m4 : les workers de phase B STRAT perdent Im(n) (mémoire partagée réelle) · L5-m1 : l'export et la sauvegarde DESIGN
nettoient le dessin (le spectre exporté n'est plus celui de l'empilement) · L6-m4 : le l0 du JSON RE écrase celui du classeur.
