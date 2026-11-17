# Chantier 39 — exécutable gelé reconstruit, 2026-11-17

- **Version** : dans l'exécutable, `certus_metrology.git_state()` rendait `("", None)` : les exports ne disaient pas
  quel code les avait produits. Corrigé en `260e4e8c` : `certus_hub.spec` écrit `BUILD_COMMIT.json` (commit, état
  modifié) à côté de l'exécutable, `git_state()` le lit une fois gelé ; test rouge sur le code d'avant.
- **Construction** : `python -m PyInstaller certus_hub.spec --noconfirm` dans un clone hors du dossier synchronisé
  (`C:\certus_clone`, `260e4e8c`), PyInstaller 6.22.3, Python 3.15.2 ; 420 Mo dans `dist\CERTUS_HUB` ;
  `BUILD_COMMIT.json` : `260e4e8c…`, `"dirty": false` ([copie](BUILD_COMMIT.json), [résumé](build_resume.txt)).
- **Fumée** : le hub et les dix modules lancés par `--run-module`, `QT_QPA_PLATFORM=offscreen`, vivants après 45 s
  et sans `certus_frozen_startup.log` : **11/11 OK** ([sortie](smoke_out.txt), [script](smoke_frozen.py.txt)).

Non vérifié : un export réel fait depuis l'exécutable (le commit qu'il porte est couvert par le test unitaire et la
présence du fichier) ; un calcul complet dans chaque module ; l'affichage à l'écran (essais humains, chantier 33).
