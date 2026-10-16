# Publication des preuves Rate,16octobre2026

L'utilisateur demande « push et commit all », puis un ménage drastique, choisit
**archives locales / dépôt Git léger**, et demande `certus0310` sous1Go, Git compris.
Le contrôle après ménage donne environ509Mo, Git compris ; le relevé après commit fait foi
dans `delivery_verification.json` lorsqu'il existe.

Les2242JSON volumineux sont conservés en gzip sans perte **hors du dossier CERTUS**, dans :

```text
D:\drivefl\01_Recherche_Enseignement\02_Couches_Minces_Optique\couches minces 2026\Archives_CERTUS_20261016
```

Les archives binaires restent locales, conformément au choix explicite de l'utilisateur ;
elles ne font pas partie du clone Git. Le dépôt garde les sources, bilans, plans, paramètres,
échecs et manifestesSHA. Pour changer de machine, conserver aussi ce dossier d'archives.
Le chemin effectif et les répertoires déplacés sont dans `archive_location.json`.

`manifest.json` (25grosJSON récents), `compact_manifest.json` (2074autresJSON récents) et
`historical_manifest.json` (143anciensJSON de simulation suivis) associent les chemins
bruts aux archives et portent tailles/SHA256. Chaque gzip a été relu et sa décompression
vérifiée avant retrait du brut. Total brut conservé :52 388 365 805octets. Les143anciens
JSON sortent deHEAD mais restent aussi dans l'historiqueGit ; aucun reset ni
réécriture d'historique n'a été effectué. Une maintenance automatique du premier commit
a signalé six refus de suppression de métadonnées d'anciens worktrees ; les commits
suivants désactivent cette maintenance. Les quatre contextesCodex restent présents et inchangés.

Les mesuresINDEX/METAL/SINGLE et `studies/` n'ont pas été touchés. Les caches régénérables
ont été retirés ; l'ancienne copie `.claude` et les journaux runtime sont conservés dans
l'archive externe. Les quatre contextesCodex historiques restent à leur place, inchangés.

Les règles `.gitignore` concernent les2242chemins bruts exacts archivés, les caches compilés
et les deux répertoires d'archives locales, pas tous les futursJSON ni toutes les futures
traces. Les petits artefacts, plans, sources et audits sont versionnés normalement.
`.gitattributes` préserve les bytes des rapportsSTRAT sans conversionLF/CRLF, pour garder
leurs empreintes. Les copies de sources, patches et journaux figés sont traités comme
preuves binaires ; leur ancien formatage n'est pas réécrit. Les sources de production
et les documentsMarkdown gardent leurs contrôles habituels. Aucun ancien protocole ni
résultat numérique n'est réécrit.

Restaurer seulement le fichier nécessaire, depuis la racine :

```powershell
python scripts\restore_rate_evidence.py --path reports/STRAT_Rate_suite_2026-10-15/R5_integration/native/measurement/pipeline_trace.json --verify-only
python scripts\restore_rate_evidence.py --path reports/STRAT_Rate_suite_2026-10-15/R5_integration/native/measurement/pipeline_trace.json
```

`--archive-root CHEMIN` permet de choisir la racine de l'archive sur un autre poste ;
sinon `archive_location.json` est utilisé. Le restaurateur vérifie lesSHA, refuse un
chemin brut sortant de `reports/` et refuse d'écraser un résultat différent. Une restauration
réelle externe de1 190 048octets a passé leSHA, puis sa copie de travail a été retirée.
Neuf tests passent, notamment corruption, traversée de chemin, non-écrasement et archive externe.
Le sandboxCodex refuse la création de liens durs ; le test runtime passe avec l'accès hôte normal.

Sans `--path`, le restaurateur traite tout le jeu et recrée environ52Go : ce n'est pas
le fonctionnement prévu pour garder le dossier de travail sous1Go. L'absence des bruts
dans un clone avant restauration ne signifie pas une mesure perdue. Un balayage des seuls
JSON décompressés n'est plus exhaustif pour déclarer de nouvelles graines fraîches : consulter
les manifestes de graines conservés et, au besoin, parcourir aussi les archives.

Contrôles : `pre_commit_audit.json`, `restore_runtime_verification.json`,
`validation_summary.json`. Le diagnostic et le prompt à donner à l'IA suivante sont dans
[la passation](../../docs/STRAT_Rate_reprise_20261016.md).
