#!/usr/bin/env bash
# ENCHAINER r75x2 SOUS LE PROTOCOLE DE PRODUCTION -- des que la machine est libre.
#
# 👤 : « moi je veux savoir ce qu'il donne sur le code de prod ! »
#
# ## 🔴 POURQUOI CE RUN EST NECESSAIRE ALORS QU'UN CHIFFRE EXISTE DEJA
#
# Le SEEL 0,5642 nm du 2026-08-22 a bien ete produit par l'orchestrateur, chemin de production,
# `overrides_tag = None`. MAIS il a ete lance avec `--graines 404 505`, c'est-a-dire avec les
# deux graines dont on SAVAIT DEJA qu'elles trouvaient.
#
# 🔑 Le chiffre est vrai, le PROTOCOLE ne l'est pas. Choisir les graines apres avoir vu leur
# resultat est un canal de selection, et ce depot en a mesure un a +12,9 %. Le protocole de
# production balaie l'echelle DANS L'ORDRE, sans savoir lesquelles marchent.
#
# Ici l'echelle 101, 202, 303, 404, 505 est deja mesuree (3 trouvent) et sera SAUTEE ; le run
# lancera donc 606 et 707, jamais essayees, et unira tout ce qui trouve. Le resultat peut etre
# meilleur que 0,5642 -- deux graines de plus dans l'union -- ou identique.
#
# ## L'ATTENTE, ET POURQUOI ELLE REGARDE LES PROCESSUS
#
# 🔴 On n'attend JAMAIS l'apparition d'un artefact comme signal de fin : la sonde l'ecrit AVANT
# sa synthese, et une chaine qui le guettait a lance la mesure suivante 10 s trop tot le
# 2026-08-21. On regarde donc les PROCESSUS, avec une temporisation de trois minutes : la
# campagne en cours passe d'un composant au suivant en quelques secondes, jamais en trois
# minutes, donc aucun risque de demarrer dans un intervalle.

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/serie75_2026-08-22"
mkdir -p "$J"
LOG="$J/journal_r75x2_prod.log"

echo "[enchainer] en attente que la machine se libere -- $(date '+%Y-%m-%d %H:%M:%S')"
vide=0
while [ "$vide" -lt 3 ]; do
  n=$(powershell.exe -NoProfile -Command \
      "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Measure-Object).Count" \
      2>/dev/null | tr -d '\r' | tail -1)
  n="${n:-0}"
  if [ "$n" -eq 0 ]; then vide=$((vide + 1)); else vide=0; fi
  sleep 60
done

echo "[enchainer] machine libre -- demarrage r75x2 a $(date '+%H:%M:%S')"
t0=$(date +%s)
"$PY" scripts/orchestre_multigraine.py r75x2 \
    --budget 2h \
    --objectif meilleur \
    --mode deep \
    --resolution 2.0 \
    --graine-notation 42 \
    --evenements \
    > "$LOG" 2>&1
code=$?
echo "[enchainer] r75x2 EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
grep -E "RESULTAT CITABLE|annonce en cours|Aucune realisation|NON ESSAYEES" "$LOG" | sed 's/^/    /' || true
