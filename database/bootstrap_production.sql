-- Production bootstrap candidate; run ONLY in a dedicated empty production Supabase project.
-- Never run in the existing test project. Do not execute until reviewed.
-- As project administrator, execute once in a transaction. No password is embedded.
-- The app role remains NOLOGIN until explicitly provisioned with a separate secret.
BEGIN;
CREATE ROLE mhs_prod_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS NOREPLICATION;
CREATE SCHEMA mhs_production;
REVOKE ALL ON SCHEMA mhs_production FROM PUBLIC, anon, authenticated, service_role;
SET LOCAL search_path TO mhs_production, pg_catalog;

CREATE TABLE IF NOT EXISTS users(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','uploader')),
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
 id_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activities(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE'
 CHECK(status IN ('ACTIVE','COMPLETED','ARCHIVED')),
 closure_status TEXT NOT NULL DEFAULT 'OPEN' CHECK(closure_status IN ('OPEN','CLOSED')),
 closed_at TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS upload_batches(
 id TEXT PRIMARY KEY,uploader_id TEXT NOT NULL REFERENCES users(id),
 activity_id TEXT NOT NULL REFERENCES activities(id),status TEXT NOT NULL DEFAULT 'PROCESSING',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY,owner_id TEXT NOT NULL REFERENCES users(id),batch_id TEXT REFERENCES upload_batches(id),
 active_version_id TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_versions(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id), version_number INTEGER NOT NULL,
 filename TEXT NOT NULL,media_type TEXT NOT NULL,sha256 TEXT NOT NULL,storage_path TEXT NOT NULL,
 file_size INTEGER NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(document_id,version_number));
CREATE TABLE IF NOT EXISTS extraction_runs(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),status TEXT NOT NULL,
 provider TEXT NOT NULL,raw_json TEXT,created_at TEXT NOT NULL,
 extraction_seq BIGINT GENERATED ALWAYS AS IDENTITY);
CREATE TABLE IF NOT EXISTS transactions(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL UNIQUE REFERENCES documents(id),
 batch_id TEXT NOT NULL REFERENCES upload_batches(id),uploader_id TEXT NOT NULL REFERENCES users(id),
 activity_id TEXT NOT NULL REFERENCES activities(id),category_id TEXT REFERENCES categories(id),
 transaction_date TEXT,amount_cents BIGINT CHECK(amount_cents IS NULL OR amount_cents>=0),
 currency TEXT NOT NULL DEFAULT 'IDR',description TEXT,vendor TEXT,payment_method TEXT,invoice_number TEXT,notes TEXT,
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SUBMITTED','PENDING_REVIEW','APPROVED','REJECTED','REVERSED')),
 revision INTEGER NOT NULL DEFAULT 1,risk_reasons TEXT NOT NULL DEFAULT '[]',is_late INTEGER NOT NULL DEFAULT 0,
 late_reason TEXT,approved_at TEXT,approved_by TEXT REFERENCES users(id),
 rejected_reason TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,submitted_at TEXT,
 deleted_at TEXT,purge_at TEXT);
CREATE TABLE IF NOT EXISTS correction_requests(
 id TEXT PRIMARY KEY,transaction_id TEXT NOT NULL REFERENCES transactions(id),
 requester_id TEXT NOT NULL REFERENCES users(id),status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
 reason TEXT NOT NULL,proposed_json TEXT NOT NULL,replacement_version_id TEXT REFERENCES document_versions(id),
 reviewer_id TEXT REFERENCES users(id),decision_reason TEXT,created_at TEXT NOT NULL,decided_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_correction ON correction_requests(transaction_id) WHERE status='PENDING';
CREATE TABLE IF NOT EXISTS reinstatement_requests(
 id TEXT PRIMARY KEY,transaction_id TEXT NOT NULL REFERENCES transactions(id),requester_id TEXT NOT NULL REFERENCES users(id),
 status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
 reason TEXT NOT NULL,assignment_stage TEXT NOT NULL DEFAULT 'PRIMARY',sla_status TEXT NOT NULL,
 calendar_quality TEXT NOT NULL,due_at TEXT,provisional_due_at TEXT,next_reminder_at TEXT,
 reminder_seq INTEGER NOT NULL DEFAULT 0,snoozed_at TEXT,snooze_until TEXT,snooze_reason TEXT,
 calendar_version INTEGER NOT NULL DEFAULT 1,assigned_reviewer_id TEXT REFERENCES users(id),
 reviewer_id TEXT REFERENCES users(id),decision_reason TEXT,created_at TEXT NOT NULL,decided_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_reinstate ON reinstatement_requests(transaction_id) WHERE status='PENDING';
CREATE TABLE IF NOT EXISTS audit_logs(
 id TEXT PRIMARY KEY,actor_id TEXT,action TEXT NOT NULL,target_type TEXT NOT NULL,
 target_id TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),type TEXT NOT NULL,
 message TEXT NOT NULL,dedup_key TEXT UNIQUE,created_at TEXT NOT NULL,read_at TEXT);
CREATE TABLE IF NOT EXISTS export_logs(
 id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),scope TEXT NOT NULL,
 filters TEXT NOT NULL,storage_path TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calendar_versions(
 id TEXT PRIMARY KEY, version INTEGER NOT NULL UNIQUE,verified INTEGER NOT NULL,
 timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta',hours_json TEXT NOT NULL,
 holidays_json TEXT NOT NULL,source TEXT NOT NULL,created_at TEXT NOT NULL,published_at TEXT);
CREATE TABLE IF NOT EXISTS holiday_import_batches(
 id TEXT PRIMARY KEY,status TEXT NOT NULL,year_start INTEGER NOT NULL,year_end INTEGER NOT NULL,
 entries_json TEXT NOT NULL,source TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,published_at TEXT);
CREATE TABLE IF NOT EXISTS background_jobs(
 id TEXT PRIMARY KEY,kind TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_trans_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_trans_owner ON transactions(uploader_id);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type,target_id);

CREATE TABLE IF NOT EXISTS owner_login_identity (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 supabase_id TEXT NOT NULL, google_sub TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_settings (
 key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE upload_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE reinstatement_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE export_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE holiday_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE background_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE owner_login_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;


-- Application role cannot create or alter tables, or truncate data.
REVOKE ALL ON ALL TABLES IN SCHEMA mhs_production FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA mhs_production FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA mhs_production TO mhs_prod_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions, activities, categories, upload_batches, documents, document_versions, extraction_runs, transactions, correction_requests, reinstatement_requests, notifications, calendar_versions, holiday_import_batches, background_jobs, owner_login_identity, app_settings TO mhs_prod_app;
GRANT SELECT, INSERT ON audit_logs, export_logs TO mhs_prod_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA mhs_production TO mhs_prod_app;
CREATE POLICY app_users ON users FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_sessions ON sessions FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_activities ON activities FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_categories ON categories FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_upload_batches ON upload_batches FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_documents ON documents FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_document_versions ON document_versions FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_extraction_runs ON extraction_runs FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_transactions ON transactions FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_correction_requests ON correction_requests FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_reinstatement_requests ON reinstatement_requests FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_notifications ON notifications FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_calendar_versions ON calendar_versions FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_holiday_import_batches ON holiday_import_batches FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_background_jobs ON background_jobs FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_owner_login_identity ON owner_login_identity FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_app_settings ON app_settings FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_audit_logs ON audit_logs FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);
CREATE POLICY app_export_logs ON export_logs FOR ALL TO mhs_prod_app USING (true) WITH CHECK (true);

-- Only expose metadata of the intended receipt bucket, never broad storage table grants.
CREATE VIEW receipt_bucket_metadata WITH (security_barrier = true) AS
    SELECT id, public, file_size_limit, allowed_mime_types
    FROM storage.buckets WHERE id = 'receipts-originals';
REVOKE ALL ON receipt_bucket_metadata FROM PUBLIC, anon, authenticated, service_role;
GRANT SELECT ON receipt_bucket_metadata TO mhs_prod_app;

ALTER ROLE mhs_prod_app SET search_path TO pg_catalog, mhs_production, pg_temp;
COMMIT;

-- Explicitly separate credential provisioning from this tracked migration.
-- Do not put passwords in source control, screenshots, SQL logs or shell history.
-- This script does not enable the application or migrate any test transaction.
