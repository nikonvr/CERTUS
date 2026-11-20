# Gel du 2026-11-20 (lot 3)

- **Construction** : `python -m PyInstaller --noconfirm --distpath %TEMP%\certus_gel_1120\dist --workpath
  %TEMP%\certus_gel_1120\build certus_hub.spec`, depuis le worktree du dépôt Drive (le clone hors Drive du 17/11 est
  interdit depuis le 19/11) ; sorties hors Drive pour ne pas synchroniser 422 Mo. PyInstaller 6.22.3, Python 3.15.2
  ([résumé](build_resume.txt)). `BUILD_COMMIT.json` : `183ebcd9`, `"dirty": false` ([copie](BUILD_COMMIT.json)).
- **Piège** : un premier essai depuis le shell de l'agent n'avait pas `C:\Windows\System32` dans `PATH` ; PyInstaller
  n'a pas résolu `VCOMP140.DLL` (avertissement « could not resolve »), et `release_checks.py` l'a refusé (« no OpenMP
  runtime »). Reconstruit avec System32 dans `PATH` : `VCOMP140.DLL` présent.
- **Contrôles** : `tools/release_checks.py --check-frozen --check-frozen-run --startup-timeout-sec 45`, pointé sur ce
  dossier ([enveloppe](release_checks_temp.py)) : **PASSED** ([sortie](release_checks.txt)) — verrous, structure,
  artefact (runtime Python, couche et runtime OpenMP, licences) et démarrage du hub et de chaque module.

Non vérifié : un calcul complet dans chaque module gelé ; l'affichage à l'écran (essais humains, chantier 33).
L'exécutable est dans `%TEMP%\certus_gel_1120\dist\CERTUS_HUB` (hors dépôt, non versionné).
