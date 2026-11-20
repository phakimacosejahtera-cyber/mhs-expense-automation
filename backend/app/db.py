"""Local SQLite development database; PostgreSQL production adapter planned.
Every financial write takes a BEGIN IMMEDIATE lock and writes an audit row in the same transaction.
"""
import sqlite3, os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import uuid, json

ROOT=Path(__file__).resolve().parents[2]
DATA = (ROOT/'storage'/'owner-auth-test' if os.getenv('MHS_MODE') == 'owner_test'
        else Path(os.getenv('MHS_DATA_DIR', str(ROOT/'storage'))))
if os.getenv('MHS_MODE') in ('pg_test','hosted_preview'):
    DATA = ROOT/'storage'/'postgres-test'
DATA.mkdir(parents=True,exist_ok=True)
DB_FILE=DATA/'mhs_expenses.sqlite3'

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid(): return str(uuid.uuid4())
def js(v): return json.dumps(v, ensure_ascii=False)

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,exc_type,exc,tb):
        try: return super().__exit__(exc_type,exc,tb)
        finally: self.close()

def using_postgres():
    return os.getenv('MHS_MODE') in ('pg_test','hosted_preview')

def connection():
    if using_postgres():
        from .postgres import connect
        return connect()
    conn=sqlite3.connect(DB_FILE,timeout=15,isolation_level=None,check_same_thread=False,factory=ClosingConnection)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn

@contextmanager
def tx():
    c=connection()
    if using_postgres():
        from .postgres import transaction
        try:
            with transaction(c):
                yield c
        finally:
            c.close()
        return
    try:
        c.execute('BEGIN IMMEDIATE')
        yield c
        c.commit()
    except Exception:
        c.rollback();raise
    finally: c.close()

def row_dict(row):
    # PostgreSQL SUM(bigint) returns numeric/Decimal. Keep integer monetary
    # totals rather than silently serializing them to floating point or strings.
    return {k: int(v) if isinstance(v, Decimal) and v==v.to_integral_value() else v
            for k,v in dict(row).items()}

def one(c,sql,params=()):
    r=c.execute(sql,params).fetchone();return row_dict(r) if r else None

def allrows(c,sql,params=()):return [row_dict(r) for r in c.execute(sql,params).fetchall()]

def audit(c,actor,action,kind,target,details=None):
    c.execute('INSERT INTO audit_logs(id,actor_id,action,target_type,target_id,details,created_at) VALUES (?,?,?,?,?,?,?)',
              (uid(),actor,action,kind,target,js(details or {}),now()))

def notify(c,who,kind,message,key=None):
    c.execute('INSERT OR IGNORE INTO notifications(id,user_id,type,message,dedup_key,created_at) VALUES (?,?,?,?,?,?)',
              (uid(),who,kind,message,key,now()))

def init_schema():
    if using_postgres():
        from .postgres import init_schema as init_pg_schema
        return init_pg_schema()
    c=connection()
    try:
        c.executescript('''
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
 provider TEXT NOT NULL,raw_json TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transactions(
 id TEXT PRIMARY KEY,document_id TEXT NOT NULL UNIQUE REFERENCES documents(id),
 batch_id TEXT NOT NULL REFERENCES upload_batches(id),uploader_id TEXT NOT NULL REFERENCES users(id),
 activity_id TEXT NOT NULL REFERENCES activities(id),category_id TEXT REFERENCES categories(id),
 transaction_date TEXT,amount_cents INTEGER CHECK(amount_cents IS NULL OR amount_cents>=0),
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
''')
    finally:c.close()
