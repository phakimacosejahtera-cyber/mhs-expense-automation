"""Run multi-role workflows in a fresh process, isolated from all application data."""
import os
import subprocess
import sys
from pathlib import Path

def test_isolated_multi_role_workflows(tmp_path):
    root = tmp_path / "workflow-db"
    root.mkdir()
    (root / ".mhs-workflow-fixture").touch()
    env = {k:v for k,v in os.environ.items()
           if not k.startswith("MHS_") and k not in ("RENDER", "RENDER_SERVICE_ID")}
    env.update(MHS_MODE="demo", MHS_STORAGE_MODE="local",
               MHS_DATA_DIR=str(root), MHS_WORKFLOW_TEST_CHILD="1")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/_workflow_cases.py"],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "16 passed" in result.stdout, result.stdout + "\n" + result.stderr
