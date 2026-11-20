"""PostgreSQL adapter for the isolated owner test. No production writes."""
import os
from contextlib import contextmanager
from pathlib import Path

SCHEMA = "mhs_owner_test"
LOCK_ID = 724632611307
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "database" / "schema_postgres.sql"


def translate_sql(sql):
    # Only trusted SQL templates from the application, never user-supplied SQL.
    if sql.startswith("INSERT OR IGNORE INTO notifications"):
        sql = sql.replace("INSERT OR IGNORE", "INSERT", 1) + " ON CONFLICT (dedup_key) DO NOTHING"
    sql = sql.replace("rowid DESC", "extraction_seq DESC")
    return sql.replace("%", "%%").replace("?", "%s")


class PostgresConnection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        return self.raw.execute(translate_sql(sql), tuple(params))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.raw.close()


def connect():
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict

    preview = os.getenv("MHS_MODE") == "hosted_preview"
    if preview:
        from .hosted_preview import preview_database_options, verify_preview_role
        preview_database_options(os.environ)
    dsn = os.environ.get("MHS_PG_PREVIEW_DSN" if preview else "MHS_PG_TEST_DSN", "")
    if not dsn:
        raise RuntimeError("MHS_PG_TEST_DSN is required in pg_test mode.")
    try:
        options = conninfo_to_dict(dsn)
        host = options.get("host", "")
        if not (host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")):
            raise ValueError("Unexpected host")
        if options.get("hostaddr") or "," in host or options.get("service"):
            raise ValueError("Unexpected connection routing")
        raw = psycopg.connect(dsn, sslmode="verify-full",
                             sslrootcert=os.environ.get("MHS_PG_SSLROOTCERT", "system"),
                             connect_timeout=10, autocommit=True,
                             row_factory=dict_row)
    except (psycopg.Error, ValueError):
        raise RuntimeError("Cannot connect to Supabase test database. Check TLS, host and credentials locally.") from None
    try:
        raw.execute("SET search_path TO pg_catalog, mhs_owner_test, pg_temp" if preview else "SET search_path TO mhs_owner_test, pg_catalog")
        if preview:
            verify_preview_role(raw)
        raw.execute("SET lock_timeout TO '10s'")
        raw.execute("SET statement_timeout TO '30s'")
    except Exception:
        raw.close()
        raise
    return PostgresConnection(raw)


@contextmanager
def transaction(connection):
    with connection.raw.transaction():
        # Preserve SQLite BEGIN IMMEDIATE's single-writer semantics.
        # Every application write must use this same transaction helper.
        connection.raw.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
        yield connection


def init_schema():
    if os.getenv("MHS_MODE") == "hosted_preview":
        # Never migrate or seed from hosted runtime. Local setup owns DDL.
        with connect() as c:
            c.raw.execute("SELECT 1 FROM mhs_owner_test.users LIMIT 1")
        return
    with connect() as c:
        with transaction(c):
            c.raw.execute("CREATE SCHEMA IF NOT EXISTS mhs_owner_test")
            c.raw.execute("REVOKE ALL ON SCHEMA mhs_owner_test FROM PUBLIC, anon, authenticated")
            # Restrict new objects to this explicitly isolated schema.
            c.raw.execute("SET LOCAL search_path TO mhs_owner_test, pg_catalog")
            for statement in SCHEMA_FILE.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    c.raw.execute(statement)
            c.raw.execute("REVOKE ALL ON ALL TABLES IN SCHEMA mhs_owner_test FROM PUBLIC, anon, authenticated")
            c.raw.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA mhs_owner_test FROM PUBLIC, anon, authenticated")
