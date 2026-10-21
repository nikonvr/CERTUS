# R0 — copie de contrôle préparée le14 octobre2026

`scratch/rate_fixed_replay_R0_suite.py` est une nouvelle copie du moteur v11.
L’ancien fichier et sa garde nocturne restent à octets identiques. **Aucun aperçu, test runtime
ou calcul R0 n’a été lancé pendant A2.**

Les modifications concernent la CLI, les gardes et la sauvegarde :

- CLI limitée au contrôle de points fixes ; échéance explicite avec fuseau obligatoire.
- Campagne A2complète24/24, sans calcul courant ; continuation terminée et aucun processus connu vivant.
- Dossier de sortie sous `reports/` du projet ; tentatives conservées.
- Sauvegarde des résultats/requêtes via le helper atomique existant, avec ses40 reprises sur `PermissionError`.

La comparaison AST de **tout le corps scientifique du try**, depuis l’initialisation jusqu’au
contrôle final des sources, est identique àv11 : paramètres, construction des plans, Worker,
transportfloat32, simulation, observateur, contrats et tolérances. La preuve et les SHA256 sont dans
`AST_comparison.json`. Cette identité statique ne vaut pas réussite du point fixe ni test d’exécution.
Ruff ciblé passe. Le helper A2 n’a pas été modifié.

## Plans et protocole figés

`selected_fixed_plans_snapshot.json` est la copie à octets identiques des trois plans retenus :
référence900951015, parent9900006 et meilleur local9900008, avec leurs scores attendus historiques.
Ne pas regénérer des enfants ni remplacer leurs attentes par les valeurs d’un nouveau run.
Le moteur copie les plans complets, y compris Rate, fente et témoins lorsqu’ils sont présents.

`protocol_R0.json` conserve300 tirages pleins, screening déclaré50, `dp_top_k`100,300 tirages par
graine de consensus, recherche101 et consensus41/42/43. Il ne contient aucune nouvelle confirmation
fraîche : c’est un contrôle de reproduction. Le protocole de R3 sera distinct et fixé avant ses résultats.

## Ordre de lancement futur

Après A2 : preflight, état/processus, validations R1 et du code en attente, vérificateur de trace R2.
Une fois la machine libre, relire le moteur et cette préparation, puis faire l’aperçu ci-dessous.
Les dossiers d’aperçu et de tentative sont des modèles ; choisir un dossier neuf.

```powershell
$ratewt = Join-Path $env:USERPROFILE '.codex\worktrees\rate-equilibre\certus0310'
$plans = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R0_replay_preparation/selected_fixed_plans_snapshot.json').Path
$protocol = (Resolve-Path 'reports/STRAT_Rate_suite_2026-10-14/R0_replay_preparation/protocol_R0.json').Path
$reference = (Resolve-Path 'reports/STRAT_Rate_equilibre_AB_2026-10-13/etat.json').Path
$controlOut = Join-Path (Get-Location).Path 'reports/STRAT_Rate_suite_2026-10-14/R0_fixed_points/attempt_01'
# Obsolète (copie scratch absente) : python scratch/rate_fixed_replay_R0_suite.py --worktree $ratewt --plans $plans --protocol $protocol --reference-state $reference --output $controlOut --run control --deadline-utc '2026-10-16T07:00:00Z' --plan
```

L’échéance du16 octobre est une proposition de fenêtre ; la fixer dans le protocole réel en fonction
de la fin d’A2. Le lancement reprend les mêmes arguments sans `--plan`, à16/0xffff/Normal/15 selon
la procédure du guide. Un aperçu n’établit aucune validation scientifique. Le lanceur vérifie
HEAD, fichiers modifiés et SHA256 des sources historiques avant/après.

## Conditions pour accepter R0

Le `control.json` doit porter `verdict=OK`, aucune erreur et les trois plans complets, chaque
score attendu reproduit à `rel_tol=1e-7`, `abs_tol=1e-10`. Ne pas élargir les tolérances.
Vérifier les appels réels à300 pour101/41/42/43 sur chaque ID, les trois graines de consensus
complètes par plan, mêmes niveaux de bruit et transport d’indicesWorkerfloat32.

Écrire durée, ressources, bibliothèque/cache, SHA256 du nouveau moteur, protocole et résultats.
Le succès permettra seulement le lancement de la trace native R2 : il ne prouve aucun gain natif.
Si le point fixe échoue, conserver tentative/logs/paramètres et chercher la cause avant de poursuivre.

## Sauvegarde et limites

Le sérialiseur NumPy d’origine est conservé ; le payload converti est transmis au helper atomique.
Le helper reprend40 fois sur refus temporaire, puis propage l’erreur et consigne la requête échouée.
La source de physique n’a pas changé. La CLI conserve certains blocs historiques désormais
inaccessibles avec `--run control` seulement, afin de préserver le corps de calcul d’origine.
Les contrôles runtime des gardes/sauvegardes restent à exécuter hors A2 ; la préparation ne les déclare pas passés.
