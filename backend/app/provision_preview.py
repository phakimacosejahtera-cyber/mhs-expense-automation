"""Local, one-time bootstrap for the existing synthetic Supabase test schema.
Never run this in Render. Administrator DSN remains on the operator's computer.
Successful output is placed in clipboard, not printed, on Windows.
"""
import os
import re
import secrets
import subprocess
import sys
from urllib.parse import quote

from .hosted_preview import ROLE, preview_database_options, verify_preview_role
from .postgres import connect, transaction
from .receipt_storage import PrivateStorage, BUCKET
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

MUTABLE = ("sessions","activities","categories","upload_batches","documents","document_versions",
           "extraction_runs","transactions","correction_requests","reinstatement_requests",
           "notifications","calendar_versions","holiday_import_batches","app_settings")
APPEND = ("audit_logs","export_logs")
READ = ("users","owner_login_identity")


def setup():
    if sys.platform!="win32" or os.environ.get("MHS_MODE")!="pg_test" or os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        raise RuntimeError("Run bootstrap locally on Windows in pg_test mode")
    if os.getenv("MHS_PREVIEW_ACK")!="synthetic-only":
        raise RuntimeError("Explicit synthetic-only acknowledgement required")
    url=os.environ.get("MHS_SUPABASE_URL","").rstrip("/")
    project=re.fullmatch(r"https://([a-z0-9]+)\.supabase\.co",url)
    opts=conninfo_to_dict(os.environ["MHS_PG_TEST_DSN"])
    host=opts.get("host","")
    if (not project or not re.fullmatch(r"aws-[0-9]+-[a-z0-9-]+\.pooler\.supabase\.com",host)
        or opts.get("port")!="5432" or opts.get("user")!="postgres."+project[1] or opts.get("dbname")!="postgres"):
        raise RuntimeError("Expected the existing Supabase test session-pooler administrator connection")
    storage=PrivateStorage.from_env()
    storage.check_private()
    storage.client.list_objects_v2(Bucket=BUCKET,MaxKeys=1)
    # This bucket must stay empty throughout the single-project preview.
    if storage.client.list_objects_v2(Bucket="receipts-originals",MaxKeys=1).get("KeyCount",0):
        raise RuntimeError("Production bucket is not empty; use a separate project")
    password=secrets.token_urlsafe(36)
    dsn="postgresql://"+ROLE+"."+project[1]+":"+quote(password,safe="")+"@"+host+":5432/postgres"
    values={"MHS_MODE":"hosted_preview","MHS_PREVIEW_ACK":"synthetic-only","MHS_STORAGE_MODE":"cloud_test",
            "MHS_PG_PREVIEW_DSN":dsn,"MHS_PG_SSLROOTCERT":"/etc/secrets/prod-ca-2021.crt",
            **{k:os.environ[k] for k in ("MHS_SUPABASE_URL","MHS_SUPABASE_PUBLISHABLE_KEY","MHS_OWNER_EMAIL","MHS_S3_ENDPOINT","MHS_S3_REGION","MHS_S3_ACCESS_KEY_ID","MHS_S3_SECRET_ACCESS_KEY")}}
    preview_database_options(values)
    if any(not v or "\n" in v or "\r" in v for v in values.values()):
        raise RuntimeError("Missing or invalid preview settings")
    with connect() as c:
        with transaction(c):
            raw=c.raw
            owner=raw.execute("SELECT email,role,active FROM mhs_owner_test.users").fetchall()
            binding=raw.execute("SELECT supabase_id,google_sub FROM mhs_owner_test.owner_login_identity WHERE singleton=1").fetchone()
            if (len(owner)!=1 or owner[0]["role"]!="admin" or not owner[0]["active"]
                or owner[0]["email"]!=values["MHS_OWNER_EMAIL"].strip().lower() or not binding):
                raise RuntimeError("Existing owner binding must be verified locally first")
            if raw.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s",(ROLE,)).fetchone():
                raise RuntimeError("Preview role already exists; do not overwrite credentials")
            verifier=raw.pgconn.encrypt_password(password.encode("ascii"),ROLE.encode("ascii"),b"scram-sha-256").decode("ascii")
            raw.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS NOREPLICATION PASSWORD {}").format(sql.Identifier(ROLE),sql.Literal(verifier)))
            role=sql.Identifier(ROLE)
            raw.execute(sql.SQL("GRANT USAGE ON SCHEMA mhs_owner_test TO {}").format(role))
            for table in MUTABLE+APPEND+READ:
                ident=sql.Identifier("mhs_owner_test",table)
                # All tables already have RLS; explicitly refuse an unexpected schema.
                row=raw.execute("SELECT relrowsecurity FROM pg_catalog.pg_class WHERE oid=to_regclass(%s)",("mhs_owner_test."+table,)).fetchone()
                if not row or not row["relrowsecurity"]:
                    raise RuntimeError("Test schema RLS missing")
                privileges="SELECT, INSERT, UPDATE, DELETE" if table in MUTABLE else ("SELECT, INSERT" if table in APPEND else "SELECT")
                raw.execute(sql.SQL("GRANT "+privileges+" ON {} TO {}").format(ident,role))
                raw.execute(sql.SQL("CREATE POLICY {} ON {} FOR ALL TO {} USING (true) WITH CHECK (true)").format(sql.Identifier("preview_"+table),ident,role))
            raw.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA mhs_owner_test TO {}").format(role))
            raw.execute("""CREATE VIEW mhs_owner_test.preview_bucket_metadata WITH (security_barrier=true) AS
                         SELECT id, public, file_size_limit, allowed_mime_types FROM storage.buckets WHERE id='receipts-test'""")
            raw.execute("REVOKE ALL ON mhs_owner_test.preview_bucket_metadata FROM PUBLIC, anon, authenticated, service_role")
            raw.execute(sql.SQL("GRANT SELECT ON mhs_owner_test.preview_bucket_metadata TO {}").format(role))
            raw.execute(sql.SQL("ALTER ROLE {} SET search_path TO pg_catalog, mhs_owner_test, pg_temp").format(role))
            # If clipboard transfer fails, roll back role creation. If commit fails,
            # the copied credential block is invalid and must not be used.
            payload="\n".join(k+"="+v for k,v in values.items())
            subprocess.run(["powershell.exe","-NoProfile","-Command","$input | Set-Clipboard"],input=payload,text=True,check=True,capture_output=True)
    # Check the actual restricted login after the creation transaction commits.
    with psycopg.connect(dsn,sslmode="verify-full",
            sslrootcert=os.environ["MHS_PG_SSLROOTCERT"],connect_timeout=10,
            autocommit=True,row_factory=dict_row) as raw:
        raw.execute("SET search_path TO pg_catalog, mhs_owner_test, pg_temp")
        verify_preview_role(raw)
        if not raw.execute("SELECT id FROM mhs_owner_test.preview_bucket_metadata WHERE public=false").fetchone():
            raise RuntimeError("Restricted login cannot verify private storage")
        if not raw.execute("SELECT singleton FROM mhs_owner_test.owner_login_identity WHERE singleton=1").fetchone():
            raise RuntimeError("Restricted login cannot read owner binding")
    print("PREVIEW ROLE CREATED AND VERIFIED; Render environment block copied to clipboard.")
    print("Paste ONLY into Render Add from .env; do not paste into terminal or chat.")
    print("Add certificate secret file prod-ca-2021.crt separately.")


if __name__=="__main__":
    try:
        setup()
    except KeyError:
        print("Missing local environment setting. No credentials printed.",file=sys.stderr)
        sys.exit(1)
    except Exception:
        print("Preview preparation failed. Check local configuration and role existence; no credentials printed.",file=sys.stderr)
        sys.exit(1)
