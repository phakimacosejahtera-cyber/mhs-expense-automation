"""Offline S3 adapter tests and opt-in live synthetic object test."""
import hashlib
import io
import os
from unittest.mock import Mock

import httpx
import pytest

from backend.app.receipt_storage import (
    BUCKET, PREFIX, MAX_BYTES, TYPES, PrivateStorage, StorageError,
    configured_storage, legacy_local_path,
)

URL="https://example.supabase.co"
ENDPOINT="https://example.storage.supabase.co/storage/v1/s3"
DATA=b"%PDF-1.4\n% MHS synthetic test only\n%%EOF\n"
DIGEST=hashlib.sha256(DATA).hexdigest()
REF=PREFIX+"originals/12345678-1234-1234-1234-123456789012.pdf"


def metadata():
    return {"id":BUCKET,"public":False,"file_size_limit":MAX_BYTES,
            "allowed_mime_types":list(TYPES.values())}


def adapter(client=None, reader=metadata):
    return PrivateStorage(ENDPOINT,"ap-southeast-2","a"*32,"b"*64,URL,
                          client=client or Mock(),metadata_reader=reader)


def test_private_write_and_read():
    client=Mock()
    client.get_object.return_value={"Body":io.BytesIO(DATA)}
    s=adapter(client)
    ref=s.put(DATA,".pdf")
    key=s.object_key(ref)
    client.put_object.assert_called_once_with(Bucket=BUCKET,Key=key,Body=DATA,
                                          ContentType="application/pdf",CacheControl="no-store")
    assert s.read(ref,DIGEST,len(DATA))==DATA
    client.get_object.assert_called_once_with(Bucket=BUCKET,Key=key)


def test_public_bucket_rejected():
    client=Mock()
    with pytest.raises(StorageError,match="private"):
        adapter(client,lambda:{**metadata(),"public":True}).put(DATA,".pdf")
    client.put_object.assert_not_called()


def test_mismatched_hash_rejected():
    client=Mock()
    client.get_object.return_value={"Body":io.BytesIO(DATA)}
    with pytest.raises(StorageError,match="integrity"):
        adapter(client).read(REF,"0"*64,len(DATA))


def test_oversized_object_read_rejected_and_closed():
    client=Mock()
    body=io.BytesIO(DATA+b"x")
    client.get_object.return_value={"Body":body}
    with pytest.raises(StorageError,match="size"):
        adapter(client).read(REF,DIGEST,len(DATA))
    assert body.closed


def test_bad_reference_rejected():
    for ref in ["https://example.com",PREFIX+"../secret.pdf","supabase://receipts-originals/originals/file.pdf"]:
        with pytest.raises(StorageError):
            PrivateStorage.object_key(ref)


def test_explicit_mode_and_credentials():
    assert configured_storage("demo",{}) is None
    with pytest.raises(StorageError):
        configured_storage("demo",{"MHS_STORAGE_MODE":"cloud_test"})
    with pytest.raises(StorageError):
        configured_storage("pg_test",{"MHS_STORAGE_MODE":"cloud_test"})
    with pytest.raises(StorageError):
        PrivateStorage(ENDPOINT,"ap-southeast-2","a"*32,"wrong",URL,client=Mock())
    with pytest.raises(StorageError):
        PrivateStorage(ENDPOINT,"ap-southeast-2","a"*32,"b"*64,"https://other.supabase.co",client=Mock())


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
    client=Mock()
    client.put_object.side_effect=RuntimeError("sensitive provider details")
    with pytest.raises(StorageError,match="S3 upload failed") as caught:
        adapter(client).put(DATA,".pdf")
    assert "sensitive" not in str(caught.value)


def test_bad_bucket_limits_rejected():
    with pytest.raises(StorageError,match="limits"):
        adapter(reader=lambda:{**metadata(),"file_size_limit":MAX_BYTES+1}).check_private()


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
