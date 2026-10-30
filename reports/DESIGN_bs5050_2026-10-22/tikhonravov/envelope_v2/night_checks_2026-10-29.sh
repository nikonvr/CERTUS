#!/usr/bin/env bash
# Night of 2026-10-29: after the grow test (campaign24), alone on the machine, in series:
# full validation of CLAUDE.md section 2 (DESIGN "Compare" tab), c1_diff, the study's barrier recomputed with DESIGN's
# module, and the throughput of DESIGN's cost-and-gradient call. Outputs next to this script; nothing is committed here.
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
log() { echo "$(date '+%F %H:%M') $*" >> "$HERE/campaign.log"; }
until grep -q "grow test done" "$HERE/campaign.log"; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
log "night checks: validation (CLAUDE.md section 2), c1_diff HEAD, barrier with DESIGN's module, DESIGN speed"
V="$HERE/validation_2026-10-29.txt"
cd "$ROOT" || exit 1
{
  echo "== ruff"; python -m ruff check . 2>&1 | tail -n 3
  echo "== oracle"; python -m pytest tests/oracle/ -q --no-cov 2>&1 | tail -n 3
  echo "== unit"; python -m pytest tests/unit/ -q --no-cov 2>&1 | tail -n 15
  echo "== ui"; python -m pytest tests/ui/ -q --no-cov 2>&1 | tail -n 15
  echo "== rest"; python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui 2>&1 | tail -n 15
  echo "== coherence_md"; python scripts/coherence_md.py 2>&1 | tail -n 4
  echo "== check_claude_md"; python scripts/check_claude_md.py 2>&1 | tail -n 3
  echo "== check_docs"; python scripts/check_docs.py 2>&1 | tail -n 3
} > "$V" 2>&1
python scripts/c1_diff.py HEAD > "$HERE/c1_diff_2026-10-29.txt" 2>&1
log "night checks: validation and c1_diff written"
cd "$HERE" || exit 1
python barrier_design_check.py > barrier_design_check.log 2>&1 || log "barrier check FAILED"
python design_speed_check.py 300 7 > design_speed_check.log 2>&1 || log "speed check FAILED"
log "night checks done"
