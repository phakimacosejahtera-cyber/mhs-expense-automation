"""HTTPS owner-mode safeguards. This does not enable hosted production."""
import re

CALLBACK_PATH = "/api/auth/google/callback"
LOCAL_ORIGIN = "http://127.0.0.1:8000"


def configured_public_origin(env):
    value = env.get("MHS_PUBLIC_ORIGIN", "")
    if not value:
        return None
    # First hosted milestone targets one exact Render subdomain only.
    if not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.onrender\.com", value):
        raise RuntimeError("MHS_PUBLIC_ORIGIN must be one exact HTTPS Render origin")
    return value


def cookie_secure(config):
    return bool(config and config.callback.startswith("https://"))


def apply_security_headers(response, path, https_mode=False):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if path == "/" or path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
    if https_mode:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def owner_pin(env):
    uid = env.get("MHS_OWNER_SUPABASE_ID", "").strip()
    sub = env.get("MHS_OWNER_GOOGLE_SUB", "").strip()
    if bool(uid) != bool(sub):
        raise RuntimeError("Owner identity pin requires both identifiers")
    if uid and (not re.fullmatch(r"[0-9a-fA-F-]{36}", uid) or not re.fullmatch(r"[0-9]{1,64}", sub)):
        raise RuntimeError("Invalid owner identity pin format")
    return (uid, sub) if uid else None
