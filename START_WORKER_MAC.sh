#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Jalankan dulu: bash START_MAC.sh (di terminal pertama).' >&2
  exit 1
fi
export MHS_MODE=demo
echo 'Worker lokal mulai. Biarkan terminal ini terbuka; Ctrl+C untuk berhenti.'
exec .venv/bin/python -m backend.app.worker
