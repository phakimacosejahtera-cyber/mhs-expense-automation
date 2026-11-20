"""Private receipt storage, opt-in local pg_test only.
No public or signed URLs are returned. Never expose backend credentials.
"""
import hashlib
import os
import re
import uuid
from pathlib import Path

import httpx

BUCKET = "receipts-test"
PREFIX = "supabase://" + BUCKET + "/"
MAX_BYTES = 8 * 1024 * 1024
TYPES = {".pdf":"application/pdf", ".png":"image/png", ".jpg":"image/jpeg", ".webp":"image/webp"}
KEY_PATTERN = re.compile(r"originals/[0-9a-f-]{36}\.(pdf|png|jpg|webp)")


class StorageError(RuntimeError):
    pass


class PrivateStorage:
    def __init__(self, url, secret, client=None):
        if not re.fullmatch(r"https://[a-z0-9]+\.supabase\.co", url):
            raise StorageError("Invalid Supabase storage URL")
        if not secret.startswith("sb_secret_"):
            raise StorageError("Storage test requires a backend secret API key")
        self.url = url + "/storage/v1"
        self.headers = {"apikey":secret}
        self.client = client

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("MHS_SUPABASE_URL","").rstrip("/"),
                   os.environ.get("MHS_STORAGE_TEST_SECRET",""))

    def request(self, method, path, **kwargs):
        try:
            if self.client is not None:
                result = self.client.request(method,self.url+path,
                    headers={**self.headers, **kwargs.pop("headers",{})},**kwargs)
            else:
                with httpx.Client(timeout=30,follow_redirects=False,trust_env=False) as client:
                    result = client.request(method,self.url+path,
                        headers={**self.headers, **kwargs.pop("headers",{})},**kwargs)
            if not result.is_success:
                raise StorageError("Storage request failed (HTTP %d)" % result.status_code)
            return result
        except httpx.HTTPError:
            raise StorageError("Storage connection failed") from None

    def check_private(self):
        try:
            bucket = self.request("GET","/bucket/"+BUCKET).json()
        except ValueError:
            raise StorageError("Invalid bucket response") from None
        if not isinstance(bucket,dict) or bucket.get("id") != BUCKET or bucket.get("public") is not False:
            raise StorageError("Dedicated test bucket must exist and be private")

    def put(self,data,ext):
        if ext not in TYPES or not data or len(data)>MAX_BYTES:
            raise StorageError("Invalid receipt size or type")
        self.check_private()
        key = "originals/"+str(uuid.uuid4())+ext
        self.request("POST","/object/"+BUCKET+"/"+key,content=data,
                     headers={"Content-Type":TYPES[ext],"x-upsert":"false","Cache-Control":"no-store"})
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
        # Stream with a hard size bound; do not trust Content-Length.
        try:
            with httpx.Client(timeout=30,follow_redirects=False,trust_env=False) as default:
                client = self.client or default
                with client.stream("GET",self.url+"/object/authenticated/"+BUCKET+"/"+key,
                                   headers={**self.headers,"Cache-Control":"no-cache"}) as r:
                    if not r.is_success:
                        raise StorageError("Storage read failed (HTTP %d)" % r.status_code)
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        data.extend(chunk)
                        if len(data)>expected_size:
                            raise StorageError("Receipt size mismatch")
        except httpx.HTTPError:
            raise StorageError("Storage connection failed") from None
        if len(data)!=expected_size or hashlib.sha256(data).hexdigest()!=expected_sha256:
            raise StorageError("Receipt integrity check failed")
        return bytes(data)

    def delete_test_object(self,ref):
        # Used by the explicit live fixture cleanup, NOT by the application.
        self.request("DELETE","/object/"+BUCKET,json={"prefixes":[self.object_key(ref)]})


def configured_storage(mode,env=None):
    env = os.environ if env is None else env
    setting = env.get("MHS_STORAGE_MODE","local")
    if setting == "local":
        return None
    if setting != "cloud_test" or mode != "pg_test":
        raise StorageError("Cloud receipt test requires explicit pg_test mode")
    return PrivateStorage(env.get("MHS_SUPABASE_URL","").rstrip("/"),
                          env.get("MHS_STORAGE_TEST_SECRET",""))


def legacy_local_path(ref,data_dir):
    folder = (Path(data_dir)/"private_docs").resolve()
    path = Path(ref).resolve()
    if path.parent != folder or not path.is_file():
        raise StorageError("Local receipt is missing or outside private directory")
    return path
