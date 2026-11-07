# Vérification GUI — Python 3.15.1 — 2026-10-25

Arbre testé : `master`, `687ebe0b`, propre avant campagne. Python 3.15.1 64 bits, Qt 6.11.0.

## Mesures de cette campagne

| contrôle | résultat |
|---|---|
| `scripts/preflight.py` | `PREFLIGHT=GO` ; import dans cet arbre |
| `python -m pytest tests/ui/ -q --no-cov -x` | **1342 passed, 12 skipped, 2 xfailed**, 2771 warnings, 1992,30 s ; sortie 0, `pytest_ui.log` |
| `python -m pip check` | `No broken requirements found.` |
| banc UX sur Qt `windows` | **11 interfaces construites, affichées et fermées**, un processus à la fois ; aucun verdict défavorable du banc |

Interfaces : HUB, DESIGN, STRAT, RE, INDEX, INDEX SPLINE, FIELD, SMOOTHER, SUBSTRATE INDEX, METAL SINGLE et METAL BILAYER.
Le protocole `native_gui_probe.py` réutilise `_measure` du banc `scripts/audit_ux_certus.py` ; préférences privées, configurations
initiales, captures `QWidget.grab()`. Les onze captures claires ont été examinées ; le tour de bienvenue masque une partie de
plusieurs fenêtres. Neuf interfaces ont aussi une capture sombre ; SMOOTHER et SUBSTRATE INDEX n'ont pas de bascule de thème
dans ce banc et n'ont été capturés qu'en clair. Les JSON `*_native.json` donnent le moteur réel, la visibilité et la taille
effective à chaque capture ; la taille demandée de 1920 × 1080 peut être réduite par l'écran Windows.

## Portée

Ces mesures confirment l'exécution des tests GUI/UX et l'ouverture native des onze interfaces sous 3.15.1. Elles **ne
certifient pas un fonctionnement à 100 %** : les cas ignorés et attendus en échec restent exclus, les parcours manuels
complets et les calculs métier de chaque module n'ont pas été rejoués ici, ni le gel ni les autres suites de tests.
Les défauts ouverts de `docs/AUDITS.md` restent ouverts. Les avertissements comprennent notamment des dépréciations pandas.

Le pilotage manuel a été bloqué par les deux accès Computer Use : `window id ... no longer belongs to ...; current owner
is ...`, avec le même identifiant propriétaire affiché des deux côtés. Le banc Qt natif est le complément mesuré ; il ne
remplace pas une validation manuelle exhaustive. Le premier lancement du hub en mode caché a été arrêté puis relancé
avec `pythonw.exe` en mode visible ; aucun code applicatif n'a été modifié.

## Actualisation des pages HTML demandée ensuite

`pages/CERTUS_DESIGN.html` : défaut mémétique, relances, branche PGLOBAL identifiée, mesures et limites du bilan
`DESIGN_bs5050_2026-10-22`. `pages/CERTUS_STRAT.html` : réglages d'ETAT, repères A3 des 21 et 24 octobre, défaut des faux
points tournants et absence de validation externe ; campagnes historiques distinguées des références courantes.
Chaque série chiffrée renvoie à son Markdown source ; aucun calcul scientifique n'a été relancé pour ces pages.

Contrôles exécutés : `verifier_html.py` sur les deux pages, `coherence_md.py`, `check_claude_md.py`, `check_docs.py`,
`ruff check .` et `git diff --check`, tous sans échec. Rendu contrôlé dans le navigateur intégré : les liens internes
atteignent un titre visible sous le menu fixe, sans débordement horizontal. Captures :
[`DESIGN_html_preview.jpg`](DESIGN_html_preview.jpg), [`STRAT_html_preview.jpg`](STRAT_html_preview.jpg).
