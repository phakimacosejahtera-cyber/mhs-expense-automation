"""Private receipt storage, opt-in local pg_test only.
S3 credentials are backend-only and project-wide; never use with real receipts.
"""
import hashlib
import os
import re
import uuid
from pathlib import Path

BUCKET = "receipts-test"
PREFIX = "supabase://" + BUCKET + "/"
MAX_BYTES = 8 * 1024 * 1024
TYPES = {".pdf":"application/pdf", ".png":"image/png", ".jpg":"image/jpeg", ".webp":"image/webp"}
KEY_PATTERN = re.compile(r"originals/[0-9a-f-]{36}\.(pdf|png|jpg|webp)")


class StorageError(RuntimeError):
    pass


def verify_bucket_metadata(project, env):
    # S3 has no GetBucketAcl implementation here. Read authoritative metadata
    # through our existing TLS-verified test DB connection, never modify it.
    from psycopg.conninfo import conninfo_to_dict
    from .postgres import connect
    try:
        if env.get("MHS_MODE") == "hosted_preview":
            from .hosted_preview import preview_database_options
            preview_database_options(env)
            with connect() as c:
                return c.raw.execute("SELECT id, public, file_size_limit, allowed_mime_types FROM mhs_owner_test.preview_bucket_metadata").fetchone()
        options = conninfo_to_dict(env.get("MHS_PG_TEST_DSN", ""))
        host, user = options.get("host", ""), options.get("user", "")
        direct = host == "db."+project+".supabase.co"
        pooled = host.endswith(".pooler.supabase.com") and user == "postgres."+project
        if not (direct or pooled):
            raise StorageError("Storage and test database project must match")
        with connect() as c:
            row = c.raw.execute(
                "SELECT id, public, file_size_limit, allowed_mime_types FROM storage.buckets WHERE id=%s",
                (BUCKET,)
            ).fetchone()
    except StorageError:
        raise
    except Exception:
        raise StorageError("Cannot verify test bucket metadata") from None
    return row


class PrivateStorage:
    def __init__(self, endpoint, region, access_id, secret, project_url, client=None, metadata_reader=None):
        match = re.fullmatch(r"https://([a-z0-9]+)\.storage\.supabase\.co/storage/v1/s3", endpoint)
        if not match or project_url != "https://"+match[1]+".supabase.co":
            raise StorageError("Invalid or mismatched Supabase S3 endpoint")
        if not re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]+", region):
            raise StorageError("Invalid S3 region")
        if not re.fullmatch(r"[a-fA-F0-9]{32}", access_id) or not re.fullmatch(r"[a-fA-F0-9]{64}", secret):
            raise StorageError("Invalid S3 credential format")
        self.project = match[1]
        self.url = project_url+"/storage/v1"
        self.metadata_reader = metadata_reader or (lambda: verify_bucket_metadata(self.project, os.environ))
        if client is None:
            import boto3
            from botocore.config import Config
            client = boto3.client("s3", endpoint_url=endpoint, region_name=region,
                aws_access_key_id=access_id, aws_secret_access_key=secret,
                config=Config(signature_version="s3v4", s3={"addressing_style":"path"},
                    connect_timeout=10, read_timeout=20,
                    retries={"total_max_attempts":2},
                    request_checksum_calculation="when_required",
                    response_checksum_validation="when_required"))
        self.client = client

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(env.get("MHS_S3_ENDPOINT","").rstrip("/"),
                   env.get("MHS_S3_REGION",""), env.get("MHS_S3_ACCESS_KEY_ID",""),
                   env.get("MHS_S3_SECRET_ACCESS_KEY",""),
                   env.get("MHS_SUPABASE_URL","").rstrip("/"))

    def check_private(self):
        row = self.metadata_reader()
        if not isinstance(row,dict) or row.get("id") != BUCKET or row.get("public") is not False:
            raise StorageError("Dedicated test bucket must exist and be private")
        size = row.get("file_size_limit")
        if not isinstance(size,int) or not 0<size<=MAX_BYTES or set(row.get("allowed_mime_types") or []) != set(TYPES.values()):
            raise StorageError("Test bucket limits must match receipt configuration")

    def check_preview_scope(self):
        # Project-wide S3 keys cannot enforce bucket isolation. This is an
        # additional startup guard, not a security boundary or ongoing monitor.
        try:
            self.client.list_objects_v2(Bucket=BUCKET,MaxKeys=1)
            result=self.client.list_objects_v2(Bucket="receipts-originals",MaxKeys=1)
            if result.get("KeyCount",0) or result.get("Contents"):
                raise StorageError("Production bucket must stay empty in single-project preview")
        except StorageError:
            raise
        except Exception:
            raise StorageError("Cannot verify synthetic-only S3 scope") from None

    def put(self,data,ext):
        if ext not in TYPES or not data or len(data)>MAX_BYTES:
            raise StorageError("Invalid receipt size or type")
        self.check_private()
        # New random key per immutable application version. No S3 versioning.
        key = "originals/"+str(uuid.uuid4())+ext
        try:
            self.client.put_object(Bucket=BUCKET, Key=key, Body=data,
                                   ContentType=TYPES[ext], CacheControl="no-store")
        except Exception:
            raise StorageError("S3 upload failed") from None
        return PREFIX+key

    @staticmethod
    def object_key(ref):
        if not isinstance(ref,str) or not ref.startswith(PREFIX):
            raise StorageError("Invalid storage reference")
        key = ref[len(PREFIX):]
        if KEY_PATTERN.fullmatch(key) is None:
            raise StorageError("Invalid object key")
        return key

    def read(self,ref,expected_sha256,expected_size):
        key = self.object_key(ref)
        if not isinstance(expected_size,int) or not 0<expected_size<=MAX_BYTES:
            raise StorageError("Invalid stored receipt size")
        self.check_private()
        data = bytearray()
        try:
            response = self.client.get_object(Bucket=BUCKET, Key=key)
            body = response["Body"]
            try:
                while True:
                    chunk = body.read(min(65536, expected_size+1-len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data)>expected_size:
                        raise StorageError("Receipt size mismatch")
            finally:
                body.close()
        except StorageError:
            raise
        except Exception:
            raise StorageError("S3 read failed") from None
        if len(data)!=expected_size or hashlib.sha256(data).hexdigest()!=expected_sha256:
            raise StorageError("Receipt integrity check failed")
        return bytes(data)

    def delete_test_object(self,ref):
        # Explicit live fixture cleanup only; no application auto-purge.
        self.check_private()
        key = self.object_key(ref)
        try:
            self.client.delete_object(Bucket=BUCKET, Key=key)
        except Exception:
            raise StorageError("S3 test cleanup failed") from None


def configured_storage(mode,env=None):
    env = os.environ if env is None else env
    setting = env.get("MHS_STORAGE_MODE","local")
    if mode == "hosted_preview" and setting != "cloud_test":
        raise StorageError("Hosted preview requires private cloud storage")
    if setting == "local":
        return None
    if setting != "cloud_test" or mode not in ("pg_test","hosted_preview"):
        raise StorageError("Cloud receipt test requires explicit pg_test mode")
    return PrivateStorage.from_env(env)


def legacy_local_path(ref,data_dir):
    folder = (Path(data_dir)/"private_docs").resolve()
    path = Path(ref).resolve()
    if path.parent != folder or not path.is_file():
        raise StorageError("Local receipt is missing or outside private directory")
    return path
