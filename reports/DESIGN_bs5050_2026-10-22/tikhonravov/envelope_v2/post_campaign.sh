#!/usr/bin/env bash
# After campaign.sh: monotonicity repair of the 50/50 envelope, then the full validation of the DESIGN changes.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "campaign done" campaign.log 2>/dev/null; do sleep 60; done
CURVES="curve_foc27-36_free_s2.csv curve_free_s1.csv curve_abl_t0k1_free_s1.csv curve_abl_t0k6_free_s1.csv curve_abl_t1k1_free_s1.csv curve_v3_free_s1.csv"
log "post 1: monotonicity repair"
python monotone.py $CURVES > monotone.out 2>&1 || log "post 1 FAILED"
log "post 2: validation"
R=../../../..
V="$PWD/validation_2026-10-28.txt"
{
  cd "$R" || exit 1
  echo "== ruff";      python -m ruff check . 2>&1 | tail -3
  echo "== oracle";    python -m pytest tests/oracle/ -q --no-cov 2>&1 | tail -3
  echo "== unit";      python -m pytest tests/unit/ -q --no-cov 2>&1 | tail -3
  echo "== ui";        python -m pytest tests/ui/ -q --no-cov 2>&1 | tail -3
  echo "== rest";      python -m pytest tests/ -q --no-cov --ignore=tests/oracle --ignore=tests/unit --ignore=tests/ui 2>&1 | tail -3
  echo "== coherence"; python scripts/coherence_md.py 2>&1 | tail -2
  echo "== claude_md"; python scripts/check_claude_md.py 2>&1 | tail -2
  echo "== docs";      python scripts/check_docs.py 2>&1 | tail -2
  echo "== c1_diff";   python scripts/c1_diff.py HEAD 2>&1 | tail -3
} > "$V"
log "post done"
