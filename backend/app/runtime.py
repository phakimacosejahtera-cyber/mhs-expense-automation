"""Fail closed while the application is still a local-only demo."""
import os
from collections.abc import Mapping


def require_local_demo(env: Mapping[str, str] | None = None) -> str:
    """Validate runtime before opening a database or seeding demo accounts.

    Render sets RENDER=true and a service identifier automatically.
    This is a deployment safety check, not a substitute for authentication.
    """
    values = os.environ if env is None else env
    if values.get("RENDER", "").strip().lower() == "true" or values.get("RENDER_SERVICE_ID", "").strip():
        raise RuntimeError(
            "MHS deployment blocked: local demo must not run on Render. "
            "Complete owner authentication and persistent database/storage integration first."
        )
    mode = values.get("MHS_MODE", "demo")
    if mode != "demo":
        raise RuntimeError("MHS production mode is not implemented; deployment blocked.")
    return mode


def require_local_app(env: Mapping[str, str] | None = None) -> str:
    """Allow explicitly selected owner-auth testing, never hosted production."""
    values = os.environ if env is None else env
    if values.get("MHS_MODE") == "owner_test":
        if values.get("RENDER", "").strip().lower() == "true" or values.get("RENDER_SERVICE_ID", "").strip():
            raise RuntimeError("Owner authentication test is local only; deployment blocked.")
        return "owner_test"
    return require_local_demo(values)
