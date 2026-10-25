# Tentative 01 — arrêt technique, 2026-10-22

Code `38acac0d` (implémentation A4 `192f8576`). M=0 terminé : 2 653 plans retournés, aucun optique pur,
meilleur SEEL global 0,15312639083714288 nm. Artefact et résumé complets conservés ici.

M=2 interrompu par l'agent avant son artefact final : les premières passes annonçaient `available=0`.
Diagnostic du code : `_execute_robustness_tasks` retire les scores non finis avant le classement et ELITE.
La première sélection A4 ajoutait en outre les restrictions score fini/non éliminé, absentes de la demande.
Cette version ne garantit donc pas l'accès aux parents optiques évalués et rejetés avant ELITE.

Correction : réserver ce pool avant le filtre, le transmettre au contexte d'ELITE et compléter le quota avec lui.
Les enfants et la sortie gardent leurs portes de validité. Tests de raccordement ajoutés avant correction :
`3 failed, 8 passed` (`../tests_avant_v2.log`). Le protocole v2 est fixé avant ses six nouveaux bancs.

`campagne.py.txt` et `protocole.md` sont les copies de la tentative initiale ; le lanceur courant est dans le dossier parent.
