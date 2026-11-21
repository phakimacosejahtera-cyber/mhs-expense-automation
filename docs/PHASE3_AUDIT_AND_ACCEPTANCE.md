# Phase 3 — Functional improvement: audit and acceptance plan

Date: 2026-11-21. Baseline main commit: 2339035eb7861ca9656be684754e11a673599140.
Status: proposed development plan; static review, not completed implementation or production approval.

## Objective and boundaries

A practical expense and cash recap tool for PT Mulia Hakimaco Sejahtera, operated by one owner, to reduce manual receipt processing and prepare accurate records for tax reporting. The software is a recordkeeping aid, not a tax filing or tax determination engine. XTROI AutoExpense is a functional/UX reference, not a mandate to copy its storage architecture. Retain orange/black/white identity, FastAPI, existing frontend, PostgreSQL/Supabase Auth/private storage adapters, and a local development path. Render deployment is on hold; retain PRs 1–6 and hosted preview restrictions. Use synthetic data only until a separate production security/recovery gate passes. Do not store real receipts or secrets in GitHub.

Authoritative existing business rules: [FINAL_BUSINESS_RULES.md](FINAL_BUSINESS_RULES.md). This document proposes work, does not supersede that baseline. In particular, existing segregation of duties remains enforced until an explicit owner-approved change. Preserve original document bytes and historical exports. No automatic destructive archiving, schema resets, credential changes, or provider migrations in this PR.

## Evidence and prioritized findings

| ID | Severity | Evidence (baseline) | Finding / proposed action |
|---|---|---|---|
| F01 | P0 | backend/app/main.py:680–726; frontend/assets/app.js:121,145 | Global income setting and expense aggregation by month only; year label static and bars for income hardcoded zero. Establish dated income records and consistent period-scoped finance queries before representing charts as actuals. Do not infer historical income dates from global total. |
| F02 | P0 | backend/app/main.py:680–691 | Income mutation authenticates but does not explicitly enforce admin role. Add server-side access controls and tests; do not rely on hidden UI. Assess global income visibility in non-owner modes. |
| F03 | P1 | frontend/assets/app.js:242–330; frontend/ocr-engine-entry.js; frontend/ocr-parser.mjs; backend/app/main.py:347–379 | Browser image OCR submits an untrusted observation, suggesting amount/date; PDFs remain manual. Improve candidate extraction, confidence/ambiguity presentation, persisted retry and review. Never mark client OCR trusted or invent values. |
| F04 | P1 | backend/app/main.py:734–774; XTROI_AutoExpense(1).html exportXlsx | Existing expense-only export has Transactions, Summary, Report Info, scope filter and formula-injection guard. XTROI offers Ringkasan, Semua Transaksi, Pemasukan, Pengeluaran, true Excel dates, numeric amounts and total formulas. Adapt styling and presentation, keep audit metadata/receipt pointers; do not mislabel expenses as formal tax calculations. |
| F05 | P1 | FINAL_BUSINESS_RULES.md sections C–F; backend/app/main.py:409–449,629–679; owner-only startup | Existing multi-person reinstatement requires independent eligible admin. Single owner cannot satisfy this if they initiate it. Preserve control, flag design decision explicitly; no bypass or hidden second account. Simplify ordinary receipt UX without erasing approvals. |
| F06 | P0 release gate | backend/app/receipt_storage.py; hosted_preview.py; main.py startup | S3 credential is project-wide; preview is explicitly synthetic and production bucket must stay empty. Startup guard is not ongoing isolation. Require production separation, least privilege, verified backup/restore and tested authorization before real data. |
| F07 | P0 release gate | main.py:734–774; README.md; implementation matrix (historical) | Hosted exports download-only; independent DB + original receipt recovery has not been demonstrated. Design consistent backup, checksums and restore into isolated destination. Do not claim implemented merely because an export is available. |
| F08 | P1 | frontend/package.json | npm test is a placeholder; establish actual parser/UI verification, automated API regression and browser acceptance. |
| F09 | P1 | README.md and IMPLEMENTATION_MATRIX.md | Documentation describes older V0.1 and is not authoritative about current Auth, PostgreSQL and OCR extensions. Refresh factual coverage after verified work, preserve historical reports. |

P0 = financial correctness/security/recovery prerequisite for release (fix order may differ); P1 = high-value functional improvement. These findings are code observations; dynamic reproduction and broader review remain open.

## Delivery sequence / acceptance

### 3.1 UI/UX and owner workflow shell
Design responsive orange/black/white interface with clear navigation, current mode and period, upload progress, draft/review distinction, empty/error/loading states, and accessible controls. No hardcoded example financial figures presented as actual. Preserve existing IDs and routes where appropriate, authentication boundaries, and reference flow. Test desktop/mobile and keyboard interactions. Finance correctness (F01/F02) must precede publishing any new financial charts; can be developed alongside shell.

