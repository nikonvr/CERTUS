# R4 — spécification de préparation,15 octobre2026

**R4 terminé/auditéGO ; trois groupes frais terminés/auditésGO.** Lire bilan_R4_recherche_20261015.md et confirmation_01/bilan_confirmation_20261015.md. Les paragraphes de lancement ci-dessous décrivent le protocole déjà exécuté, à ne pas relancer. Groupe001 terminéOK, trois ancres reproduites et neuf propositions non finies rejetées ; le coordinateur43244 enchaîne les groupes, un seul enfant scientifique. `preparation.json` porte les limites. Générateur vérifié :839 contrats réels/synthétiques, sans simulation, dans `generator_verification_02/verification.json`. Replayer, garde, planificateur et fonctions du coordinateur vérifiésGO :26 contrôles et six refus d’isolation. Lire launch_review_20261015.md, ETAT§0, controller.json/checkpoint.json et les processus avant reprise. Les sources des mesures engagées restent figées.

## Objectif et séparation des preuves

H02 ne gagne pas. La reconstruction des étapes prouve une éviction de rang au premier halving pour deux plans admissibles au seuil, avant la notation complète. R4 teste donc le raffinement après recherche, avec notation homogène et génération bornée. Il ne promeut ni les largeurs seules ni le voisinage de λh02.

Deux branches partagent les mêmes règles et le plafond global, leurs parents restent séparés : locale depuis9900006/9900008 ; native depuis901054165/900754638, les deux finalistes natifs deh02. Les trois comparateurs de notation sont900951015/9900006/9900008, reproduits dans le rejeuh02 ; ils ne sont pas injectés comme parents de la branche native. Un résultat local n’est pas une preuve de découverte native. Une amélioration native peut rester moins bonne que le meilleur local ; les deux écarts doivent être rapportés.

## Bornes et étapes

Deux passes au total : fenêtre interne la plus profonde puis préfixe. Chaque passe comprend un voisinage grossier puis fin pour chaque branche encore active. Une branche sans gain à la fin de sa passe complète s’arrête ; l’absence de gain du seul grossier ne supprime pas prématurément le fin. Faisceau global de quatre, au plus deux plans par branche. Au plus300 nouvelles propositions par branche et par passe,1200 au total ; aucun transfert automatique d’un reliquat. Les contrats rejetés nouveaux comptent conservativement dans le budget ; doublons et propositions inchangées sont enregistrés séparément.

Grossier interne : λ grossières légales espacées d’au moins10nm à géométrie parent, puis déplacements−2..+2 et longueurs1..7 à λ parent. Grossier préfixe : grille grossière légale à géométrie parent, puis longueurs2..fin du premier bloc à λ parent. L’ordre réel est déterministe, les propositions de parents distincts s’entrelacent, et sera figé avant scores. La grille vient d’une trace native effective du même composant ; aucun688/613 ni indice34 propre au cas dans le générateur.

Après le grossier, retenir jusqu’à deux centres par branche parmi propositions éligibles et parents initiaux : score de consensus300/41/42/43 croissant, premier meilleur, puis meilleur masqueRate distinct si possible, puis λ distincte, puis signature canonique stable. Les décisions utilisent la même formule mean_std et le poids0,35 ; conserver aussi la base101 et les appels réels. Le fin varie position±1, longueur±1 et λ parent+0/−1/+1/−2/+2/−3/+3 lorsqu’elles sont légales ; pour le préfixe, départ0 et longueur≥2. Les limites exactes de longueur interne doivent être fixées avant mesure ; retenir1..7 pour éviter une expansion implicite.

Le générateur conserve les partitions, la fente, les témoins et toutes les autres fenêtres. Il refuse explicitement le cas où la fenêtre sélectionnée traverse plusieurs blocs ou où modifier la λ de son bloc changerait une autre fenêtre optique : ce prototype n’invente pas de reconstruction plus large. Les quatre parents actuels doivent passer ce contrat. Les cas non applicables sont conservés et expliqués. Leurs limites feront partie du bilan de généralisation.

Dédupliquer avec blocs/Rate/fente/témoins, en ignorant seulement la λ d’un bloc entièrementRate, comme le demande le guide. Ne pas confondre cette équivalence avec une liberté de supprimer les partitions, les témoins ou les autres métadonnées. Les provenances des doublons restent sauvées, sans compter une nouvelle stratégie ni une accélération du code.

## Notation et artefacts

