# Rate : échec strict de la comparaison d’ablation (2026-10-13)

Contrôle de quatre plans à 22 h 32 : verdict **FAILED_REPLAY**, un seul écart, sur le vainqueur sans voisins conjoints.
Son score de base 101 reproduit exactement 0,03339661422533983 ; sa notation avec les trois consensus complets est
0,03517507293183044. Les trois autres plans (référence, local, natif conjoint) reproduisent leurs scores.
La tolérance reste inchangée ; aucun artefact, score original ou journal n’est remplacé.

Le score de batch et le score par consensus ne doivent pas servir ensemble à attribuer le supplément apparent de 1,49 %.
La comparaison doit renoter le pool sauvegardé de l’ablation à profondeur homogène, puis valider son meilleur plan séparément.
Preuves : `control.json`, `diagnosis.json`, plans, sources et protocole conservés. Aucun défaut de production activé, aucun commit.
