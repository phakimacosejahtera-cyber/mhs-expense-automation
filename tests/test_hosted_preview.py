"""Offline hosted preview regression; no external calls or real credentials."""
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

from backend.app.runtime import require_local_app
from backend.app.receipt_storage import PrivateStorage, StorageError, configured_storage
from backend.app.hosted_preview import preview_database_options, verify_preview_role

ORIGIN="https://mhs-example.onrender.com"
PROJECT="example"
ENV={
    "RENDER":"true","RENDER_SERVICE_ID":"srv-mock","RENDER_EXTERNAL_URL":ORIGIN,
    "MHS_MODE":"hosted_preview","MHS_PREVIEW_ACK":"synthetic-only","MHS_STORAGE_MODE":"cloud_test",
    "MHS_PG_PREVIEW_DSN":"postgresql://mhs_preview_app.example:mock@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres",
    "MHS_PG_SSLROOTCERT":"mock-cert.crt","MHS_SUPABASE_URL":"https://example.supabase.co",
    "MHS_SUPABASE_PUBLISHABLE_KEY":"sb_publishable_mock","MHS_OWNER_EMAIL":"owner@example.com",
    "MHS_S3_ENDPOINT":"https://example.storage.supabase.co/storage/v1/s3","MHS_S3_REGION":"ap-southeast-2",
    "MHS_S3_ACCESS_KEY_ID":"a"*32,"MHS_S3_SECRET_ACCESS_KEY":"b"*64,
}


def test_explicit_preview_mode_only():
    assert require_local_app(ENV)=="hosted_preview"
    assert preview_database_options(ENV)["user"]=="mhs_preview_app.example"


@pytest.mark.parametrize("key,value",[
    ("RENDER","false"),("RENDER_SERVICE_ID",""),("RENDER_EXTERNAL_URL","http://mhs-example.onrender.com"),
    ("MHS_PUBLIC_ORIGIN","https://other.onrender.com"),("MHS_PREVIEW_ACK",""),("MHS_STORAGE_MODE","local"),
    ("MHS_PG_TEST_DSN","forbidden"),("MHS_PG_PROD_DSN","forbidden"),("DATABASE_URL","forbidden"),
    ("MHS_PG_SSLROOTCERT",""),("MHS_PG_PREVIEW_DSN","postgresql://postgres.example:x@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres"),
    ("MHS_PG_PREVIEW_DSN","postgresql://mhs_preview_app.other:x@aws-1-ap-southeast-2.pooler.supabase.com:5432/postgres"),
    ("MHS_PG_PREVIEW_DSN","postgresql://mhs_preview_app.example:x@evil.example:5432/postgres"),
    ("MHS_PG_PREVIEW_DSN","postgresql://mhs_preview_app.example:x@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres"),
])
def test_configuration_fails_closed(key,value):
    with pytest.raises(RuntimeError):
        require_local_app({**ENV,key:value})


def test_preview_cannot_fall_back_to_local_storage():
    with pytest.raises(StorageError):
        configured_storage("hosted_preview",{"MHS_STORAGE_MODE":"local"})


def test_preview_refuses_production_objects():
    s=PrivateStorage.from_env(ENV)
    s.client=Mock()
    s.client.list_objects_v2.side_effect=[{"KeyCount":0},{"KeyCount":1}]
    with pytest.raises(StorageError,match="empty"):
        s.check_preview_scope()


def test_role_privilege_guard():
    raw=Mock()
    safe_role={"name":"mhs_preview_app","rolsuper":False,"rolcreaterole":False,
               "rolcreatedb":False,"rolbypassrls":False,"rolreplication":False,"rolinherit":False}
    raw.execute.return_value.fetchone.side_effect=[
        safe_role,None,{"can_create":False,"can_change_identity":False,"can_change_audit":False,"can_delete_audit":False},None]
    verify_preview_role(raw)
    raw.execute.return_value.fetchone.side_effect=[{**safe_role,"rolbypassrls":True}]
    with pytest.raises(RuntimeError):
        verify_preview_role(raw)


def test_hosted_owner_routes_offline(tmp_path):
    env={k:v for k,v in os.environ.items() if not k.startswith(("MHS_","RENDER")) and k not in ("DATABASE_URL","SUPABASE_SERVICE_ROLE_KEY")}
    env.update(ENV,MHS_TMP=str(tmp_path))
    script=r"""
import os
from pathlib import Path
from unittest.mock import Mock
from fastapi.testclient import TestClient
from backend.app import db, receipt_storage
from backend.app.owner_auth import OwnerAuthError

db.DATA=Path(os.environ["MHS_TMP"])
db.DB_FILE=db.DATA/"preview-test.sqlite3"
db.using_postgres=lambda:False
storage=Mock()
receipt_storage.PrivateStorage.from_env=classmethod(lambda cls,env=None:storage)
from backend.app import main
main.DATA=db.DATA
db.init_schema()
with db.tx() as c:
    c.execute("CREATE TABLE owner_login_identity(singleton INTEGER PRIMARY KEY,supabase_id TEXT,google_sub TEXT)")
    c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",("owner","Owner","owner@example.com","unused","admin",1,db.now()))
    c.execute("INSERT INTO owner_login_identity VALUES(1,?,?)",("mock-owner","mock-google"))
    c.execute("INSERT INTO documents VALUES (?,?,?,?,?)",("doc","owner",None,"ver",db.now()))
    c.execute("INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?)",("ver","doc",1,"legacy.png","image/png","unused","legacy-local.png",100,db.now()))

def exchange(conf,code,verifier):
    if not verifier:raise OwnerAuthError()
    return ("wrong" if code=="bad" else "mock-owner","mock-google")
main.exchange_owner=exchange
origin=os.environ["RENDER_EXTERNAL_URL"]
with TestClient(main.app,base_url=origin,follow_redirects=False) as c:
    assert c.get("/api/health").json()["mode"].startswith("HOSTED PREVIEW")
    assert "DATA SIMULASI" in c.get("/").text
    assert c.get("/api/receipts/doc").status_code==401
    assert c.post("/api/batches",headers={"Origin":origin},json={}).status_code==401
    c.get("/api/auth/google/start")
    assert c.get("/api/auth/google/callback?code=bad").headers["location"]=="/?login=denied"
    c.get("/api/auth/google/start")
    result=c.get("/api/auth/google/callback?code=ok")
    assert result.headers["location"]=="/"
    assert any("secure" in h.lower() for h in result.headers.get_list("set-cookie") if h.startswith("mhs_session="))
    me=c.get("/api/me")
    assert me.status_code==200
    assert c.get("/api/receipts/doc").status_code==503
    assert c.post("/api/auth/logout",headers={"Origin":origin}).status_code==403
    assert c.post("/api/auth/logout",headers={"Origin":origin,"X-CSRF-Token":me.json()["csrf"]}).status_code==200
    assert c.get("/api/me").status_code==401
storage.check_private.assert_called_once()
storage.check_preview_scope.assert_called_once()
"""
    result=subprocess.run([sys.executable,"-c",script],env=env,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+result.stderr
