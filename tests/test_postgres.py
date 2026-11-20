"""SQL compatibility and opt-in real Supabase connectivity checks."""
import os
import uuid
from decimal import Decimal

import pytest

from backend.app.postgres import translate_sql, SCHEMA_FILE, SCHEMA
from backend.app.runtime import require_local_app


def test_parameters_are_bound_not_interpolated():
    assert translate_sql("SELECT * FROM users WHERE email=?") == "SELECT * FROM users WHERE email=%s"


def test_notify_conflict():
    sql = translate_sql("INSERT OR IGNORE INTO notifications(id,dedup_key) VALUES (?,?)")
    assert sql == "INSERT INTO notifications(id,dedup_key) VALUES (%s,%s) ON CONFLICT (dedup_key) DO NOTHING"


def test_ocr_ordering():
    assert translate_sql("ORDER BY created_at DESC, rowid DESC LIMIT 1") == "ORDER BY created_at DESC, extraction_seq DESC LIMIT 1"


def test_postgres_schema():
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    assert "amount_cents BIGINT" in schema
    assert "GENERATED ALWAYS AS IDENTITY" in schema
    assert "CREATE TABLE IF NOT EXISTS owner_login_identity" in schema
    assert "ALTER TABLE transactions ENABLE ROW LEVEL SECURITY" in schema


def test_postgres_test_stays_local():
    assert require_local_app({"MHS_MODE":"pg_test"}) == "pg_test"
    for marker in ({"RENDER":"true"}, {"RENDER_SERVICE_ID":"srv-test"}):
        with pytest.raises(RuntimeError):
            require_local_app({"MHS_MODE":"pg_test", **marker})


def test_integer_money_results():
    from backend.app.db import row_dict
    assert row_dict({"total":Decimal("5000000000")}) == {"total":5000000000}
    assert type(row_dict({"total":Decimal("5000000000")})["total"]) is int


@pytest.mark.skipif(os.getenv("MHS_RUN_PG_TESTS") != "1",
                    reason="Explicitly opt in to isolated Supabase schema test.")
def test_live_postgres_schema_and_rollback():
    from backend.app.postgres import init_schema, connect, transaction
    init_schema()
    key = "test_rollback_" + uuid.uuid4().hex
    with connect() as c:
        assert c.execute("SELECT current_schema() AS name").fetchone()["name"] == SCHEMA
        row = c.execute("SELECT count(*) AS n FROM transactions").fetchone()
        assert row["n"] >= 0
        with pytest.raises(ValueError, match="rollback test"):
            with transaction(c):
                c.execute("INSERT INTO app_settings(key,value,updated_at) VALUES (?,?,?)",
                          (key,"test-only","2026-01-01T00:00:00Z"))
                assert c.execute("SELECT value FROM app_settings WHERE key=?",(key,)).fetchone()["value"] == "test-only"
                raise ValueError("rollback test")
        assert c.execute("SELECT value FROM app_settings WHERE key=?",(key,)).fetchone() is None
        # Verify RLS is enabled on every table created in this test namespace.
        rows = c.execute("SELECT relrowsecurity FROM pg_class JOIN pg_namespace ON pg_namespace.oid=pg_class.relnamespace WHERE nspname=? AND relkind='r'",(SCHEMA,)).fetchall()
        assert rows and all(r["relrowsecurity"] for r in rows)
