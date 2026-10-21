# R2 — lanceur et vérificateur préparés le14 octobre2026

Ruff ciblé et parsing AST passent. Les sources figées et SHA256 sont dans ce dossier.
**Aucun test, aperçu ou calcul de ces nouveaux lanceurs n’a été exécuté pendant A2.**
La préparation précédente de l’observateur à9 h43 reste conservée ; son raccordement est maintenant préparé.

## Ordre impératif après A2

1. Inspecter les processus/checkpoints. A2doit être complète24/24 et ses contrôleurs terminés.
2. Faire les validations R1/A1 et du code déjà en attente, hors calcul scientifique.
3. Vérifier l’observateur et la factory avec le vérificateur préparé, dans un dossier de tentative neuf.
4. Préparer une **nouvelle copie** du replayer v11 avec échéance explicite ; ne pas modifier l’original expiré.
   Préparer le protocole R0 : mêmes300/50/100/300,101 et consensus41/42/43, les trois plans sélectionnés.
5. Rejouer R0 et vérifier `OK`, même transportfloat32 et métadonnées, profondeur et graines des appels réels.
6. Préparer le protocole de la trace native : au plus un run, même recette480/Rate240/six tours/préfixe0.
7. Aperçu puis lancement unique à16/0xffff/Normal/15 ; vérifier ressources et état, ne pas démarrer d’autre calcul.

## Vérificateur, commande future hors mesure

Les chemins ci-dessous sont des modèles de dossiers nouveaux ; ne pas réutiliser un dossier existant.

```powershell
$ratewt = Join-Path $env:USERPROFILE '.codex\worktrees\rate-equilibre\certus0310'
$reference = (Resolve-Path 'reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json').Path
$verifyOut = Join-Path (Get-Location).Path 'reports/STRAT_Rate_suite_2026-10-14/R2_observer_verification/attempt_01'
# Obsolète (copie scratch absente) : python scratch/verify_rate_native_pipeline_trace.py --worktree $ratewt --reference-state $reference --output $verifyOut
```

Ce script vérifie la factory réelle du worktree, y compris cinq chemins/états de génération avec/sans
observation. Les tâches physiques du contrôle de délégation sont substituées : il **ne mesure pas**
le SEEL ni un dépôt. Une réussite écrit `verification.json` avec verdictGO et empreintes exactes.
Un échec conserve sa trace et interdit le lancement R2. Si une source change après vérification,
revalider dans une autre tentative, sans réécrire le record précédent.

## Aperçu natif, après vérifications et R0

```powershell
$verifyRecord = Join-Path $verifyOut 'verification.json'
$control = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R0_fixed_points/attempt_01/control.json').Path
$traceOut = Join-Path (Get-Location).Path 'reports/STRAT_Rate_suite_2026-10-14/R2_native_trace/attempt_01'
# Obsolète (copie scratch absente) : python scratch/rate_native_pipeline_probe.py --worktree $ratewt --reference-state $reference --output $traceOut --deadline-utc '2026-10-16T07:00:00Z' --tag rate_native_trace_R2_20261014_v1 --verification-record $verifyRecord --validated-control $control --plan
```

L’échéance du16 octobre est **une proposition de fenêtre** pour le prochain run, pas une modification
de la campagne nocturne. La fixer dans le protocole réel après inventaire d’A2 ; si elle est dépassée,
préparer une nouvelle fenêtre explicite avant lancement. L’aperçu ne mesure rien et n’établit aucune validation.
Le chemin R0 ne sera valide qu’après création du nouveau moteur/protocole et reproduction réussie.

Le lancement scientifique reprend ces arguments sans `--plan`, à travers la procédure de ressources
et de journalisation du guide. Le nouveau probe refuse A2incomplète, les autres contrôleurs/processus,
un ancien tag, les SHA256 non vérifiés, un contrôle avec mauvais plans/profondeurs/graines ou une date expirée.
Il n’accepte pas de nouveaux budgets scientifiques à cette phase : la recette R2est fixe.

## Artefacts du run futur

- `etat.json`, ressources, arguments, deadline, empreintes de sources et de records de contrôle.
- Copies des sources utilisées, artefact de sonde même après un échec de diagnostic.
- `generated_candidates.json` avec la trace conjointe existante.
- `pipeline_trace.json` : grille, parents, sorties, seuils, appels réels, consensus et résultats finaux.
- Logsstdout/stderr et erreurs explicites ; sauvegardes atomiques du helper existant.

La sérialisation NumPy porte sur les copies de trace. Les patches sont restaurés, les sources scientifiques
figées ne sont pas modifiées. Les exceptions de tâches sont propagées. Une erreur de trace doit rendre
le run diagnostique échoué tout en conservant l’artefact scientifique, pas le faire disparaître.

Les sorties privées de plafond/dédoublonnage ne sont pas exhaustivement tracées. La profondeur réelle
vient des arguments des tâches, le cache de consensus a sa propre trace ; la taille des tableaux retenus
ne doit pas être utilisée comme profondeur du consensus. La consommation de mémoire/temps de l’observateur
reste à mesurer. Le raccordement n’est ni une nouvelle stratégie retenue ni un gain scientifique.
