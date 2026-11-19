#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
printf '%s\n' 'PT Mulia Hakimaco Sejahtera - Expense Automation V0.1 (macOS)'
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 belum tersedia. Install Python 3.11, 3.12, atau 3.13 dari python.org.' >&2
  exit 1
fi
python3 - <<'PYVERSION'
import sys
if not (3, 11) <= sys.version_info[:2] <= (3, 13):
    raise SystemExit(f'Python {sys.version.split()[0]} terdeteksi. V0.1 mendukung 3.11-3.13; gunakan versi tersebut.')
print('Python:', sys.version.split()[0])
PYVERSION
if [ ! -x .venv/bin/python ]; then
  echo '[1/3] Membuat virtual environment...'
  python3 -m venv .venv
fi
echo '[2/3] Menginstal dependency Python... (butuh internet pada instalasi pertama)'
.venv/bin/python -m pip install -r backend/requirements.txt
echo '[3/3] Memulai aplikasi lokal...'
echo 'Buka: http://127.0.0.1:8000'
echo 'DEMO LOKAL SAJA. Jangan expose port ke internet.'
echo 'Hentikan dengan Ctrl+C.'
export MHS_MODE=demo
exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
