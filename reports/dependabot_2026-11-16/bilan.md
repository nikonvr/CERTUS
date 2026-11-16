# Alertes Dependabot sur `master` (`557925db`) — tri du 2026-11-16

Source : `gh api "repos/nikonvr/CERTUS/dependabot/alerts?state=open&per_page=100" --paginate` (44 alertes ouvertes,
n° 1 à 45 sauf 28 : 5 critical, 24 high, 14 medium, 1 low). Rien n'est monté ni modifié ici : 👤 décide. Aucune mesure
lancée ; « exposition » = chemin de code lu, pas exploit essayé.

## 1. Synthèse

| paquet | alertes | manifeste signalé | version verrouillée | tiré par | plus petite version corrigée | verdict |
|---|---|---|---|---|---|---|
| Pillow | 43 (5 crit., 24 high, 14 med.) | `uv.lock` | 12.3.0 | `matplotlib` (dépendance directe) | **13.0.0** (toutes les 43) | **exposition réelle** à l'exécution |
| setuptools | 1 (low) | `uv.lock` | 84.0.0 | `pyinstaller` (extra `freeze`) | **84.1.0** | **outils seulement** (construction de l'exécutable) |

**Par verdict : exposition réelle 43 alertes (1 paquet) · tests ou outils seulement 1 (1 paquet) · inutilisé 0.**

Dependabot liste Pillow sous deux casses (`Pillow` 31 alertes, `pillow` 12) : un seul paquet.

## 2. Manifestes

- `pyproject.toml` ne nomme ni Pillow ni setuptools ; il déclare `matplotlib>=3.10.9` (dépendance) et
  `pyinstaller>=6.10.0` (extra `freeze`). Pas de `[build-system]`.
- `uv.lock` : `pillow 12.3.0` (seul dépendant : `matplotlib 3.11.2`), `setuptools 84.0.0` (seul dépendant : `pyinstaller`).
- `requirements.lock` (`uv export --extra dev --extra freeze`) épingle **les mêmes versions** (`pillow==12.3.0`,
  `setuptools==84.0.0`) mais Dependabot ne l'a pas signalé : une montée doit régénérer les **deux** verrous.
- Environnement local (`importlib.metadata`) : pillow 12.3.0, setuptools 84.0.0, matplotlib 3.11.2.

## 3. Pillow — pourquoi « exposition réelle »

Aucun `import PIL` dans `certus/`, `certus_physics/`, `CERTUS_*.py` ni `scripts/` (fichiers suivis). Pillow est atteint
**indirectement**, par deux bibliothèques que CERTUS appelle :

1. **`openpyxl.load_workbook` sur un `.xlsx` choisi par l'utilisateur** — le chemin à surface d'attaque. Hors
   `read_only`, openpyxl ouvre chaque image incorporée par `PIL.Image.open` (`openpyxl/reader/drawings.py` →
   `drawing/image.py::_import_image`) et lit taille et format, sans décoder les pixels. Appels :
   - `certus/ui/certus_re_excel_mixin.py:937` — fichier RE ouvert par `QFileDialog` (l. 907) ;
   - `certus/ui/certus_re_excel_mixin.py:230` — classeur d'indices voisin du fichier RE ;
   - `certus/ui/certus_strat_ui_export.py:311` — relit le classeur que STRAT vient d'écrire (entrée maîtrisée).

   Un classeur piégé (image TIFF, GIF, XBM, MIC, EPS… renommée dans `xl/media/`) fait donc analyser son en-tête par
   Pillow 12.3.0. Les alertes déclenchées à l'ouverture (déni de service ou lecture hors limites à l'analyse d'en-tête)
   sont plausiblement atteignables ; celles d'écriture (TIFF/PDF/JPEG en sortie) ou de décodage complet ne le sont
   probablement pas. **Je n'ai pas vérifié l'atteignabilité alerte par alerte**, et la correction est la même pour
   toutes (13.0.0).
   `pandas.read_excel` (4 modules) passe par openpyxl en `read_only` : les images n'y sont pas lues.
2. **matplotlib** — export PDF/Excel des rapports (`certus/utils/certus_reports.py:376` `savefig` PNG,
   `:656` `imread` PNG, `:385` image openpyxl ; appelés par `certus/ui/mixins/certus_base_core_mixins.py:612,641`).
   Les images sont des PNG produits par CERTUS lui-même : pas d'entrée hostile.

L'exécutable gelé (`certus_hub.spec`) n'exclut ni `PIL` ni `matplotlib` : il embarque vraisemblablement Pillow 12.3.0
(je n'ai pas inspecté de build).

Usage direct restant, hors application : `reports/DESIGN_bs5050_2026-10-22/tikhonravov/envelope_v2/fig4_2020_extract.py`
(`from PIL import Image`, script d'étude ponctuel).

## 4. setuptools — pourquoi « outils seulement »

Aucune occurrence de `setuptools`, `pkg_resources` ni `distutils` dans les fichiers suivis. Seul `pyinstaller` (extra
`freeze`) le tire, pour construire l'exécutable. L'avis (GHSA-xmj3-9gf7-h52w, low) porte sur un échappement de chemin
Windows via `namespace_packages.txt` lors d'une installation « legacy » d'un paquet piégé : rien que CERTUS fasse à
l'exécution.

## 5. Ce qu'une montée demanderait (non fait)

- Pillow 12.3.0 → 13.0.0 est une **version majeure** : contraintes de matplotlib 3.11.2 et roues pour Python 3.15 non
  vérifiées ici. Régénérer `uv.lock` et `requirements.lock`, puis la validation complète (`0 failed`, oracle compris) et
  un essai de l'export PDF/Excel et du chargement RE.
- setuptools 84.0.0 → 84.1.0 : mineure, n'affecte que la construction ; même régénération des deux verrous.

## 6. Liste des alertes

Pillow, toutes « < 13.0.0 » ou « ≤ 12.3.0 », corrigées en 13.0.0 — par gravité, numéro d'alerte et GHSA :

- **critical** : 2 GHSA-8g5g-8vmr-9782 · 10 GHSA-w889-685w-c8fh · 27 GHSA-332p-7hrc-92wf · 32 GHSA-v9pv-5gc8-w2m6 ·
  42 GHSA-5x8w-8jj5-q52h
- **high** : 1 GHSA-58r4-6rv3-gfh8 · 3 GHSA-c6hw-5grf-ff96 · 5 GHSA-p4wg-p73j-c528 · 6 GHSA-pchr-8j38-3x4p ·
  7 GHSA-q45j-58j2-45rg · 9 GHSA-65qm-jvmh-6pqg · 12 GHSA-7mwm-ghpf-9vrm · 13 GHSA-j4m9-6w36-pw47 ·
  14 GHSA-cp9v-662q-vvx9 · 15 GHSA-27h8-gf7j-v5hc · 17 GHSA-22hg-r758-rrw9 · 22 GHSA-jg86-v3jv-hrpm ·
  23 GHSA-gg2r-wvfm-q9rx · 24 GHSA-5xm2-6676-qcp9 · 25 GHSA-f2g6-542v-9j58 · 30 GHSA-g842-9rc4-69pw ·
  33 GHSA-mrfp-p49p-3hf2 · 35 GHSA-3j72-p6qg-6xp7 · 36 GHSA-g4qv-2jxx-769h · 37 GHSA-9v9v-9qvf-h2hj ·
  38 GHSA-g7cr-3p24-7wf7 · 39 GHSA-78g4-xqwv-q3g8 · 43 GHSA-xvh5-g6gv-559v · 44 GHSA-xcvg-w56q-r89m
- **medium** : 4 GHSA-462x-pgg6-55fp · 8 GHSA-vx6w-vv9f-6gvg · 11 GHSA-4558-3h8r-v8xp · 16 GHSA-fc9g-5qg7-mf45 ·
  18 GHSA-74r2-7ff9-mjj2 · 19 GHSA-rfgq-q3w2-pmv2 · 20 GHSA-xgh8-jp6q-p5x8 · 21 GHSA-254f-3936-288h ·
  26 GHSA-4rr5-89j8-mwwm · 29 GHSA-p8hx-v2p6-rp84 · 31 GHSA-24rc-8hj2-v98c · 34 GHSA-4rm8-3hmm-39fg ·
  41 GHSA-654x-cwwv-5j9c · 45 GHSA-wqgw-9xfh-qf2g

setuptools : **low** 40 GHSA-xmj3-9gf7-h52w (≥ 38.2.2, < 84.1.0 → 84.1.0).
