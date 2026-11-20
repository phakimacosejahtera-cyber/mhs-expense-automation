"""Owner authentication tests. No real Google/Supabase requests or data."""
import copy
import os
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from backend.app.owner_auth import (
    OwnerConfig, OwnerAuthError, authorize_url, new_verifier, exchange_owner,
)
from backend.app.runtime import require_local_app

CONFIG = OwnerConfig("https://example.supabase.co", "sb_publishable_test", "owner@example.com")
USER = {
    "id": "supabase-user-1", "email": "owner@example.com",
    "email_confirmed_at": "2026-01-01T00:00:00Z", "role": "authenticated",
    "is_anonymous": False,
    "identities": [{"provider": "google", "identity_data": {
        "email": "owner@example.com", "email_verified": True, "sub": "google-owner-1"
    }}],
}


def exchange(user, status=200):
    def handler(request):
        if request.url.path.endswith("/token"):
            assert request.url.params["grant_type"] == "pkce"
            return httpx.Response(200, json={"access_token": "mock-token"})
        assert request.headers["Authorization"] == "Bearer mock-token"
        return httpx.Response(status, json=user)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return exchange_owner(CONFIG, "test-code", new_verifier(), client)


def test_pkce_redirect():
    verifier = new_verifier()
    q = parse_qs(urlsplit(authorize_url(CONFIG, verifier)).query)
    assert q["provider"] == ["google"]
    assert q["redirect_to"] == [CONFIG.callback]
    assert q["code_challenge_method"] == ["s256"]
    assert len(q["code_challenge"][0]) == 43
    assert verifier not in authorize_url(CONFIG, verifier)


def test_owner_accepted():
    assert exchange(USER) == ("supabase-user-1", "google-owner-1")


@pytest.mark.parametrize("case", ["wrong_email", "unverified", "wrong_provider", "linked_email", "anonymous", "missing_id", "missing_sub", "provider_unavailable"])
def test_non_owner_rejected(case):
    user = copy.deepcopy(USER)
    if case == "wrong_email": user["email"] = "other@example.com"
    elif case == "unverified": user["identities"][0]["identity_data"]["email_verified"] = False
    elif case == "wrong_provider": user["identities"][0]["provider"] = "email"
    elif case == "linked_email": user["identities"].append({"provider": "email"})
    elif case == "anonymous": user["is_anonymous"] = True
    elif case == "missing_id": user.pop("id")
    elif case == "missing_sub": user["identities"][0]["identity_data"].pop("sub")
    with pytest.raises(OwnerAuthError):
        exchange(user, 503 if case == "provider_unavailable" else 200)


def test_callback_needs_verifier():
    with pytest.raises(OwnerAuthError):
        exchange_owner(CONFIG, "code", None)


def test_owner_test_mode_never_on_render():
    assert require_local_app({"MHS_MODE": "owner_test"}) == "owner_test"
    with pytest.raises(RuntimeError):
        require_local_app({"MHS_MODE": "owner_test", "RENDER": "true"})


def test_owner_routes_isolated_subprocess(tmp_path):
    # Isolate module imports and SQLite from other tests and actual user data.
    env = dict(os.environ, MHS_MODE="owner_test",
               MHS_SUPABASE_URL=CONFIG.url,
               MHS_SUPABASE_PUBLISHABLE_KEY=CONFIG.key,
               MHS_OWNER_EMAIL=CONFIG.email,
               MHS_TEST_TMP=str(tmp_path))
    env.pop("RENDER", None)
    env.pop("RENDER_SERVICE_ID", None)
    script = r"""
import os
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import main, db
from backend.app.owner_auth import OwnerAuthError

db.DATA = Path(os.environ["MHS_TEST_TMP"])
db.DB_FILE = db.DATA / "test.sqlite3"
main.DATA = db.DATA

def fake_exchange(config, code, verifier):
    if not verifier or code == "wrong":
        raise OwnerAuthError()
    return ("user-other" if code == "changed" else "user-owner", "google-owner")
main.exchange_owner = fake_exchange

with TestClient(main.app, follow_redirects=False) as c:
    assert c.get("/api/me").status_code == 401
    assert c.get("/api/dashboard").status_code == 401
    assert c.get("/api/receipts/fake").status_code == 401
    page = c.get("/").text
    assert "Masuk dengan Google" in page
    assert "AdminDemo123!" not in page
    assert c.post("/api/auth/login", json={"email":"admin@mhs.local","password":"AdminDemo123!"}).status_code == 403
    assert c.get("/api/auth/google/callback?code=ok").headers["location"] == "/?login=denied"
    assert c.get("/api/auth/google/start").status_code == 303
    assert c.get("/api/auth/google/callback?code=wrong").headers["location"] == "/?login=denied"
    assert c.get("/api/me").status_code == 401
    c.get("/api/auth/google/start")
    assert c.get("/api/auth/google/callback?code=ok").headers["location"] == "/"
    me = c.get("/api/me").json()
    assert me["email"] == "owner@example.com"
    assert c.get("/api/dashboard").status_code == 200
    assert c.post("/api/admin/users",headers={"X-CSRF-Token":me["csrf"]},json={"name":"Other","email":"other@example.com","password":"TestPassword123!"}).status_code == 403
    assert c.post("/api/auth/logout",headers={"X-CSRF-Token":me["csrf"]}).status_code == 200
    assert c.get("/api/me").status_code == 401
    c.get("/api/auth/google/start")
    assert c.get("/api/auth/google/callback?code=changed").headers["location"] == "/?login=denied"
    assert c.get("/api/me").status_code == 401
"""
    result = subprocess.run([sys.executable, "-c", script], env=env,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
