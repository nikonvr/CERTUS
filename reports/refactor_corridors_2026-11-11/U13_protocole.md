# U13 — ce que la machine a mesuré, et ce qui reste à 👤

Rédigé le 2026-11-13. U13 : « ce que l'audit ne pouvait pas faire : écran réel et HiDPI, thème sombre, lecteur
d'écran, cinq utilisateurs sur trois tâches ».

## 1. Mesuré par la machine (hors écran, `scripts/audit_ux_certus.py`)

| Point | Mesure | Garde |
|---|---|---|
| Écran à l'échelle | `--scale` : rapport de pixels réellement appliqué par Qt (1,25 · 1,5 · 2). 1920×1080 à 150 % (1280×720 logiques) : 2 boutons sans infobulle dans DESIGN et INDEX SPLINE (flèches d'onglets), 0 après ; 125 % et 200 % : 0/11 module en défaut | `tests/ui/test_ux_a_scaled_screen_keeps_the_rules.py` |
| Thème sombre, logo (A10) | encre principale du logo `#05103b` sur l'en-tête sombre `#111827`, sous 4,5:1 ; encres de la palette sombre après | `tests/ui/test_ux_the_logo_reads_in_both_themes.py` |
| Thème sombre, feuilles | déjà mesuré (`dark_stale`, `low_contrast_dark`) | audit |
| Noms pour un lecteur d'écran, clavier | déjà mesurés (`a11y_unnamed`, ordre de tabulation, anneau de focus) | `tests/ui/test_a11y.py`, `test_ux_tab_order.py`… |

Limite : `offscreen` ne dit rien du flou d'une icône matricielle à 150 %, ni de ce qu'un lecteur d'écran **lit**
réellement : il dit seulement que chaque contrôle porte un nom.

## 2. À faire par 👤 (une demi-journée)

1. **Écran réel à 150 %** (Paramètres Windows › Affichage › Échelle) : ouvrir les onze modules ; noter tout texte
   coupé, toute icône floue, tout panneau qui défile alors qu'il ne devrait pas.
2. **Thème sombre à l'écran** : basculer dans chaque module ; noter ce qui reste clair ou illisible.
3. **Lecteur d'écran** : Narrateur (Ctrl+Win+Entrée) ; dans DESIGN, atteindre au clavier seul le bouton PGLOBAL
   et le lancer ; noter tout contrôle annoncé « bouton » sans nom, ou dans un ordre absurde.
4. **Cinq utilisateurs, trois tâches**, sans aide, chronométrés, à voix haute :
   - DESIGN : ouvrir l'exemple, lancer l'optimisation, exporter l'empilement ;
   - STRAT : ouvrir l'exemple depuis l'accueil, lancer, lire le SEEL de la meilleure stratégie ;
   - INDEX : charger une mesure, ajuster, enregistrer le résultat.
   Par tâche : réussie ou non, durée, hésitations (où, combien de secondes), phrase dite au moment du blocage.
   Un blocage vu chez deux utilisateurs sur cinq est un défaut à corriger.

Les constats vont dans ce fichier, section 3, un par ligne : module, ce qui a été vu, chez combien d'utilisateurs.

## 3. Constats de 👤

(vide)
