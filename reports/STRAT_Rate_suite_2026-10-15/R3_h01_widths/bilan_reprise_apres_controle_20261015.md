# Reprise après le contrôle R3 — 15 octobre2026

## État scientifique

Contrôle **terminé à11 h20 Paris**, PID21508 terminé, **auditGO** dans[le rapport](audit_control.json).5412 stratégies,1059 lignes de consensus complet ; meilleur ID901054165, score0,032410960467156955, SEEL0,3600608863nm. Durée2660,18s, soit44min20s exports inclus. Sources et scripts exacts, copie native/root et trois exports contrôlés ; aucun appel physique nouveau dans l’audit. Ce résultat reproduit le natif historique, pas un nouveau gain.

**Variante engagée à11 h35 Paris**, coordinateur33592 et enfant17704 au lancement. Lire `pair_controller_v4.json`, `variant/etat.json`, les verrous et les processus ; ne pas se fier au seul numéro dePID. Les deux réservations de la paire sont prises, aucun test ni modification des scripts/sources actifs, aucun doublon. La source scientifique reste inchangée ; seul le facteur du protocolev3, largeurs conjointes1..7, est actif dans la variante.

## Échec du coordinateur et preuves

Le coordinateur36608 inscrit `Arm failed: control` malgré l’état scientifique `complete`. Sous Windows PowerShell5.1, `Start-Process -PassThru`, `WaitForExit` puis `Refresh` donnent un `ExitCode=null` si le handle n’est pas conservé ; `null -ne 0` déclenche ce faux refus. Le shell de l’outil rend0 sur le même processus vide : il fallait vérifier le runtime exact du coordinateur.

[Contre-épreuve sous PowerShell5.1.26100.9549](controller_exitcode_diagnostic/windows_powershell_comparison.json) : Python vide, sans handle→code absent/refus ; handle conservé→code0/passe. Ce contrôle ne simule aucun dépôt et ne mesure aucune performance scientifique. L’ancien code de sortie du contrôle scientifique n’ayant pas été enregistré, on ne l’invente pas ; son adoption repose sur l’état complet, le verdictOK, les empreintes, les traces et l’audit.

La première reprise41504 s’arrête **avant tout enfant et réservation** : `Get-FileHash` absent de l’environnement de modules du PowerShell de fond. [Tentative conservée](controller_repair03_before_child_failed.json). La copie suivante utilise directement `System.Security.Cryptography.SHA256`, sans module additionnel ; [preuve sous le même PowerShell5.1](controller_exitcode_diagnostic/verify_resume_sha.json), empreinte exacte de l’état de contrôle.

Le coordinateur courant `scratch/run_rate_R3_widths_resume_variant_v2.ps1` conserve le handle, adopte l’état de contrôle auSHA audité et lance **uniquement la variante**. [Lancement](pair_launch_v4.json). Les fichiers et journaux des contrôleurs précédents restent intacts. Aucun résultat n’est écrasé, aucun contrôle rejoué, aucun paramètre physique changé.

## À la fin de la variante

Vérifier le processus terminé, l’état, les copies, les sources et le code de sortie enregistré. La copie `scratch/audit_rate_R3_arm.py --arm variant` est préparée ; ne l’exécuter qu’après la fin réelle de la mesure. Elle crée `audit_variant.json` sans écraser un rapport existant ; ses hypothèses de jointures sont celles déjà vérifiées pour le contrôle.

Figer les finalistes des deux voies avant toute nouvelle notation ; renoter à profondeur homogène300/50/100/300, base101 et consensus41/42/43, avec les comparateurs9900001/9900006/9900008 et la référence. Créer une nouvelle copie bornée de lanceur et un quota de renotation explicite ; ne pas détournerR0. Seulement en cas de gain homogène, réserver des groupes réellement frais avant leur inspection. Aucun défaut scientifique activé, aucun commit/push/publication.