### 3.2 Financial integrity and dashboard
Design dated income records separately from expenses, explicit period and dataset semantics (calendar year/activity; do not silently equate XTROI datasets with MHS activities), one consistent source of totals, and server-side admin mutation. Decide income data model and migration of global income before implementation: retain old value as legacy/unallocated until owner confirms dates, no invented transactions or retroactive allocation. Use integer minor units consistently. Include approved, non-deleted expenses only; reversed/rejected/pending/draft excluded. Confirm receipt date, not upload date, determines period. Define balance as selected period net movement unless opening balance is explicitly supported. Test years crossing December/January, empty data, leap dates, mixed statuses, authorization, reversals/corrections, and dashboard-export reconciliation. Test SQLite and PostgreSQL adapters, including restricted role privileges and migrations.

### 3.3 Excel reporting
Propose owner-facing workbook Ringkasan, Semua Transaksi, Pemasukan, Pengeluaran; retain existing required Transactions/Summary/Report Info compatibility or explicitly approve changed contract. Use real Excel date/number types, IDR format, filters, frozen headers, formulas and totals. Include receipt links with access checks, category/activity and stable transaction ID, metadata on scope/period/export time. Transfer recipient/sender fields and opening balances need agreed data mapping, not guesses. Snapshot content immutable; no live Excel sync. Test zero rows, formulas, formula injection, exact totals, corrected/reversed state, and download access. Excel import exists in XTROI but not automatically in MHS scope; assess separately.

### 3.4 OCR intelligence
Preserve one receipt = one transaction, original immutable file, raw observations separate. Provide multi-file progress, candidate amount/date/vendor/description/invoice/payment/category where supported, confidence or explicit ambiguity, manual fallback, retry after reload. PDF text extraction or rendering with resource limits; never fabricate OCR and never use client confidence alone for auto-approval. Preserve 8 MiB upload limit unless changed deliberately. Build synthetic labeled corpus across Indonesian receipts, blurred/rotated images, transfer proofs, ambiguous totals, date/reference numbers, handwriting and PDFs; measure field accuracy, abstention, latency, and failure recovery before claims. Confirm external asset/network dependencies and no receipt transfer to external OCR providers without explicit approval.

### 3.5 Workflow optimization
Keep risk-based review, duplicate flags, late receipt reasons, correction/version history, audit, and approved-only financial outputs. Single owner path should minimize clicks while maintaining explicit confirmation and risk rationale. Existing admin-initiated reinstatement remains blocked without independent admin. Propose separately either retain this restriction or a formally approved revised policy with explicit compensating controls; do not weaken it in UI changes. No approval based on fabricated trusted extraction. Test idempotency, duplicate submissions, concurrent decisions, rejected corrections and reinstatement eligibility.

### 3.6 Backup and restore
Back up database, all original/versioned receipts, metadata and export history as applicable. Keep backups encrypted, separate from runtime storage, exclude secrets/session tokens from ordinary downloadable backup. Use manifest/checksums, versioned format, consistent recovery point and documented retention, failed-job recovery, isolated restore dry-run and verification before any replacement. Determine scheduling based on local versus hosted runtime; local cannot run when laptop is off. Never confuse CSV/XLSX export with recoverable backup.

### 3.7 Storage management
Report measured usage and quota with data source/scope/time; handle unknown quota explicitly. Warn before limits. Preserve original receipt bytes; compression may generate separate display derivative, never replace originals. Archive only under owner-approved retention and restore-tested procedure. No unattended deletion of submitted docs or versions. Reconcile object and DB references and orphaned uploads safely.

### 3.8 Acceptance and release gate
Run existing regression suite plus new unit/API/adapter/browser tests. Validate local owner Google login, role denial, receipts and download, finance totals, OCR manual fallback, backup restore, storage safeguards, security headers and no credentials in logs. Live provider tests opt-in and synthetic only. No real company data until production credentials/storage boundaries, recovery, deployment strategy, access rules and owner acceptance are verified. Render remains optional for this phase; no change of plan or card.

## Open owner decisions (only before dependent feature changes)
- D1: how to record incoming funds and whether opening balance is needed, including handling legacy global income.
- D2: whether XTROI free-form datasets map to year, activity, or a separate partition and how reports filter.
- D3: whether existing independent reviewer restriction remains for reinstatement; default retain.
- D4: workbook column mapping and owner-approved tax-reporting format; do not claim fiscal compliance.
- D5: deployment and backup retention/location before production; no provider change at present.

## Test status and review
This PR is documentation only. No app code, DB, provider configuration or previous PR changed. No tests run as part of this document; previous reported 66 passed / 2 skipped remain historical, not a new result. Full code/browser audit not yet complete. Each implementation PR must report actual tests and limitations.
