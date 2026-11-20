# Production readiness — security preparation

This branch is deliberately NOT deployable. The existing runtime and worker
gates remain in effect. Do not change Render settings or use company receipts.

## Included in this PR
- Exact optional HTTPS Render origin, never supplied by a request Host header.
- HTTPS callback and Secure/HttpOnly/SameSite cookies; local test defaults preserved.
- Host validation and same-origin checks for unsafe methods in HTTPS owner mode,
  in addition to existing CSRF and server-side owner authorization.
- Optional pre-bound Supabase and Google identity pair; existing identity binding remains.
- Private no-store API responses, same-origin receipt framing, no-referrer,
  nosniff and HSTS in HTTPS mode. API docs disabled in owner mode.
- Candidate SQL bootstrap for an empty, separate production project; restricted
  application role initially NOLOGIN, RLS and explicit grants, append-only audit
  and export logs at the role privilege level. Not executed or live validated.

## Mandatory next release gates
1. Separate Supabase production project from the existing test project, with
   independent credentials, Google Auth configuration and private receipts-originals
   bucket. S3 keys are project-wide. A dedicated production project isolates
   test data from those credentials; do not use test S3 keys or postgres credentials.
2. Review and exercise bootstrap_production.sql in the isolated project. Provision
   a login for mhs_prod_app securely; verify it cannot access test/public tables or
   mutate audit/export history. Never embed a DB password in tracked SQL.
3. Implement production database connection with TLS verification, explicit
   schema/role checks and production-only credentials; require a pinned owner
   identity, exact HTTPS origin and separate production bucket. Verify bucket
   metadata via the restricted view. No local receipt fallback in production.
4. Keep the app owner-only. Do not expose demo login or allow new app users;
   restrict provider configuration, review session invalidation and TLS.
5. Validate upload/read/replace/approval/export in hosted preview using synthetic
   data. Resolve persistent export snapshots, orphan reconciliation, purge
   semantics, backup/restore, and worker schedule before real financial use.
6. Enable Render only with all production prerequisites validated; suppress
   request access logs containing OAuth authorization codes; use explicit
   environment variable configuration, no public secrets. Configure exact
   Supabase HTTPS callback after the real Render hostname is known.
7. Record smoke test, anonymous and non-owner denial, restart persistence,
   and regression evidence. Maintain rollback and recovery plan.

This PR prepares security components; it does not configure live hosting or
grant production approval. Existing test transactions and files stay unchanged.
