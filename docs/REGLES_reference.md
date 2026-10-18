# CERTUS — référence : pièges d'exécution, gel, vocabulaire, documentation, revue d'un agent

> Extrait de [`CLAUDE.md`](../CLAUDE.md) le 2026-10-18 (convention de `scripts/extraire_section.py`). Ce contenu **fait autorité** ; `CLAUDE.md`
> n'en garde qu'un renvoi par section, sous le même numéro. **Un fait, un seul endroit** : corrige ici, ne recopie pas ailleurs, mets un lien.
> Les `§N` nus qui renvoient aux règles qui annulent un travail sont écrits `CLAUDE.md §N`. À lire en touchant le sujet, pas à chaque session.

## 6. Pièges d'exécution

- `params` peut être un DTO Pydantic : `get` et `[]` marchent,
  `setdefault` non. Un import de paquet exécute `__init__.py` ;
  depuis `certus/physics`, importer `certus_physics.X` peut créer un cycle.
- **Numba** met en cache le code machine de l'appelant, y compris un appelé
  d'un autre fichier et les tableaux de module. `numba_cache_key` dans
  `certus/core/certus_core.py` clé le cache par les sources ; les modules
  qui donnent une constante ou une façade aux noyaux doivent mentionner
  numba dans leur texte. Garde :
  `tests/unit/test_the_cache_key_covers_what_the_kernels_read.py`.
- Les tests partagent des caches de classe : les restaurer par fixture.
  Un test Qt prend la fixture `qapp`, jamais une `QApplication` locale.
  `tests/headless/test_design.py` et `test_strat.py` simulent le calcul :
  pour une mesure réelle, utiliser `scripts/bench_examples.py`.
- La Phase A se lit dans `reports/STRAT_observability_*.json`.
  Dans INDEX SPLINE, `d_lo`/`d_hi` désignent nominale/tolérance au widget,
  mais des bornes dans `SplineOptConfig` : vérifier le dialogue Smart Init.
- Un export passe par `atomic_open` (`certus/utils/certus_atomic_io.py`).
  Un `except` large journalise l'exception ou se restreint aux erreurs
  attendues ; les tests `test_exports_are_written_atomically.py` et
  `test_no_broad_exception_is_swallowed_in_silence.py` gardent ces règles.
- **Qt/thème** : toujours `apply_certus_theme()` et les jetons `CertusTheme`, jamais un
  hexadécimal. Une feuille locale de `create_styled_button` prime sur celle de
  l'application. L'encre d'un bouton plein est `CertusTheme.label_on`, une transparence
  `CertusTheme.tint(couleur, 0.18)`, jamais une concaténation ; `refresh_widget_sheets()` actualise les feuilles
  au changement de thème. Vérifier les pixels, pas la feuille déclarée (`scripts/audit_ux_certus.py`).
- Le premier calcul compile Numba : chauffer avant un chronométrage.
  Ne pas citer dans le code le motif littéral qu'un garde-fou cherche
  (couleur, règle QSS), au risque de déclencher le garde-fou lui-même.

## 8. Architecture — le gel et les points d'entrée (suite de la section 8 de CLAUDE.md)

- Le gel (`certus_hub.spec`) est **un** exécutable : `CERTUS_HUB.exe` lance le hub, et
  `CERTUS_HUB.exe --run-module NOM [fichier]` un module. Son point d'entrée est `tools/frozen_entry.py`,
  **jamais** un fichier de `certus/core/` : PyInstaller cherche d'abord dans le dossier de son script
  d'entrée, qui masquerait `certus_substrate_index.py`. Un script de `scripts/` importé au démarrage doit
  être dans les `datas` du spec, avec ce qu'il importe (`test_the_frozen_spec_bundles_the_suite` le suit).
- `certus_curve_smoother.py` et `certus_substrate_index.py`, à la racine, sont des points d'entrée
  que le hub lance ; le second recopie aussi les globales de `certus.core.certus_substrate_index`.

## 9. Vocabulaire

| terme | sens |
|---|---|
| juge de paix | le dichroïque 48 couches, `example/example_strat/JSON-strat-example.json` — un repère, pas le seul composant |
| λ de contrôle, bloc | la longueur d'onde surveillée ; un bloc = des couches consécutives à la même λ |
| POEM | arrêt à un pourcentage de l'amplitude entre les deux derniers points tournants |
| plantage, rendement | un dépôt qui ne se termine pas ; la part de ceux qui se terminent (objectif 95 %) |
| Phase A, Phase B | choix d'une λ par couche ; regroupement en blocs et test Monte-Carlo |
| SEEL | erreur d'épaisseur équivalente par couche, en nm — **la** grandeur qu'on rapporte, jamais le RMSE seul |

## 10. Tenir la documentation

- **Un fait, un seul endroit** : état dans `docs/ETAT.md`, règle ici.
- **Cite une fonction, jamais un numéro de ligne** : les lignes bougent.
- Pas de récit dans les documents vivants (« cette ligne disait… ») : `git log` le garde.
- Les trois contrôles documentaires de CLAUDE.md §2 ne lisent pas les phrases : « 0 point à instruire » ne
  veut pas dire « tout est cohérent ».
- `pages/*.html` sont des rapports scientifiques **en anglais**, fidèles à ce que le code fait, sans
  affirmation non étayée : chaque page doit répondre « oui » à *décrit-elle exactement ce que fait le
  code, sans enjolivement ?*
- La vitrine `pages/CERTUS_STRAT.html` a un régime strict : tout nombre sourçable dans le code
  ou dans `reports/`, la limite montrée, la structure revérifiée (`python scripts\verifier_html.py pages\CERTUS_STRAT.html`).

## 12. Vérifier le travail d'un autre agent

Un rapport est une déclaration, pas une preuve : essaie de la **casser**. Trois questions, dans
l'ordre : le diff correspond-il à la déclaration ? la mesure se reproduit-elle ? la conclusion
suit-elle de la mesure ? Puis cinq contrôles : le nouveau paramètre est-il inerte au bit ? les
tests ajoutés échouent-ils sur le code d'avant ? les grandeurs de bruit suivent-elles le bruit ?
chaque filtre rejette-t-il réellement quelque chose (**compte les rejets**) ? les conclusions
dépassent-elles les mesures ? Le repère d'origine est l'étiquette `depart-gemini` : ne la
déplace pas.
