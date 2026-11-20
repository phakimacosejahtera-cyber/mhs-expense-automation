"""Offline production-preparation tests. No external storage or DB credentials."""
import os
import subprocess
import sys

import pytest

from backend.app.https_security import configured_public_origin, owner_pin
from backend.app.runtime import require_local_app


ORIGIN = "https://mhs-example.onrender.com"


@pytest.mark.parametrize("origin", [
    "http://mhs-example.onrender.com",
    "https://mhs-example.onrender.com/",
    "https://mhs-example.onrender.com.evil.example",
    "https://user@mhs-example.onrender.com",
    "https://mhs-example.onrender.com?x=1",
    "https://mhs-example.onrender.com:443",
])
def test_reject_invalid_public_origin(origin):
    with pytest.raises(RuntimeError):
        configured_public_origin({"MHS_PUBLIC_ORIGIN":origin})


def test_origin_and_owner_pin():
    assert configured_public_origin({}) is None
    assert configured_public_origin({"MHS_PUBLIC_ORIGIN":ORIGIN}) == ORIGIN
    assert owner_pin({}) is None
    with pytest.raises(RuntimeError):
        owner_pin({"MHS_OWNER_SUPABASE_ID":"missing-other"})
    assert owner_pin({"MHS_OWNER_SUPABASE_ID":"12345678-1234-1234-1234-123456789012",
                      "MHS_OWNER_GOOGLE_SUB":"123456789"}) == (
                          "12345678-1234-1234-1234-123456789012","123456789")


def test_render_still_blocked():
    for mode in ("demo","owner_test","pg_test","production"):
        with pytest.raises(RuntimeError):
            require_local_app({"MHS_MODE":mode,"RENDER":"true","MHS_PUBLIC_ORIGIN":ORIGIN})


def test_https_owner_flow_and_boundaries(tmp_path):
    env = dict(os.environ, MHS_MODE="owner_test", MHS_STORAGE_MODE="local",
               MHS_SUPABASE_URL="https://example.supabase.co",
               MHS_SUPABASE_PUBLISHABLE_KEY="sb_publishable_mock",
               MHS_OWNER_EMAIL="owner@example.com", MHS_PUBLIC_ORIGIN=ORIGIN,
               MHS_OWNER_SUPABASE_ID="12345678-1234-1234-1234-123456789012",
               MHS_OWNER_GOOGLE_SUB="123456789", MHS_TEST_TMP=str(tmp_path))
    env.pop("RENDER",None)
    env.pop("RENDER_SERVICE_ID",None)
    script = r"""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from fastapi.testclient import TestClient
from backend.app import main, db
from backend.app.owner_auth import OwnerAuthError

db.DATA=Path(os.environ["MHS_TEST_TMP"])
db.DB_FILE=db.DATA/"security.sqlite3"
main.DATA=db.DATA

def fake_exchange(config,code,verifier):
    if not verifier:
        raise OwnerAuthError()
    if code=="wrong":
        return ("wrong-id",config.pin[1])
    return config.pin

main.exchange_owner=fake_exchange
origin=os.environ["MHS_PUBLIC_ORIGIN"]
with TestClient(main.app,base_url=origin,follow_redirects=False) as c:
    assert c.get("/api/dashboard").status_code==401
    assert "no-store" in c.get("/api/dashboard").headers["cache-control"]
    assert c.get("/docs").status_code==404
    assert c.get("/openapi.json").status_code==404
    assert c.get("/",headers={"Host":"evil.example"}).status_code==400
    start=c.get("/api/auth/google/start")
    assert start.status_code==303
    assert parse_qs(urlsplit(start.headers["location"]).query)["redirect_to"]==[origin+"/api/auth/google/callback"]
    cookie=start.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert c.get("/api/auth/google/callback?code=wrong").headers["location"]=="/?login=denied"
    assert c.get("/api/me").status_code==401
    c.get("/api/auth/google/start")
    ok=c.get("/api/auth/google/callback?code=ok")
    assert ok.headers["location"]=="/"
    session=[v.lower() for v in ok.headers.get_list("set-cookie") if v.startswith("mhs_session=")][0]
    assert "secure" in session and "httponly" in session and "samesite=strict" in session
    me=c.get("/api/me")
    assert me.status_code==200
    assert me.headers["strict-transport-security"]=="max-age=31536000"
    assert me.headers["x-frame-options"]=="SAMEORIGIN"
    assert me.headers["x-content-type-options"]=="nosniff"
    assert c.get("/api/dashboard").status_code==200
    csrf=me.json()["csrf"]
    assert c.post("/api/auth/logout",headers={"X-CSRF-Token":csrf}).status_code==403
    assert c.post("/api/auth/logout",headers={"Origin":"https://evil.example","X-CSRF-Token":csrf}).status_code==403
    assert c.post("/api/auth/logout",headers={"Origin":origin}).status_code==403
    assert c.post("/api/auth/logout",headers={"Origin":origin,"X-CSRF-Token":csrf}).status_code==200
    assert c.get("/api/me").status_code==401
"""
    result=subprocess.run([sys.executable,"-c",script],env=env,capture_output=True,text=True,timeout=45)
    assert result.returncode==0,result.stdout+result.stderr
