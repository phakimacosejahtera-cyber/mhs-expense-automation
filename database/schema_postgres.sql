-- PostgreSQL schema for isolated mhs_owner_test only. Run through adapter, not public SQL editor.
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
