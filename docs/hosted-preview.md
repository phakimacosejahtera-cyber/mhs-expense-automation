# Hosted preview (synthetic data only)

Use the existing Supabase test project, schema mhs_owner_test and private
receipts-test bucket. This is NOT production. Do not use actual financial or
personal data, and keep receipts-originals empty. S3 access keys are project-wide;
the startup empty-bucket check is not credential isolation. Before real data,
separate the projects or replace the project-wide credentials with enforceable
least-privilege access. Do not execute bootstrap_production.sql in this project.

## Offline checks first
From repository root in Windows PowerShell, with existing venv:
```powershell
$env:MHS_MODE="demo"
$env:MHS_STORAGE_MODE="local"
$env:MHS_RUN_PG_TESTS="0"
$env:MHS_RUN_STORAGE_TESTS="0"
.\.venv-win\Scripts\python.exe -m pytest -q --tb=short tests/test_hosted_preview.py tests/test_production_security.py tests/test_runtime.py tests/test_owner_auth.py tests/test_browser_ocr_api.py tests/test_postgres.py tests/test_receipt_storage.py
```
Expected 66 passes, 2 opt-in live tests skipped if prior tests remain unchanged.
The new tests use mocks; live role and Render checks still required.

## One-time local provisioning (only after review/merge)
Requires the existing local administrator DSN, trusted PostgreSQL CA file,
Supabase owner/auth settings and current S3 credentials in the same terminal.
Never send administrator DSN or actual secret values to chat or Render.
The local test owner must already be bound to the verified Google identity.
```powershell
$env:MHS_MODE="pg_test"
$env:MHS_PREVIEW_ACK="synthetic-only"
.\.venv-win\Scripts\python.exe -m backend.app.provision_preview
```
This creates one limited role mhs_preview_app, grants access to existing test
tables, creates RLS policies and a restricted metadata view, checks the actual
new role login over verified TLS, and copies only the preview environment block
to Windows clipboard. No existing test rows are modified. Do not rerun if role
already exists. If live verification fails, do not deploy; local provisioning
may have committed, so investigate before retrying or rotating the role.
Disable clipboard history/sync while handling secrets; clear clipboard/history
after pasting. No screenshots containing the environment block.

## Render
Use the existing configured free web service form, Python, main, Singapore,
root directory blank, build command pip install -r backend/requirements.txt,
start command python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --no-access-log,
health path /api/health, auto-deploy Off.
Paste clipboard block directly into Add from .env only after local setup
reports successful role verification. Add the public Supabase CA certificate
as a Render secret file named prod-ca-2021.crt (file contents, not path);
the environment points to /etc/secrets/prod-ca-2021.crt.
Render supplies RENDER_EXTERNAL_URL; there is no guessed callback hostname.

After creating/deploying the service, copy its actual onrender.com URL into the
Supabase Auth redirect allowlist as an exact URL ending /api/auth/google/callback.
Retain the local redirect for ongoing development. No new Google OAuth client
is needed for the same Supabase project. Confirm HTTPS host, health, owner login
and rejection of non-owner/anonymous requests. Check one synthetic cloud receipt
preview and one download. Verify test data persists across restart. Do not
enable auto-deploy until review and smoke test pass.

## Deliberate limitations
- Local-only receipt files from earlier tests are not migrated or served on Render.
- New receipts use cloud test storage; production storage is never written.
- Excel downloads are generated in memory; download event and SHA-256 are
  recorded, but server-side archived XLSX bytes are not retained in preview.
- Worker remains local-demo-only; no scheduled purge, reminders or escalation
  in hosted preview. Backup/restore, malware validation, orphan reconciliation,
  persistent report snapshots, scalable upload limits, and independent production
  credentials are outstanding. Real-data use and production runtime remain blocked.
- Render Free suspends idle services and its filesystem is ephemeral.
