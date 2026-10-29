#!/usr/bin/env bash
# Queued at 2026-10-29 07:05, after campaign19. Trubetskov 2020 three-line designs (Fig. 4, fig4_2020_extract.py):
# deep 101 layers MF 0.0128 at TOT 14171 nm, classical 104 layers 0.0129 at 14101 nm. Our trajectories stop at
# 11600-12100 nm (0.0712, 0.0925; theirs 0.053-0.059 there). Continue 7 of them to 14500 nm, one process each.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

log "3line race to 2020: 7 gradual trajectories resumed from 11600/12100 nm up to 14500 nm, 240 min (theirs 0.0128 at 14171)"
i=0
for cfg in "1 100 gradual_classic.csv" "1 50 gradual_classic.csv" "2 150 gradual_classic.csv" \
           "1 80 gradual_deep4_cont.csv" "2 100 gradual_deep4_cont.csv" "3 70 gradual_deep4_cont.csv" \
           "4 100 gradual_deep4_cont.csv"; do
  set -- $cfg; i=$((i + 1))
  SEARCH_TARGET=threeline GRAD_DEEP=$1 GRAD_DTOT=$2 GRAD_TAG="_r2020_$i" GRAD_RESUME="$3" \
    python gradual.py 240 14500 > gradual_r2020_$i.out 2>&1 &
done
wait
log "3line race to 2020 done"
