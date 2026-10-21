# Arrêt à la demande du propriétaire — 21 octobre 2026

À 08 h 09 Paris, le propriétaire demande l'arrêt pour éteindre le PC. Relances automatiques suspendues
(`PAUSED`), contrôleur A5 9692 et enfant 28780 arrêtés, puis absence de tout processus Python vérifiée.
La première lecture système a brièvement vu la fin de destruction des processus ; la suivante était vide.
Aucun arrêt du système d'exploitation n'a été commandé.

Le calcul à six tours n'expose pas de commande d'annulation coopérative externe. Il a été interrompu par
le système, après arrêt de son contrôleur pour empêcher tout lancement suivant. Son journal et son audit
sont conservés ; **aucun résultat final n'est revendiqué pour cet essai**. La référence complète est intacte.

## Travail conservé

Branche `codex/actions-prudentes-2026-10-20`, tête de mesure A5 `8ab08a1e` ; consulter le dernier commit
pour la sauvegarde documentaire d'arrêt. Le répertoire d'origine et ses modifications préexistantes sont préservés.
Aucun push, aucune fusion, aucune modification de la vitrine ni des défauts scientifiques.

| action | acquis et preuve | reste à faire |
|---|---|---|
| A1, A2 | déjà terminées avant cette nuit, voir la feuille de route | aucune reprise ajoutée ici |
| A6 | supprimée avec ses renvois, commit `619d84eb` | ne pas la reprendre |
| A7 | neuf propositions sourcées, commit `e369c324`, [rapport](../STRAT_vitrine_passages_a_relire_2026-10-20.md) | intégration éventuelle séparée après accord explicite ; vitrine inchangée |
| A8 simple | trois imports remontés, deux suppressions E402 retirées ; trois photos identiques, dette réduite, validation complète ; `37f27cb0` | autres modules et autres dettes ouverts |
| A3 | six bancs officiels mesurés et publiés, [table et limites](../STRAT_A3_reperes_reprise_2026-10-21/bilan.md) ; défaut réel d'émission corrigé en une ligne, `cd481836` | repère 99 couches conforme à C2 encore absent |
| A5 | référence neuve valide : SEEL `0.39671478821937545` nm, trois paquets Rate, 670 plans éligibles au consensus réservé, durée `3241.6050043` s ; [rapport](../STRAT_A5_tours_budgets_2026-10-21/bilan.md) | six tours interrompus ; dix tours et budgets 40/360 non lancés ; comparaison finale absente |
| A4 | [conception statique](../STRAT_A4_parents_optiques_2026-10-21/preparation.md), brouillon de sélection non appliqué et non testé | implémenter l'option inactive, prouver C1 au bit et le raccordement, validation complète, six mesures et rapport |
| A10 | [préparation statique](../STRAT_A10_corridors_2026-10-21/preparation.md), banques proposées avant observation | vérifier l'enveloppe expérimentale ; 36 recherches, plans figés puis confirmations indépendantes, rapport |
| A9 | [préparation statique](../STRAT_A9_natif_2026-10-21/preparation.md) ; aucune ancienne chaîne relancée | nouveau protocole borné, budgets fixés, recherche native 99 couches puis injection et raffinements, confirmations indépendantes |
| A8 structure | [diagnostic préparatoire](A8_structure_preparation.md) | reproduire D23 avant correction, puis D11/D50/D72 ; traiter les autres dettes une par une avec leurs preuves |

### A3 : limite scientifique à préserver

Les six repères officiels sont distincts du travail 99 couches. Les douze intervalles 99 couches ont été
calculés et trois assemblages ont produit des nombres, mais le contrôle C2 les a invalidés : indice de bruit
et domaines de normalisation différents entre croissance et notation. **Ne pas reprendre ces nombres ni
leur moyenne comme résultat valide.** Une correction du seul indice de bruit ne suffit pas.
Le [diagnostic C2](../STRAT_A3_C2_assemblage_2026-10-21/bilan.md), les tentatives et les archives sont conservés.
Le prototype de notation est bloqué avant tout lancement. Les incidents d'import et LLVM restent documentés.

### Validation du code

Dernière validation complète après le correctif réel : **8 425 réussis, 19 ignorés, 3 échecs attendus**,
aucun échec inattendu ; Ruff et trois contrôles documentaires passent. Détail et preuve rouge/vert dans
le [rapport du correctif](../STRAT_A3_reperes_2026-10-21/bilan.md).
Depuis, seuls documents et pilotes de campagne ont changé ; aucune suite complète répétée pour cet arrêt.
Les outils de lecture et d'archive A5 sont contrôlés séparément après sortie des processus.

## Reprendre sans perdre les acquis

1. Lire ce document, le bilan général, puis l'état et le rapport A5. Vérifier les processus et lancer
   `python scripts/preflight.py`, puis `python scripts/orient.py` depuis ce même arbre. Ne relancer aucune mesure automatiquement.
2. L'automatisation demeure suspendue : attendre une nouvelle demande du propriétaire pour reprendre.
3. Pour A5, conserver la référence à trois tours et ses empreintes. L'essai six tours est incomplet :
   reprendre avec une tentative neuve, puis dix tours, budget 40 et budget 360. Ne pas exploiter son calcul partiel comme résultat.
4. **Ne pas lancer directement l'ancien pilote avec `--resume-interrupted` après le commit d'arrêt** :
   il impose la tête `8ab08a1e` et une échéance expirant le 21 octobre à 10 h.
   Préparer un nouveau protocole/dossier avec échéance autorisée, comparer les sources scientifiques au code mesuré,
   puis référencer la baseline existante avec provenance et SHA plutôt que la refaire ou changer l'ancien état à la main.
5. Après A5 : A4, A10, A9, puis A8 structurel. Le 99 couches A3 reste ouvert et demande un protocole C2 conforme.
   Une seule mesure ou validation à la fois ; graines réservées, paramètres effectifs contrôlés, rejets conservés.
6. Les sources de `review_A5_evidence.py` et `pack_A5_evidence.py` sont archivées sous `scratch/` dans le ZIP A5.
   Restaurer leur emplacement relatif pour les employer ; ne pas relancer un outil sur une sortie existante.

Les anciens dossiers, résultats, échecs et journaux ne sont pas supprimés. Les fichiers bruts non suivis restent
dans l'arbre local ; les archives versionnées contiennent les preuves nécessaires avec chemins neutralisés et empreintes originales.

Archive A5 : [30 preuves, référence et essai interrompu](../STRAT_A5_tours_budgets_2026-10-21/preuves_A5_partielles_20261021T061232Z.zip),
SHA-256 `51c83a5b49d849b56ccb93e782a829261b8590b9df3f7a57f100b21e0b6b2348` ; intégrité et empreintes vérifiées.
Le lecteur des preuves a réussi, sans mesure nouvelle ; il identifie explicitement les quatre variantes sans résultat.

Contrôles documentaires de la sauvegarde, exécutés après arrêt des processus :
`python scripts/coherence_md.py` → `0 point(s) a instruire.` ;
`python scripts/check_claude_md.py` → `CONTRADICTIONS MECANIQUES : 0` ;
`python scripts/check_docs.py` → `DEFAUTS MECANIQUES : 0`.
Journaux conservés dans `scratch/arret_*_20261021.log`. Les Markdown nouveaux ont été ajoutés à l'index
avant ces contrôles. La condition documentaire historique des quatre scripts locaux supplémentaires
reste celle signalée dans le bilan général ; aucun nouveau contrôle n'en efface la limite.
