# Chantiers restants — 19 novembre 2026

Chantiers ouverts uniquement (les clos sortent de la page ; bilans dans `reports/`). Dépendances priment sur l'ordre ; profilage avant modif de gradients ; premier pas d'une session, mesurable, avec critère d'arrêt.

- **Décisions 👤 (15/11)** : graphes inchangés ; modèle de dépôt = `example/example_strat/JSON-strat-example.json` (31, 32) ; 41 trié en local par 👤 (rien sur GitHub).
- **Décisions 👤 (17/11)** ([audit](../reports/audit_chantiers_2026-11-17_soir/bilan.md)) : 31 et 32 jugés sur [bilan 49](../reports/chantier49_2026-11-18/bilan.md) ; 05, 21, 41 indépendants ; 31 en session dédiée ; 33 bloqué (essais humains).

| Ordre | Priorité | Complexité | Chantier | État / Premier pas | Fin ou arrêt | Src |
|---:|---|---|---|---|---|---|
| 31 | P2 | Très forte | Co-conception B : épaisseurs et plan ensemble | [Bilan 49](../reports/chantier49_2026-11-18/bilan.md) : biais par couche = 6,9 % (nominal) / 2,6 % (robuste) de l'erreur². `native_evaluator` fige les épaisseurs nominales : chaque pas reconstruit l'évaluateur. Inactif par défaut (C1). | Archivé si 49 sans marge ; sinon gain sur 3 graines sans arrêt ajouté. | A §1.4 |
| 32 | P3 | Moyenne | Co-conception C : contrôlabilité dans DESIGN | [Bilan 49](../reports/chantier49_2026-11-18/bilan.md) : seulement 2 plans, insuffisant pour corréler marges/dynamiques au SEEL. | Archivé si corrélation faible ; sinon critère proposé à 👤. | A §1.4 |
| 05 | P3 | Moyenne | Ajustement Sellmeier SUBSTRATE (D6) | Tester `sellmeier_ir_pole` sur indice mesuré ([bilan](../reports/chantier05_2026-11-18/bilan.md)), puis Jacobien analytique de la variante standard. | Jacobien gardé s'il accélère. | A §4 |
| 41 | P3 | Faible (👤) | PR Dependabot | Cinq PR CI (#10–#14 : `codeql-action`, `upload-artifact`, `setup-uv`). | 👤 fusionne ou ferme. | G §2.8 |
| 21 | P3 | Forte | Dérivées SPLINE (D4/D5) | Profil puis dérivées des nœuds libres et du Smart Init ([bilan](../reports/chantier21_2026-11-19/bilan.md)). | Vérifier cas limites + replis ; garder si plus rapide. | A §4 |
| 33 | P1 | Validation humaine | U13 : écran réel, Narrateur, 5 utilisateurs | Partie machine prête (`U13_protocole.md`). | Bloqué : date, testeurs, matériel. | U13 |

## Sources

- **A** : [audit 13/11](../reports/audits_2026-11-13/bilan.md) · **U13** : [protocole](../reports/refactor_corridors_2026-11-11/U13_protocole.md) · **G** : [audit général 14/11](../reports/audit_general_2026-11-14/bilan.md).
- Chantier 26 gelé tant que les écarts/plantages du cache Numba restent ouverts.
