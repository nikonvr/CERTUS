"""RECALER LES RENVOIS `fichier.py:N` QUE LES EDITIONS DE CODE ONT DECALES.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\recaler_renvois.py           # SIMULATION
    C:\\envs\\certus\\Scripts\\python.exe scripts\\recaler_renvois.py --ecrire  # applique

## 🔑 POURQUOI CET OUTIL EXISTE, ET IL EST NE D'UNE MESURE

📏 Le 2026-08-21, en une seule session, mes editions de code ont perime **dix** renvois
`fichier.py:N` repartis dans quatre documents, en **quatre** vagues :

    +20 lignes dans certus_strat_ui_state.py   (routage de screen_seed_list)
    +19 lignes dans certus_strat_ui_state.py   (routage de injected_strategies)
    +26 puis +40 dans certus_strat_robustness.py (instruments [GATE] et par niveau de bruit)
    +25 et +80  (enable_wl_diversity, _apply_wl_diversity)

Aucun n'etait faux quand il a ete ecrit.

    Un renvoi `fichier.py:N` est perime par TOUTE insertion en amont dans le meme fichier, y
    compris par un commentaire. C'est un cout d'entretien PROPORTIONNEL au volume d'edition du
    code, et il tombe sur des documents que l'editeur n'a pas ouverts.

🟢 Le controle F de `scripts/coherence_md.py` attrape ces derives -- il a mordu quatre fois en
une session, dans l'heure a chaque fois. Et surtout **il calcule deja la bonne ligne** :

    🔴 PLAN_PRODUCTION_2026-08-20.md:1155 — `...context.py:627` ne porte pas
       ['_extract_rmse_p95_for_noise'] (trouve ligne 706)

Cet outil consomme cette sortie et applique la correction. Il ne cherche rien lui-meme : la
verite vient du controle F, qui a deja verifie que le symbole se trouve bien a la ligne dite.

## ⚠️ CE QU'IL NE FAIT PAS, ET IL FAUT LE SAVOIR

Quand le controle F dit **« symbole introuvable »**, il n'a pas su localiser le symbole -- soit
il a ete renomme, soit il a disparu, soit il n'est pas la ou le document le croit. Ces cas
demandent une lecture humaine et **cet outil les laisse en place**, en les listant. 📏 Sur les
dix decalages de la session, deux etaient de cette nature.

🔒 **SIMULATION PAR DEFAUT.** Il modifie de la documentation ; il faut `--ecrire` pour agir.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# 🔴 La console Windows est en cp1252 et cet outil ecrit des fleches et des pastilles. Sans
# cette ligne il leve UnicodeEncodeError sur SA PREMIERE LIGNE DE SORTIE -- y compris sur le
# cas « rien a faire ». 📏 Constate le 2026-08-21 : l'outil avait ete ecrit et jamais vu
# fonctionner, parce que le seul essai avait ete fait quand il n'y avait rien a recaler... et
# ce cas-la plantait aussi. Meme defaut, meme correctif que dans `coherence_md.py`.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

#: La ligne que le controle F emet quand il SAIT ou le symbole se trouve.
_RE_RESOLU = re.compile(
    r"🔴 (?P<doc>[\w./-]+\.md):(?P<ligne_doc>\d+) — `(?P<cible>[\w./-]+\.py):(?P<vieille>\d+)`"
    r" ne porte pas \[(?P<sym>[^\]]*)\] \(trouve ligne (?P<neuve>\d+)\)"
)
#: Celle qu'il emet quand il ne sait PAS -- on ne touche a rien.
_RE_PERDU = re.compile(
    r"🔴 (?P<doc>[\w./-]+\.md):(?P<ligne_doc>\d+) — `(?P<cible>[\w./-]+\.py):(?P<vieille>\d+)`"
    r" ne porte pas \[(?P<sym>[^\]]*)\] \(symbole introuvable\)"
)


def sortie_du_controle() -> str:
    """Fait tourner coherence_md.py et rend sa sortie. La verite vient de lui, pas d'ici."""
    r = subprocess.run(
        [PY, "scripts/coherence_md.py"],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ecrire = "--ecrire" in sys.argv[1:]
    txt = sortie_du_controle()

    resolus = list(_RE_RESOLU.finditer(txt))
    perdus = list(_RE_PERDU.finditer(txt))

    if not resolus and not perdus:
        print("🟢 aucun renvoi decale. Rien a faire.")
        return 0

    print(f"{'SIMULATION -- rien ne sera ecrit' if not ecrire else 'ECRITURE'}\n")

    # 🔴 LA CORRECTION EST APPLIQUEE A TOUS LES DOCUMENTS, PAS AU SEUL QUE LE CONTROLE NOMME.
    #
    # 📏 Mesure du 2026-08-21 : le controle F ne signale qu'UNE occurrence par renvoi perime.
    # Deux vagues de suite, `certus_strat_ranking.py:410` et `:589` etaient cites dans DEUX
    # documents chacun, et l'outil n'en corrigeait qu'un -- laissant l'autre a la main, deux
    # fois. Or la correction `X:vieux -> X:neuf` est vraie PARTOUT ou `X:vieux` apparait :
    # c'est un fait sur le fichier cible, pas sur le document qui le cite.
    faits = 0
    for m in resolus:
        vieux = f"{m.group('cible')}:{m.group('vieille')}"
        neuf = f"{m.group('cible')}:{m.group('neuve')}"
        touches = []
        for doc in sorted(ROOT.rglob("*.md")):
            if ".git" in doc.parts:
                continue
            txt = doc.read_text(encoding="utf-8")
            n = txt.count(vieux)
            if not n:
                continue
            touches.append((doc, n))
            if ecrire:
                doc.write_text(txt.replace(vieux, neuf), encoding="utf-8")
            faits += n
        if not touches:
            print(f"  🟠 {vieux} deja absent partout -- ignore")
            continue
        ou = ", ".join(f"{d.name}×{n}" if n > 1 else d.name for d, n in touches)
        print(f"  {'✅' if ecrire else '→ '} {vieux} -> {neuf}"
              f"   (symbole {m.group('sym')}) dans {ou}")

    if perdus:
        print(f"\n🔴 {len(perdus)} renvoi(s) que le controle n'a PAS su resoudre — "
              f"lecture humaine requise, rien n'a ete touche :")
        for m in perdus:
            print(f"     {m.group('doc')}:{m.group('ligne_doc')} — "
                  f"{m.group('cible')}:{m.group('vieille')} — symbole {m.group('sym')}")
        print("   Le symbole a peut-etre ete RENOMME ou SUPPRIME : c'est le document qui a "
              "tort, pas seulement son numero de ligne.")

    print(f"\n{faits} renvoi(s) {'recale(s)' if ecrire else 'a recaler'}"
          f"{'' if ecrire else ' -- relance avec --ecrire'}.")
    return 0 if (ecrire or not faits) else 1


if __name__ == "__main__":
    raise SystemExit(main())
