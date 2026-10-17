# R6/77 — finalistes figés et confirmation fraîche v2

Les deux natifs sont terminés avec sortie0 : contrôle35160 à00h30Paris, variante12900 à01h15Paris,
coordinateur55048 clos. pair_audit.json vérifie sources/copies/paramètres, tâches physiques, profondeurs
et quotas du raffinement. Résultat de recherche : meilleur consensus contrôle0,04213534390413829,
SEEL0,4105379100845051nm ; variante0,04095516271849109,SEEL0,4047476385032584nm, gain environ1,41%.
Ce résultat seul ne confirme pas un gain indépendant.

Six plans ont été figés avant tout nouveau groupe : trois ancres historiques de notation, le meilleur
consensus complet du contrôle98610004, son export officiel98610005, et le gagnant complet/officiel
de variante98610006. Blocs, Rate, fente2, témoins et facteur de bruit éventuel sont conservés ; aucune
nouvelle proposition ni injection dans la recherche. Les anciennes attentes numériques des ancres
ont été retirées : elles concernaient101/41/42/43 et ne valent pas pour des graines fraîches.

La première vérification bloque avant toute mesure : le protocole prédisait un hashLF alors que
write_text avait écritCRLF. Le manifeste et le fichier réel étaient cohérents. Aucun claim frais pris.
confirmation_protocol.json, fresh/group_XX et fresh_verification_01FAILED restent intacts.
preparation_failure_01 conserve le diagnostic et les sources exécutées. Les copies v2 ont des noms
distincts, confirmation_protocol_v2.json et fresh_v2/group_XX, avec les mêmes octets de plans et les
mêmes36graines réservées avant les recherches. Les phases de quota ne sont pas augmentées.

Copies courantes : rate_R6_fresh_scorer_v2.py, rate_R6_fresh_guard_v2.py, run_rate_R6_fresh_v2.ps1.
Le replayer utilise l’APIproductionrefine=False,expand_variants=False et le transportfloat32 validé ;
les callbacks physique et observateur sont identiques à l’AST deR5points. fresh_verification_02GO :
dix contrôles, dont graines réellement réservées, métadonnées incomplètes conservées, profondeur
insuffisante/appel manquant refusés, groupe2 prématuré et délai refusés, aucune évaluation physique.
Les quatre fonctions PowerShell sont exactement celles deR6natif, vérifiées sous5.1.26100.9549.

Le coordinateur v2 enchaîne seulement les trois groupes17610001..04,17610011..14,17610021..24,
six plans au plus,300tirages par appel base/consensus. Chaque groupe possède un nouveau claim permanent
R6_c01_s77_fresh_gXX ; rien ne doit être relancé silencieusement. Refus en cas de concurrence, source,
plan, graine, quota ou heure modifiés. Python24,affinité0xffffff,Normal,bibliothèques≤23. Limite16octobre06:00UTC.
Laisser finir l’enfant engagé ; aucune analysePython ni test pendant ses mesures.

Après trois groupes : audit de provenance et des appels réels puis moyenne/médiane/victoires/pireperte,
contre le contrôle complet propre et son export officiel. Critère fixé avant inspection :3/3favorables
et médiane≥1% pour un cas clairement favorable. Un petit résultat ou une hétérogénéité reste une limite,
aucun groupe ajouté automatiquement. Les sources de production sont toujours celles deR5validé ;
aucun défaut activé, commit, push ou publication.
