# Fenêtre autorisée jusqu'au 15 octobre 2026 à 8 h Paris

La demande explicite de l'utilisateur fixe la limite à **2026-10-15T06:00:00Z**
(8 h Paris, UTC+2). [Autorisation](authorization.json) et [vérification du suivi](automation_verification.json)
conservées ici. Les préparations anciennes proposant le16 octobre restent des archives ; elles ne
fixent plus la fenêtre de lancement. Le suivi existant est actualisé, sans créer un doublon.

Priorité : terminer A2 puis poursuivre R0–R6 dans les limites du guide. Une seule mesure,
16 processeurs/0xffff/Normal/15 threads ; aucun test pendant une mesure. Pas d'arrêt d'un calcul
scientifique engagé, pas de défaut activé, de commit avant validation complète ni de publication.

À l'échéance : aucun nouveau test ou calcul ; conserver le calcul engagé, écrire le bilan honnête
avec les phases inachevées et mettre le suivi en pause. La minute de marge du dernier réveil sert
uniquement à recevoir ce réveil final malgré son décalage de quelques secondes ; elle ne prolonge
pas l'autorisation de lancer une mesure.

## Reprise après A2, avant l'échéance

Preflight puis inventaire des processus/checkpoints. A2 doit être complète24/24 et ses contrôleurs
terminés avant les validations runtime et nouvelles mesures Rate. Les sources A2 et nocturnes
restent figées. Vérifier R1 et le code en attente, puis l'observateur R2, dans des dossiers nouveaux.

La nouvelle copie du protocole R0 conserve exactement les profondeurs300/50/100/300, les plans
et attentes historiques, ainsi que101 et41/42/43. Seuls les renseignements de fenêtre/autorisation
sont actualisés. Aucun groupe de confirmation frais n'est consommé par cette préparation.

```powershell
$ratewt = Join-Path $env:USERPROFILE '.codex\worktrees\rate-equilibre\certus0310'
$reference = (Resolve-Path 'reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json').Path
$plans = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R0_replay_preparation/selected_fixed_plans_snapshot.json').Path
$protocol = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/autonomie_jusqu_20261015_0800/protocol_R0_until_20261015_0800.json').Path
$controlOut = Join-Path (Get-Location).Path 'reports/STRAT_Rate_suite_2026-10-14/R0_fixed_points/attempt_01'
python scratch/rate_fixed_replay_R0_suite.py --worktree $ratewt --plans $plans --protocol $protocol --reference-state $reference --output $controlOut --run control --deadline-utc '2026-10-15T06:00:00Z' --plan
```

L'aperçu ci-dessus est à exécuter hors mesure ; il n'est pas exécuté par cette rédaction. Après
les validations, lancer avec les mêmes arguments sans `--plan`, selon la procédure de ressources
du guide. Vérifier les trois points fixes, contrats, transportfloat32, consensus et appels réels.
La tolérance reste relative1e-7, absolue1e-10.

Après `R0=OK` et le vérificateur d'observation `GO` aux mêmes SHA256, aperçu de R2 :

```powershell
$verifyRecord = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R2_observer_verification/attempt_01/verification.json').Path
$control = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R0_fixed_points/attempt_01/control.json').Path
$traceOut = Join-Path (Get-Location).Path 'reports/STRAT_Rate_suite_2026-10-14/R2_native_trace/attempt_01'
python scratch/rate_native_pipeline_probe.py --worktree $ratewt --reference-state $reference --output $traceOut --deadline-utc '2026-10-15T06:00:00Z' --tag rate_native_trace_R2_20261014_v1 --verification-record $verifyRecord --validated-control $control --plan
```

Choisir des noms de tentative/tag neufs si ceux-ci existent déjà. Mesurer ensuite une seule trace,
avec la même échéance, puis sélectionner le facteur R3 à partir des observations. Tous les futurs
contrôleurs R3–R6 doivent vérifier l'échéance **avant chaque mesure**, y compris un groupe de
confirmation. Une boucle ne doit pas consommer toute une liste au-delà de la limite.

La fin d'A2 est attendue avant cette nouvelle échéance mais n'est pas un résultat acquis. Le
contrôleur A2 original n'a pas de garde dynamique pour cette nouvelle date : si A2 reste active
à l'approche de8 h, traiter sa continuation avant la limite avec une reprise bornée, préserver
l'enfant scientifique et ses artefacts, puis documenter le checkpoint. Ne pas compter sur la
seule expiration du suivi pour arrêter l'enchaînement d'un contrôleur externe.

Cette préparation ne promet pas l'achèvement de toutes les phases avant8 h. Le bilan devra séparer
gain local confirmé, recherche native, code validé et travail encore en attente.
