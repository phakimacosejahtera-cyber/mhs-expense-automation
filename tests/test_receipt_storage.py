"""Offline storage adapter tests; opt in separately for real cloud test."""
import hashlib
import os

import httpx
import pytest

from backend.app.receipt_storage import (
    BUCKET, PREFIX, PrivateStorage, StorageError, configured_storage, legacy_local_path,
)

URL="https://example.supabase.co"
DATA=b"%PDF-1.4\n% MHS synthetic test only\n%%EOF\n"
DIGEST=hashlib.sha256(DATA).hexdigest()


def mocked(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_private_write_and_read():
    requests=[]
    def handler(r):
        requests.append(r)
        assert r.headers["apikey"]=="sb_secret_mock"
        if "/bucket/" in r.url.path:
            return httpx.Response(200,json={"id":BUCKET,"public":False})
        if r.method=="POST":
            assert r.headers["x-upsert"]=="false"
            assert r.headers["Content-Type"]=="application/pdf"
            assert r.content==DATA
            return httpx.Response(200,json={})
        assert "/object/authenticated/" in r.url.path
        return httpx.Response(200,content=DATA)
    with mocked(handler) as client:
        s=PrivateStorage(URL,"sb_secret_mock",client)
        ref=s.put(DATA,".pdf")
        assert ref.startswith(PREFIX)
        assert s.read(ref,DIGEST,len(DATA))==DATA
        assert len(requests)==4


def test_public_bucket_rejected():
    with mocked(lambda r: httpx.Response(200,json={"id":BUCKET,"public":True})) as client:
        with pytest.raises(StorageError,match="private"):
            PrivateStorage(URL,"sb_secret_mock",client).put(DATA,".pdf")


def test_mismatched_hash_rejected():
    def handler(r):
        if "/bucket/" in r.url.path:
            return httpx.Response(200,json={"id":BUCKET,"public":False})
        return httpx.Response(200,content=DATA)
    with mocked(handler) as client:
        s=PrivateStorage(URL,"sb_secret_mock",client)
        with pytest.raises(StorageError,match="integrity"):
            s.read(PREFIX+"originals/12345678-1234-1234-1234-123456789012.pdf","0"*64,len(DATA))


def test_bad_reference_rejected():
    for ref in ["https://example.com",PREFIX+"../secret.pdf", "supabase://receipts-originals/originals/file.pdf"]:
        with pytest.raises(StorageError):
            PrivateStorage.object_key(ref)


def test_explicit_mode_and_credentials():
    assert configured_storage("demo",{}) is None
    with pytest.raises(StorageError):
        configured_storage("demo",{"MHS_STORAGE_MODE":"cloud_test"})
    with pytest.raises(StorageError):
        configured_storage("pg_test",{"MHS_STORAGE_MODE":"cloud_test","MHS_SUPABASE_URL":URL,"MHS_STORAGE_TEST_SECRET":"sb_publishable_mock"})
    assert configured_storage("pg_test",{"MHS_STORAGE_MODE":"cloud_test","MHS_SUPABASE_URL":URL,"MHS_STORAGE_TEST_SECRET":"sb_secret_mock"}).url==URL+"/storage/v1"


def test_local_path_stays_private(tmp_path):
    folder=tmp_path/"private_docs"
    folder.mkdir()
    receipt=folder/"receipt.pdf"
    receipt.write_bytes(DATA)
    assert legacy_local_path(str(receipt),tmp_path)==receipt.resolve()
    outside=tmp_path/"outside.pdf"
    outside.write_bytes(DATA)
    with pytest.raises(StorageError):
        legacy_local_path(str(outside),tmp_path)


def test_storage_failure_is_sanitized():
    with mocked(lambda r: httpx.Response(403,text="sensitive provider details")) as client:
        with pytest.raises(StorageError,match=r"HTTP 403") as caught:
            PrivateStorage(URL,"sb_secret_mock",client).check_private()
        assert "sensitive" not in str(caught.value)


@pytest.mark.skipif(os.getenv("MHS_RUN_STORAGE_TESTS")!="1",reason="Opt in to dedicated private bucket test")
def test_live_private_bucket():
    s=PrivateStorage.from_env()
    ref=s.put(DATA,".pdf")
    try:
        assert s.read(ref,DIGEST,len(DATA))==DATA
        key=s.object_key(ref)
        publishable=os.environ.get("MHS_SUPABASE_PUBLISHABLE_KEY","")
        assert publishable.startswith("sb_publishable_")
        with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as anonymous:
            for route in ("public","authenticated"):
                for headers in ({},{"apikey":publishable}):
                    response=anonymous.get(s.url+"/object/"+route+"/"+BUCKET+"/"+key,headers=headers)
                    assert response.status_code in (400,401,403,404), "Unauthenticated object access not denied"
    finally:
        s.delete_test_object(ref)
