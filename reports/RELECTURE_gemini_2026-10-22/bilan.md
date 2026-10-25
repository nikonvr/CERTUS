# Relecture du relais Gemini A14/A10 — 2026-10-22

Départ : `e774a120`, branche `gemini/2026-10-21`. Les six cas A14 et quatre cas A10 sont présents.
`relecture.py.txt` contrôle les dix artefacts : étage actif, recherche de fente attendue, composant/mode/graine,
provenance propre et sources scientifiques inchangées entre leurs commits et le départ de la relecture.

Les huit jugements existants ont été rejoués : deux corridors, trois graines, 1 000 tirages par graine,
mêmes plans et mêmes tirages que le lanceur original. Les nombres d'arrêts sont identiques. Écart maximal de SEEL :
`2,3203661214665772e-14 nm` ; tolérances fixées avant rejeu : relative `1e-10`, absolue `1e-12`.
Les deux cas où l'étage était refusé (`35c_s42`, `r75x2_s202`) n'ont pas de jugement indépendant à reproduire.
`RELECTURE=GO` porte sur les plans figés ; les populations de recherche n'ont pas été régénérées.

Point à transmettre à Claude : A10 `r75x2_s101` reproduit un SEEL ±0,005 de 0,5383 → 0,5959 nm,
et des arrêts ±0,010 de 0 → 2. Le signe du gain moyen RMSE² ne suffit donc pas à cocher les critères SEEL/arrêts.
L'interprétation physique reste à faire ; aucun défaut n'est changé par cette relecture.

Validation de départ (`validation_avant/`) : 8 427 réussis, 19 ignorés, 3 échecs attendus, aucun échec inattendu.
`VALIDATION=NO-GO` documentaire : cinq chemins distincts signalés, dont le lanceur `.py.txt` tronqué en `.py`.
Le correctif local `d0d0acf1` reconnaît le suffixe complet et marque explicitement six citations de commandes scratch
obsolètes dans quatre rapports anciens. Les scripts scientifiques archivés restent inchangés.
Lint et trois contrôles documentaires rejoués séparément passent après correction ; le lint intermédiaire avait
rejeté les copies exécutables du scanner, désormais archivées en `.py.txt` sans modification de leur contenu.

Preuves : `controle.json`, sous-dossiers `A14/` et `A10/` (tâches, résultats et tableaux par tirage),
`relecture.log` et journaux de validation. Les chemins locaux sont neutralisés dans les copies des journaux.