Chaque groupe : trois comparateurs stricts et au plus neuf propositions, donc≤12 plans ; base101 à300tirages et consensus41/42/43 à300 par graine. Reprendre exactement les callbacks `check_sources`, `record_task`, `keep_fixed_plans`, `evaluate_fixed` et le transport SharedIndicesManager/Workerfloat32 validés par R0/h01/h02. Aucun ELITE, aucune expansion Rate/fente pendant ce rejeu. Les candidats non finis ou à consensus incomplet restent rejetés et sauvegardés ; aucune note de base rebaptisée consensus. Les ancres restent strictes àrel1e-7/abs1e-10.

Créer des copies nouvelles du replayer, de la garde et du contrôleur, pas une réutilisation des slotsR0/h01/h02 consommés. La gardeR4 vérifie autorisation originale et fenêtre actuelle, sources/HEAD, hash de protocole et scripts, étatA2 complet, validationsGO, bornes/provenances de plans, quota restant, groupe non consommé et absence de concurrence. Réserver atomiquement avant chaque groupe ; conserver la réservation après échec. Le contrôleur vérifie aussi la date juste avant chaque lancement. Une seule mesure,CPU24 dès démarrage, affinité0xffffff,Normal,bibliothèques≤23.

Un coordinateurPowerShell peut appeler un planificateurPython après chaque fin de groupe ; le planificateur doit se terminer avant le replayer scientifique. Cela évite d’exempter un parentPython vivant de la garde. PowerShell : Handle conservé avant WaitForExit, sauvegarde atomique avec backup explicite, SHA256.NET si nécessaire ; arguments de date passés comme chaînes ISO littérales, car ConvertFrom-Json peut les convertir enDateTime. Ne pas ouvrir de fenêtre visible.

Checkpoint atomique avec phases, branche, passe, grossier/fin, compteurs, parents de provenance, plans offerts, contrats refusés, doublons, SHA, graines, résultats et enfant courant. Un groupe préparé est immuable, chaque tentative et journal est conservé. Après crash : inspecter le vrai enfant, le laisser finir ou adopter le résultat complet après audit ; ne jamais écraser un résultat ou refaire silencieusement une réservation.

## Vérifications exécutées et restantes avant mesure

- Fixtures génériques18couches : déterminisme, parents inchangés, deux premières couches optiques, bornes de bloc, grille légale, une seule fenêtre modifiée, fente/témoins conservés, cas non applicables refusés.
- Réels quatre parents : contrats de toutes les propositions préparées, déduplication et plafonds par phase/global, aucun changement physique dans un bloc entièrementRate présenté comme nouveauté.
- Callbacks AST identiques aux replayers validés ; pipeline de score et transportfloat32 inchangés ; points fixes stricts dans le premier groupe.
- Garde : échéance avant/à/après limite, CLI trop longue ou date naïve refusée, mauvais chemin/source/compteur/groupe consommé/refus concurrent ; aucune réservation dans les tests.
- Sélection : tri stable et diversité explicite, aucun parent local ne traverse dans la branche native, aucun état courant écrasé lors de reprise. Revue manuelle et Ruff ; outils/code-review/LSP natifs seulement s’ils sont disponibles, ne pas inventer un passage.

## Confirmation et arrêt

Figer les gagnants et leurs plans complets avant de réserver trois groupes vraiment frais, seulement si un gain homogène de la branche le justifie. Au plus trois groupes supplémentaires si effet petit/hétérogène, moyenne/médiane/victoires/pire perte publiées dans le rapport local ; pas d’intervalle de confiance inventé. Les groupes202–3535 sont déjà utilisés. La branche locale doit battre le meilleur local disponible ; la branche native doit battre son contrôle et son écart au meilleur local reste explicite.

Le16 octobre2026 à06:00UTC/8hParis, aucun nouveau test ou mesure ; conserver le calcul déjà engagé, sauver l’état et donner le bilan puis mettre le suivi en pause. Même arrêt anticipé si quotas épuisés, programme fini ou absence de réparation sûre. R3 a encore une paire disponible sur trois ; ne pas inventer une quatrième. R5 intégration seulement après preuve et validation complète, aucun défaut scientifique activé. R6 au plus six paires conditionnelles dans le temps restant. R7 attend des données quantitatives machine absentes. Aucun commit/push/publication.

Vérification de génération :839 constructions ont passé les contrats et invariants, sur fixture18couches et les quatre parents réels. Le premier vérificateur supposait à tort le champtémoins toujours présent ; la correction contrôle la conservation exacte de sa présence et de sa valeur, générateur inchangé. Première tentative et source conservées dans `generator_execution_01`. Le passageGO est dans `generator_execution_02` et `generator_verification_02`. Aucune simulation physique R4, aucun quota scientifique R4 consommé.
