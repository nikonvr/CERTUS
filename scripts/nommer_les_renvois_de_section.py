"""NOMMER LE DOCUMENT SUR UN RENVOI « §N » QUI POINTE AILLEURS.

    C:\\envs\\certus\\Scripts\\python.exe scripts\\nommer_les_renvois_de_section.py           # SIMULATION
    C:\\envs\\certus\\Scripts\\python.exe scripts\\nommer_les_renvois_de_section.py --ecrire  # applique

## 🔑 POURQUOI CET OUTIL EXISTE

`scripts/coherence_md.py` signale les renvois de la forme « §N » ecrits dans un dossier ou la
section N **n'existe pas**, alors qu'elle existe dans un AUTRE document. Le lecteur doit alors
devinerpou chercher. 📏 Le 2026-08-22 il y en avait **41**, sur cinq dossiers.

Ce n'est pas une erreur de fait -- l'outil le dit lui-meme, « un signalement n'est PAS une
erreur » -- mais c'est un cout de lecture qui se paie a chaque passage, et il grandit avec le
nombre de dossiers. Le corriger une fois vaut mieux que le relire vingt fois.

## 🔴 CE QU'IL NE DEVINE PAS

La verite vient de `coherence_md.py`, jamais d'une regex maison : l'outil a deja verifie que la
section est **absente ici** et **presente la-bas**. Ce script ne fait que reecrire ce qu'il
nomme, sur la ligne qu'il designe.

⚠️ Il ne touche PAS un renvoi deja nomme (« §21 de `CLAUDE.md` »), ni un renvoi vers une section
locale. Et il refuse d'agir si la ligne a change depuis le signalement -- ce serait ecrire a
l'aveugle.

🔒 SIMULATION PAR DEFAUT. Il modifie de la documentation ; il faut `--ecrire` pour agir.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

#: La ligne que le controle emet. Elle porte tout : ou, quel §, et dans quel document il vit.
_RE = re.compile(
    r"🟠 (?P<doc>[\w./-]+\.md):(?P<ligne>\d+) — §(?P<num>[\w-]+) absent d'ici, "
    r"present dans (?P<cible>[\w./-]+\.md)"
)


def sortie_du_controle() -> str:
    r = subprocess.run(
        [PY, "scripts/coherence_md.py"], cwd=str(ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    return (r.stdout or "") + (r.stderr or "")


def resoudre(nom: str) -> Path | None:
    for cand in (ROOT / nom, ROOT / "docs" / nom, ROOT / "reports" / nom):
        if cand.is_file():
            return cand
    return None


def lien_relatif(depuis: Path, vers_nom: str) -> str:
    """Le chemin du lien, VU DEPUIS le document qui le porte.

    🔴 DEFAUT REEL, ATTRAPE AVANT D'ECRIRE. La premiere version ecrivait `(CLAUDE.md)` quel que
    soit l'emplacement du document citant. Depuis `docs/`, ce lien pointe vers `docs/CLAUDE.md`
    -- qui n'existe pas. On aurait remplace 33 renvois anonymes par 33 LIENS MORTS, et le
    controle des ancres ne balaye que le HTML.
    """
    cible = resoudre(vers_nom)
    if cible is None:
        return vers_nom
    import os
    return Path(os.path.relpath(cible, depuis.parent)).as_posix()


def main() -> int:
    ecrire = "--ecrire" in sys.argv[1:]
    signalements = list(_RE.finditer(sortie_du_controle()))
    if not signalements:
        print("🟢 aucun renvoi de section anonyme. Rien a faire.")
        return 0

    print(f"{'ECRITURE' if ecrire else 'SIMULATION -- rien ne sera ecrit'}\n")
    # On groupe par document, et on traite les lignes de la PLUS GRANDE a la plus petite :
    # une reecriture ne change pas le nombre de lignes ici, mais l'ordre decroissant rend le
    # script insensible a toute insertion future.
    par_doc: dict[Path, list[re.Match]] = {}
    introuvables = 0
    for m in signalements:
        q = resoudre(m.group("doc"))
        if q is None:
            print(f"  🔴 {m.group('doc')} introuvable sur le disque -- ignore")
            introuvables += 1
            continue
        par_doc.setdefault(q, []).append(m)
    faits = sautes = 0
    for q, ms in sorted(par_doc.items()):
        lignes = q.read_text(encoding="utf-8").splitlines(keepends=True)
        touche = 0
        for m in sorted(ms, key=lambda x: -int(x.group("ligne"))):
            i = int(m.group("ligne")) - 1
            if not (0 <= i < len(lignes)):
                print(f"  🟠 {q.name}:{i+1} hors du fichier -- ignore")
                sautes += 1
                continue
            ln = lignes[i]
            num, cible = m.group("num"), m.group("cible")
            # 🔴 On n'ecrit pas a l'aveugle : le § doit etre LA, et pas deja nomme.
            # 🔴 CE QUE CE MOTIF REFUSE DE TOUCHER, et chaque exclusion est mesuree :
            #   `§24-26`  -> un renvoi vers le DEFAUT 26 du §24, pas vers le §2 ni le §24
            #   `§2.2`    -> une sous-section, pas la section 2
            #   `§21 de `CLAUDE.md`` -> deja nomme
            # ⚠️ Mais `§2.` en FIN DE PHRASE est bien un renvoi nu : on n'exclut donc le point
            # que s'il precede un CHIFFRE. Premiere version trop large, elle sautait 2 cas justes.
            motif = re.compile(
                rf"§{re.escape(num)}(?!\s*(?:de|of)\s+[\[`])(?![\w-])(?!\.\d)"
            )
            if not motif.search(ln):
                print(f"  🟠 {q.name}:{i+1} : §{num} absent de la ligne ou deja nomme -- ignore")
                sautes += 1
                continue
            rel = lien_relatif(q, cible)
            lignes[i] = motif.sub(f"§{num} de [`{cible}`]({rel})", ln, count=1)
            touche += 1
            faits += 1
        if touche:
            print(f"  {'✅' if ecrire else '→ '} {q.name} : {touche} renvoi(s) nomme(s) -> {ms[0].group('cible')}")
            if ecrire:
                q.write_text("".join(lignes), encoding="utf-8")

    print(f"\n{faits} renvoi(s) {'nomme(s)' if ecrire else 'a nommer'}"
          f"{'' if ecrire else ' -- relance avec --ecrire'}"
          f"{f', {sautes} saute(s)' if sautes else ''}"
          f"{f', {introuvables} introuvable(s)' if introuvables else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
