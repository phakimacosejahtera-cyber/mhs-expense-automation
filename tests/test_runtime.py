"""Focused deployment-gate tests; no database or network required."""
import pytest
from backend.app.runtime import require_local_demo


@pytest.mark.parametrize("env", [{}, {"MHS_MODE": "demo"}, {"RENDER": "false"}])
def test_local_demo_remains_available(env):
    assert require_local_demo(env) == "demo"


@pytest.mark.parametrize("env", [
    {"RENDER": "true"},
    {"RENDER": " TRUE ", "MHS_MODE": "demo"},
    {"RENDER_SERVICE_ID": "srv-example"},
    {"MHS_MODE": "production"},
    {"MHS_MODE": ""},
])
def test_incomplete_production_is_blocked(env):
    with pytest.raises(RuntimeError):
        require_local_demo(env)
