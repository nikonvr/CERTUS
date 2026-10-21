# A3 — Reprise des repères après correction de transmission

Code avant protocole : `cd481836`. Le pilote consigne la tête après protocole dans les états vivants.
L'[essai initial échoué et son diagnostic](../STRAT_A3_reperes_2026-10-21/bilan.md) restent conservés.
Aucun de ses scores intermédiaires n'est repris comme résultat valide.

## Mesures réservées avant lancement

Six bancs officiels, dans cet ordre : 48 couches premium ; random75 livré fast ; vrai 35 couches deep ;
fichier 3 cavités deep livré à 36 couches ; r75x2 natif à 1 nm ; r75x2 à 2 nm avec ses rampes livrées.
Graine 42, paramètres physiques livrés, aucun exemple modifié.
Le profil à 35 couches est dérivé du fichier de 35 couches avec le seul changement de mode vers deep.
[Protocole des bancs](protocole.json), [profils réellement collectés](params_effectifs.json),
[sources SHA-256](sources_sha256.json), [pilote](run_A3_official_benches.py.txt).

Après la sortie réelle des six bancs réussis, le [pilote d'intervalles](run_A3_retained_intervals.py.txt)
rejoue la partition historique figée du 99 couches : [0,22), [22,42), [42,76), [76,99).
[Protocole d'intervalles](intervalles_protocole.json) : graines de robustesse 42, 101 et 202 réservées
avant observation ; mode fast, fente 2 nm, recherche de fente désactivée, autres défauts courants.
Ce sont trois recherches de la même partition, pas une confirmation indépendante des mêmes plans figés.
La partition elle-même n'est pas réoptimisée.

Chaque intervalle appelle la méthode existante `campagne_intervalles.mesurer`, avec un dossier neuf par tentative.
Une enveloppe de diagnostic capture les paramètres après surcharge avant leur passage au workflow, et ne modifie pas leur valeur.
Elle contrôle le nombre de couches, le mode, la graine, l'offset physique du bruit, le total 99,
la fente, le corridor, la recherche locale et le plancher d'hystérésis.
Les quatre tranches partagent la même graine et conservent leurs offsets, conformément à C2.
Les paramètres réellement collectés, plans et scores retournés, verdicts négatifs, épaisseurs simulées et journaux restent conservés.

Pour chaque graine dont les quatre intervalles sont déposables, leurs fichiers sont copiés dans un cache neuf d'assemblage.
`classer_partitions.main` assemble les mêmes tirages, sans tirage neuf ni formule TMM ajoutée.
Il note le spectre des 99 couches et refuse une partition dont les tirages plantés cumulés dépassent son seuil.
Le SEEL assemblé imprimé est celui du P95, arrondi à 0,001 nm ; ce n'est pas la moyenne des SEEL des intervalles.
Le score de consensus d'un banc officiel et ce P95 assemblé ne sont pas des comparaisons appariées.

## Exécution et reprise

La [chaîne PowerShell](run_suite.ps1) attend la sortie du pilote officiel avant tout intervalle,
et n'engage aucun nouveau calcul après le 21 octobre 2026 à 10 h Europe/Paris.
Le pilote d'intervalles contrôle lui-même l'échéance avant chaque lancement : l'option historique `--limite` n'est pas utilisée.
Une mesure engagée peut finir après l'échéance. Aucun ancien cache n'est écrasé ou considéré comme une mesure courante.

Depuis la racine de l'arbre, après commit du protocole et contrôle d'absence d'autre mesure :

```text
powershell -NoProfile -ExecutionPolicy Bypass -File reports/STRAT_A3_reperes_reprise_2026-10-21/run_suite.ps1
```

États vivants : `etat.json` pour les bancs, `intervalles_etat.json` pour les intervalles ; journaux par tentative.
La tête et les fichiers suivis restent fixes pendant toute la chaîne. Toute reprise commence par l'examen des processus.
Un `RESULT=None`, un timeout, une exception ou un classement de repli ne fournissent aucun repère valide.
Un intervalle réellement sans plan déposable est conservé comme constat négatif, avec SEEL absent ; les autres graines restent autorisées.

## Résultats

Les six bancs ont terminé avec un résultat valide au code `85a9e82f`, graine 42. Empreintes des sorties vérifiées ;
les reçus `revue_*_a01.json` conservent ces vérifications. [Conditions et limites de l'export](conditions_et_limites.md).

| profil | RESULT officiel | SEEL (nm) | population retournée | durée du processus (s) |
|---|---:|---:|---:|---:|
| 48 premium | 0.007402488118579864 | 0.17207542670096582 | 2652 | 1035.64 |
| 75 fast livré | 0.012373053745766442 | 0.2224684584004343 | 2634 | 1787.58 |
| vrai 35 deep | 0.06020241915781839 | 0.4907236255075494 | 1245 | 500.18 |
| 36 deep livré | 0.026218616702447725 | 0.32384327507266675 | 1440 | 569.29 |
| r75x2 natif 1 nm deep | 0.085061538305979 | 0.5833062259430427 | 3946 | 3759.02 |
| r75x2 rampes 2 nm deep | 0.06481287745259888 | 0.5091674673527321 | 4691 | 3670.23 |

Les dix rangs sont présents, sans repli final. Les populations retournées ne prouvent pas un nombre de plans
déposables ou optiques purs. Les listes de longueurs d'onde du banc ne portent pas les frontières complètes.
Aucune comparaison statistique ni confirmation indépendante n'est revendiquée.

Les quatre intervalles 42 ont terminé, puis l'assemblage a échoué avant calcul sur la capture de console.
La chaîne s'est arrêtée, sans lancer les graines 101/202. [Archive partielle des 74 preuves](preuves_A3_partielles_20261021T040040Z.zip),
SHA-256 `cd86605215ff0921e3c700b61a38c75cdd34c88dd3a1799cf26f0a1b09c9bbbe` : six bancs, intervalles,
épaisseurs, paramètres, état et échec réel conservés, chemins normalisés et empreintes originales incluses.
Les données binaires des épaisseurs sont identiques.

[Reprise corrigée de l'assemblage](../STRAT_A3_intervalles_reprise_2026-10-21/bilan.md), sans recalculer les quatre intervalles 42.
A3 reste ouverte jusqu'au bilan du 99 couches et à l'actualisation d'ETAT §2.
