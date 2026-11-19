#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Jalankan dulu: bash START_MAC.sh (lalu hentikan dengan Ctrl+C).' >&2
  exit 1
fi
.venv/bin/python -m pip install -r backend/requirements-dev.txt
exec .venv/bin/python -m pytest -q tests
