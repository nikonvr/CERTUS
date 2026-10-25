# Relais ChatGPT → Claude — 2026-10-22

Branche `chatgpt/2026-10-22` ; base Gemini relue `e774a120` ; code A4 et tête avant ce relais : `b399b842`.
Six bancs A4 terminés. Travail local, aucune poussée ni fusion. A8b différé à la demande de 👤.

## Mission prioritaire : refaire l'analyse

**Demande explicite de 👤 : refaire l'analyse des résultats Gemini et GPT à partir des artefacts bruts, avec des conclusions indépendantes.**
Recalculer les synthèses, vérifier configuration/provenance/plans comparés, puis distinguer résultats confirmés, résultats à confirmer et échecs.

1. **Gemini :** [A14, six cas](STRAT_etage_A14_2026-10-21/bilan.md) et [A10, quatre cas](STRAT_etage_A10_2026-10-21/bilan.md).
   Partir de leurs `cas.json` et artefacts ; examiner SEEL et arrêts aux deux corridors, les gains du 75c,
   le cas contradictoire `r75x2_s101` et les refus `35c_s42` / `r75x2_s202`.
   Vérifier les critères écrits : aucun SEEL dégradé, aucun arrêt ajouté, gain sur la majorité des designs, tenue à ±0,010.
   Expliquer les statuts accepté/repli/refusé et leur rapport à ces critères ; proposer la décision physique.
2. **Relecture GPT :** [bilan et preuves](RELECTURE_gemini_2026-10-22/bilan.md).
   Dix configurations contrôlées ; huit jugements de plans figés reproduits (`RELECTURE=GO`), avec tableaux par tirage.
   Les populations de recherche n'ont pas été régénérées ; les deux refus n'ont pas de jugement indépendant.
3. **A4 GPT :** [bilan v2, six résultats](STRAT_A4_parents_optiques_2026-10-22/bilan.md), protocole, `cas.json` et `artefacts/`.
   Recalculer SEEL global, SEEL optique pur et nombre de déposables optiques purs ; comparer chaque M à son M0.
   Le quota actif est tracé dans `cas.json`. Une graine par composant, étage `strat_local_search=true` :
   ces minima de recherche ne sont pas directement comparables aux jugements Gemini sur graines neuves.
   Proposer une confirmation indépendante si nécessaire ; le levier reste à 0 par défaut.

## Code et validation

A4 réserve les parents sans Rate avant le filtre des scores finis et les fournit à ELITE ; les filtres natifs
des résultats restent en place. La tentative initiale cherchait les parents après ce filtre : M2 interrompu,
données conservées dans `tentative_01/`, à ne pas mélanger avec la table v2.

**Validation complète en série : GO (0 failed), C1 : TENU**, preuves et empreintes dans
[controle_v2.md](STRAT_A4_parents_optiques_2026-10-22/controle_v2.md). Le code est inchangé depuis.
`validate_parallel.py --only docs` final : **GO**. Le passage complet n'est pas répété : la référence du code v2 reste l'ensemble des huit commandes de CLAUDE.md exécutées en série.
Selon l'accord de 👤, pas de répétition complète ni d'archivage supplémentaire ; journaux natifs conservés localement dans le worktree. Les JSON A4 à la racine de `reports/` sont des sorties locales dupliquées ; utiliser les artefacts du bilan v2.
Les erreurs de nettoyage Drive signalées par Gemini surviennent après sauvegarde ; les fichiers utiles ont été contrôlés.

Après l'analyse, proposer confirmations/corrections et fusion à 👤. A8b n'est pas entamé (§4 et action A8b de `docs/ETAT_actions.md`,
un commit par arête, dette réelle seulement). A9 reste conditionné au `GO_OWNER.txt` écrit par 👤, absent au dernier contrôle.

## Première reprise (PowerShell)

```powershell
Set-Location -LiteralPath (Join-Path $env:USERPROFILE '.codex\worktrees\certus-chatgpt-2026-10-22\certus0310')
python scripts\preflight.py
python scripts\orient.py
```

Puis `CLAUDE.md`, `docs/ETAT.md` §0 et ce relais ; vérifier avant de poursuivre.
