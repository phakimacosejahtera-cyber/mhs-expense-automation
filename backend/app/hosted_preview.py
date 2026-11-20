"""Explicit synthetic-only hosted preview configuration."""
import re
from .https_security import configured_public_origin

ROLE = "mhs_preview_app"
SCHEMA = "mhs_owner_test"
MODE = "hosted_preview"


def preview_origin(env):
    origin = configured_public_origin({"MHS_PUBLIC_ORIGIN":env.get("RENDER_EXTERNAL_URL","")})
    if not origin or (env.get("MHS_PUBLIC_ORIGIN") and env["MHS_PUBLIC_ORIGIN"] != origin):
        raise RuntimeError("Hosted preview requires matching Render HTTPS URL")
    return origin


def preview_database_options(env):
    from psycopg.conninfo import conninfo_to_dict
    url = env.get("MHS_SUPABASE_URL","").rstrip("/")
    match = re.fullmatch(r"https://([a-z0-9]+)\.supabase\.co",url)
    if not match:
        raise RuntimeError("Invalid preview project URL")
    project = match[1]
    try:
        opts = conninfo_to_dict(env.get("MHS_PG_PREVIEW_DSN",""))
    except Exception:
        raise RuntimeError("Invalid preview connection configuration") from None
    host = opts.get("host","")
    if (set(opts)-{"host","port","dbname","user","password"} or
        not re.fullmatch(r"aws-[0-9]+-[a-z0-9-]+\.pooler\.supabase\.com",host) or
        opts.get("port") != "5432" or opts.get("dbname") != "postgres" or
        opts.get("user") != ROLE+"."+project or not opts.get("password")):
        raise RuntimeError("Preview requires dedicated role and matching Supabase session pooler")
    return opts


def validate_preview(env):
    if env.get("RENDER","").lower().strip()!="true" or not env.get("RENDER_SERVICE_ID"):
        raise RuntimeError("Hosted preview requires Render")
    preview_origin(env)
    if env.get("MHS_PREVIEW_ACK")!="synthetic-only" or env.get("MHS_STORAGE_MODE")!="cloud_test":
        raise RuntimeError("Hosted preview must be explicitly synthetic-only with cloud test storage")
    for forbidden in ("MHS_PG_TEST_DSN","MHS_PG_PROD_DSN","MHS_STORAGE_TEST_SECRET","SUPABASE_SERVICE_ROLE_KEY","DATABASE_URL"):
        if env.get(forbidden):
            raise RuntimeError("Administrator/test/production credentials forbidden in preview")
    for key in ("MHS_PG_PREVIEW_DSN","MHS_PG_SSLROOTCERT","MHS_SUPABASE_URL",
                "MHS_SUPABASE_PUBLISHABLE_KEY","MHS_OWNER_EMAIL","MHS_S3_ENDPOINT",
                "MHS_S3_REGION","MHS_S3_ACCESS_KEY_ID","MHS_S3_SECRET_ACCESS_KEY"):
        if not env.get(key):
            raise RuntimeError("Missing hosted preview setting: "+key)
    preview_database_options(env)
    return MODE


def verify_preview_role(raw):
    row = raw.execute("""SELECT current_user AS name, rolsuper, rolcreaterole, rolcreatedb,
        rolbypassrls, rolreplication, rolinherit
        FROM pg_catalog.pg_roles WHERE rolname=current_user""").fetchone()
    if not row or row["name"]!=ROLE or any(row[k] for k in
        ("rolsuper","rolcreaterole","rolcreatedb","rolbypassrls","rolreplication","rolinherit")):
        raise RuntimeError("Unexpected preview database role")
    if raw.execute("""SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid=m.member WHERE r.rolname=current_user LIMIT 1""").fetchone():
        raise RuntimeError("Preview role must not inherit other roles")
    row = raw.execute("""SELECT has_schema_privilege(current_user,'mhs_owner_test','CREATE') AS can_create,
        has_table_privilege(current_user,'mhs_owner_test.owner_login_identity','UPDATE') AS can_change_identity,
        has_table_privilege(current_user,'mhs_owner_test.audit_logs','UPDATE') AS can_change_audit,
        has_table_privilege(current_user,'mhs_owner_test.audit_logs','DELETE') AS can_delete_audit""").fetchone()
    if not row or any(row.values()):
        raise RuntimeError("Preview role has excessive test-schema privileges")
    row=raw.execute("""SELECT 1 FROM pg_catalog.pg_namespace
        WHERE nspname='mhs_production' AND has_schema_privilege(current_user,oid,'USAGE')""").fetchone()
    if row:
        raise RuntimeError("Preview role can access production schema")
