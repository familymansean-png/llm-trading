#!/usr/bin/env bash
# One decision cycle: pull latest state, decide+trade, push the log back.
# Intended to be run by the hourly scheduled Cowork session.
set -euo pipefail
cd "$(dirname "$0")"
git pull --quiet --rebase || true
set -a; [ -f .env ] && source .env; set +a
python3 harness/trader.py "$@"
git add logs/ && git commit --quiet -m "cycle $(date -u +%Y-%m-%dT%H:%M)" || true
git push --quiet || true
