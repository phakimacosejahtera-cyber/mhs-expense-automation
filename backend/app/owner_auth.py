"""Server-side Supabase Google PKCE flow; no service-role key or Google secret."""
import base64
import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode
import httpx


class OwnerAuthError(Exception):
    """Safe, generic authentication failure; never expose provider tokens."""


@dataclass(frozen=True)
class OwnerConfig:
    url: str
    key: str
    email: str
    callback: str = "http://127.0.0.1:8000/api/auth/google/callback"

    @classmethod
    def from_env(cls):
        url = os.environ.get("MHS_SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("MHS_SUPABASE_PUBLISHABLE_KEY", "").strip()
        email = os.environ.get("MHS_OWNER_EMAIL", "").strip().lower()
        if not re.fullmatch(r"https://[a-z0-9]+\.supabase\.co", url):
            raise RuntimeError("Set MHS_SUPABASE_URL to the HTTPS Supabase project URL.")
        if not key.startswith("sb_publishable_"):
            raise RuntimeError("Set MHS_SUPABASE_PUBLISHABLE_KEY (publishable key only).")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise RuntimeError("Set MHS_OWNER_EMAIL to the exact owner Google email.")
        return cls(url, key, email)


def new_verifier():
    return secrets.token_urlsafe(48)


def authorize_url(config, verifier):
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode().rstrip("=")
    return config.url + "/auth/v1/authorize?" + urlencode({
        "provider": "google", "redirect_to": config.callback,
        "code_challenge": challenge, "code_challenge_method": "s256",
        "prompt": "select_account",
    })


def verified_owner(user, expected_email):
    """Only use the server-returned identity record, never editable user_metadata."""
    if not isinstance(user, dict):
        raise OwnerAuthError()
    if (user.get("email", "").lower() != expected_email or not user.get("email_confirmed_at")
            or user.get("is_anonymous") or user.get("role") != "authenticated"
            or not isinstance(user.get("id"), str) or not user["id"]):
        raise OwnerAuthError()
    identities = user.get("identities")
    if not isinstance(identities, list):
        raise OwnerAuthError()
    # A Google-only user must not have an alternate linked sign-in identity.
    if len(identities) != 1:
        raise OwnerAuthError()
    identity = identities[0]
    if not isinstance(identity, dict) or identity.get("provider") != "google":
        raise OwnerAuthError()
    data = identity.get("identity_data")
    if not isinstance(data, dict):
        raise OwnerAuthError()
    if (data.get("email", "").lower() != expected_email or data.get("email_verified") is not True
            or not isinstance(data.get("sub"), str) or not data["sub"]):
        raise OwnerAuthError()
    return user["id"], data["sub"]


def exchange_owner(config, code, verifier, client=None):
    if not isinstance(code, str) or not code or len(code) > 2048:
        raise OwnerAuthError()
    if not isinstance(verifier, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
        raise OwnerAuthError()
    owns_client = client is None
    client = client or httpx.Client(timeout=10, follow_redirects=False)
    try:
        headers = {"apikey": config.key}
        exchange = client.post(config.url + "/auth/v1/token", params={"grant_type": "pkce"},
                               headers=headers, json={"auth_code": code, "code_verifier": verifier})
        exchange.raise_for_status()
        token = exchange.json().get("access_token")
        if not isinstance(token, str) or not token:
            raise OwnerAuthError()
        # The user response is authenticated directly by the configured project.
        result = client.get(config.url + "/auth/v1/user",
                            headers={**headers, "Authorization": "Bearer " + token})
        result.raise_for_status()
        return verified_owner(result.json(), config.email)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError):
        raise OwnerAuthError() from None
    finally:
        if owns_client:
            client.close()
