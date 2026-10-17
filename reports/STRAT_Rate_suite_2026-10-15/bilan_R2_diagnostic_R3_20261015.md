# R2 — audit et choix du premier facteur R3, 15 octobre2026

R2 est **terminé à10 h13 Paris**, après **2879,26s (47min59s)** exports inclus. Le processus scientifique est terminé ; ses verrous sont libérés, ses réservations conservées. [État](R2_native_base/etat.json), [auditGO](R2_audit_20261015.json), [diagnostic des transitions](R2_transition_diagnostic_20261015.json). Sources et scripts exacts, copie native/root et empreintes des trois exports contrôlés. Le champ embarqué `running` dans la provenance est une photographie prise avant finalisation ; l’état final du contrôleur fait foi.

## Résultat natif et portée

5353 stratégies sauvegardées ;1076 lignes portent un consensus complet41/42/43. Le meilleur ID901054165 retrouve **score0,032410960467156955**, soit **SEEL0,3600608863nm** dans la convention des campagnes (2×racine du score). C’est le plan natif historique déjà connu, pas un nouveau gain. Référence fixe0,3967147882nm ; meilleur plan local0,3345159946nm. Les métadonnées et appels réels sont conservés ; aucune comparaison de scores bruts et consensus n’est utilisée pour choisir un vainqueur de variante.

## Diagnostic observé

-124 générations,77473 propositions totales dont38580 conjointes ;106506 appels physiques enregistrés et1722 réutilisations de consensus. La grille reçue est toujours450..750nm au pas1nm :613 et688 sont légales.
-Une fenêtre optique interne[34,37) apparaît dans740 propositions, dont348 conjointes. **Dans ces348, sa géométrie est toujours héritée ; aucune de ces propositions conjointes ne change directement cette fenêtre ou sa λ.** Elles portent691nm (318) ou690nm (30), jamais688. Ne pas confondre présence d’une fenêtre héritée et capacité à la reconstruire dans le voisinage conjoint.
-Le préfixe[0,5) apparaît dans3781 propositions, dont1113 conjointes ;80 le créent indirectement,1033 l’héritent. Aucun n’associe ce préfixe à613nm. Son traitement constitue un levier distinct ; il n’est pas ajouté au premier essai.
-Les parents mêlent492 lignes avec consensus complet et612 autres ; parmi ces dernières448 sont dans des scopes pleins300 et164 dans des scopes50. Ce mélange est observé, mais sa causalité sur le gain n’est pas démontrée. La simple inversion des deux ancres en R0 ne suffit pas à l’établir.
-Les appels réels comprennent50/64/25/80/150/300tirages selon l’étape ; la profondeur déclarée300/50/100/300 ne décrit pas seule le screening ELITE. Les trois graines de consensus ont chacune924 appels réels à300tirages. `n_samples=3` compte des scores, pas des tirages.

## Première expérience R3

[Protocole courant figé](R3_h01_widths/protocol_v3.json) : **largeurs conjointes2/4/6 contre1..7** ; déplacements±2, flux de λ, ordres des familles, budgets480conjoints/240Rate, six tours, plafonds plein36, physique, bruits, fente et graines inchangés. Les largeurs impaires permettent la reconstruction conjointe de trois couches ; cet essai n’ajoute pas688/613 à un flux qui ne les propose pas encore. Une interaction géométrie/λ peut donc rester à traiter ensuite, un facteur à la fois.

Les copies conservent exactement le chemin de contrôle : candidats, ordre, IDs, curseur et événements. Vérification des deux voies et de l’observateurGO, ainsi que d’un exemple générique18couches, contrats réels, grille, déterminisme et héritage fente/témoins :[preuve](R3_h01_widths/verification_02/verification.json). [Gardes/quotaGO](R3_h01_widths/guard_verification/verification.json), [revue manuelle](R3_h01_widths/manual_review_before_launch.json). Aucun fichier scientifique historique ou du contexte de mesure n’est modifié.

Une paire native contrôle/variante constitue le premier des trois essaisR3 autorisés. Les deux interpréteurs déclarentCPU24 dès leur démarrage ; affinité0xffffff, prioritéNormal, bibliothèques≤23. La durée de R2, dont la déclarationCPU interne arrivait plus tard, n’est pas une mesure d’accélération de code. Après la paire, figer et renoter les finalistes à profondeur homogène avec9900001/9900006/9900008 et la référence. Réserver des groupes réellement frais avant leur notation uniquement si un gain de recherche justifie cette confirmation.

Préparations rejetées conservées : comparaison initiale de lignes complètes contre snapshots partiels dans l’audit, diagnosticsRuff, et garde trop large incluant le service IDE. Ces échecs de préparation ne consomment aucune mesure et ne sont pas des échecs scientifiques. `protocol.json` et `protocol_v2.json` restent des préparations non mesurées ; seulev3 est utilisée. Le script exact de l’audit réussi est sauvegardé dans `R2_audit_executed.py.txt` ; les assertions sont ensuite séparées pourRuff, sans refaire de mesure.

La suite reste bornée :R3trois paires, R4deux passes/faisceau4/1200nouveaux plans, R5validation, R6six paires conditionnelles. Aucun défaut nouveau activé, aucun commit/push/publication. R7 attend les données machine quantitatives.
