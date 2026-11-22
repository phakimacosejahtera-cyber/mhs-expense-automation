# Shared-office deployment plan (3–5 users)

## Confirmed operating requirements

- 3–5 people use the application from different computers in one office.
- Every signed-in user has the same application permissions.
- Transactions, attachments, and reports are shared through one central service.
- Existing SQLite files, PostgreSQL test data, receipt files, and audit history must be retained.

## Current implementation boundary

The current application is not a multi-user hosted production system.

- `backend/app/db.py` selects SQLite by default. PostgreSQL is selected only for `pg_test` and `hosted_preview`.
- `backend/app/runtime.py` deliberately blocks production mode and deployment.
- `backend/app/hosted_preview.py` only permits synthetic test data in `mhs_owner_test`.
- `backend/app/owner_auth.py` and the hosted-preview startup path implement one pinned Google owner, not registration/invitation for 3–5 users.
- `database/bootstrap_production.sql` is a candidate for a separate empty project, but is not a complete production application setup and must not be executed in the existing test project.
- `backend/app/receipt_storage.py` only implements test bucket `receipts-test`; the production bucket and migration path are not wired into a production runtime.

Therefore this branch is a rollout specification, not permission to deploy or use real receipts.

## Target topology

```text
Office computers (3–5 browsers)
          |
          | HTTPS, individual login
          v
     One hosted FastAPI service
          |
          +---- one production PostgreSQL database
          |       shared transactions, users, categories,
          |       activities, audit history, reports
          |
          +---- one private production object bucket
                  shared receipt originals and versions
```

The application server, not each user's computer, connects to PostgreSQL and object storage. Never expose database or storage administrator credentials to browsers.

## Equal-permission user model

Implement individual accounts (one identity per person) with a common application permission set. Do not share one login. Record the authenticated user ID on each write for audit attribution even though permissions are equal.

Before implementation, decide and document:
- invitation/provisioning mechanism for the first 3–5 accounts;
- whether any account may invite/deactivate another account (this is account administration, not a transaction privilege);
- session revocation and account recovery process.

Do not reuse the current owner-only Google identity pin as a multi-user login system.

## Non-destructive data preservation and migration

No migration may run against the existing test project or the existing local SQLite data directory.

1. Inventory every SQLite database, PostgreSQL test schema, local receipt directory, and export snapshot. Record paths, sizes, timestamps, row counts by table, and SHA-256 checksums for files.
2. Take immutable, independently stored backups of each database and receipt directory. Test restoration into a disposable environment before proceeding.
3. Provision a new, dedicated production Supabase project and private receipt bucket. Keep it separate from the test project and test credentials.
4. Create a versioned production schema using additive migrations. Do not use `DROP`, `TRUNCATE`, destructive table recreation, or overwrite existing database files.
5. Build an explicit, repeatable importer with source-to-target mapping, stable original IDs where safe, idempotency keys, transaction boundaries, and a migration ledger. Preserve original timestamps, audit records, receipt hashes, and document-version relationships.
6. Copy receipt objects without deleting originals. Verify object count, byte size, and SHA-256 after copy. Keep source receipts read-only until sign-off.
7. Reconcile source and target row counts, monetary totals by currency and period, duplicate keys, orphan references, receipt hashes, and audit continuity. Produce a signed migration report.
8. Run the new application in a restricted acceptance phase. Only switch users after login, concurrent writes, shared visibility, upload/download, export, restart persistence, backup, and restore tests pass.
9. Keep the old database and files unchanged and recoverable for an agreed retention period. Rollback means switching the service back to the old system; never reverse-migrate by deleting source data.

## Required engineering work before production

- Multi-user authentication and account lifecycle with individual identities.
- Shared permission policy (same transaction permissions for all active members) enforced server-side.
- Production-only PostgreSQL adapter, explicit schema/role checks, TLS verification, connection pooling and tested concurrent writes.
- Production-only private object storage adapter; no local filesystem fallback in hosted mode.
- Versioned schema migration and one-time import/verification tooling.
- Persistent export snapshots, background worker and retention semantics.
- Automated tests for two or more users concurrently creating and viewing records, authorization, session revocation, and audit attribution.
- Backup/restore runbook, monitoring, rate/size limits, and operational owner.

## Deployment gates

Do not enable public hosting or use real financial/personal information until all required engineering work is implemented and independently tested. Do not place DSNs, passwords, OAuth secrets, or storage keys in GitHub. Configure secrets directly in the hosting provider. Do not execute `database/bootstrap_production.sql` in the current test project.
