"""Phase 3.6 checks: use only pytest temporary folders, never live application data."""
import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest

from backend.app import backup_local as b

RECEIPT = "11111111-1111-4111-8111-111111111111.png"
EXPORT = "22222222-2222-4222-8222-222222222222.xlsx"


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "active"
    root.mkdir()
    for folder in ("private_docs", "exports"):
        (root / folder).mkdir()
    receipt = root / "private_docs" / RECEIPT
    receipt.write_bytes(b"synthetic receipt only")
    export = root / "exports" / EXPORT
    export.write_bytes(b"synthetic historical export")
    (root / ".env").write_text("NOT_FOR_BACKUP=fixture", encoding="utf-8")
    (root / "private_docs" / "orphan.txt").write_text("not registered", encoding="utf-8")
    with closing(sqlite3.connect(root / b.DB_NAME)) as c:
        c.executescript("""
        CREATE TABLE users(id TEXT PRIMARY KEY);
        CREATE TABLE sessions(id TEXT PRIMARY KEY);
        CREATE TABLE documents(id TEXT PRIMARY KEY);
        CREATE TABLE document_versions(id TEXT PRIMARY KEY, document_id TEXT REFERENCES documents(id),
             storage_path TEXT, sha256 TEXT, file_size INTEGER);
        CREATE TABLE transactions(id TEXT PRIMARY KEY, status TEXT, amount_cents INTEGER);
        CREATE TABLE export_logs(id TEXT PRIMARY KEY, storage_path TEXT);
        CREATE TABLE audit_logs(id TEXT PRIMARY KEY);
        CREATE TABLE finance_incomes(id TEXT PRIMARY KEY, amount_cents INTEGER);
        INSERT INTO users VALUES ('demo');
        INSERT INTO sessions VALUES ('not-for-backup');
        INSERT INTO documents VALUES ('d1');
        INSERT INTO transactions VALUES ('t1','APPROVED',3820000000);
        INSERT INTO finance_incomes VALUES ('i1',10000000000);
        INSERT INTO audit_logs VALUES ('a1');
        """)
        c.execute("INSERT INTO document_versions VALUES (?,?,?,?,?)",
                  ("v1","d1",str(receipt),hashlib.sha256(receipt.read_bytes()).hexdigest(),receipt.stat().st_size))
        c.execute("INSERT INTO export_logs VALUES (?,?)",("e1",str(export)))
        c.commit()
    return root


def test_round_trip_and_live_data_unchanged(source, tmp_path):
    before = b.digest(source / b.DB_NAME)
    archive = b.create_backup(source, tmp_path / "manual.zip")
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {b.DB_NAME, b.MANIFEST,
            "private_docs/" + RECEIPT, "exports/" + EXPORT}
    assert b.verify_backup(archive)["files"] == 3
    recovered = tmp_path / "recovered"
    assert b.restore_backup(archive, recovered)["target"] == str(recovered.resolve())
    with closing(sqlite3.connect(recovered / b.DB_NAME)) as c:
        assert c.execute("SELECT amount_cents FROM transactions").fetchone() == (3820000000,)
        assert c.execute("SELECT amount_cents FROM finance_incomes").fetchone() == (10000000000,)
        assert c.execute("SELECT count(*) FROM audit_logs").fetchone() == (1,)
        assert c.execute("SELECT count(*) FROM sessions").fetchone() == (0,)
        receipt = Path(c.execute("SELECT storage_path FROM document_versions").fetchone()[0])
        export = Path(c.execute("SELECT storage_path FROM export_logs").fetchone()[0])
        assert receipt == recovered / "private_docs" / RECEIPT
        assert export == recovered / "exports" / EXPORT
        assert receipt.read_bytes() == (source / "private_docs" / RECEIPT).read_bytes()
        assert export.read_bytes() == (source / "exports" / EXPORT).read_bytes()
    assert b.digest(source / b.DB_NAME) == before
    with closing(sqlite3.connect(source / b.DB_NAME)) as c:
        assert c.execute("SELECT count(*) FROM sessions").fetchone() == (1,)


def test_existing_restore_destination_is_never_overwritten(source, tmp_path):
    archive = b.create_backup(source, tmp_path / "backup.zip")
    before = b.digest(source / b.DB_NAME)
    with pytest.raises(b.BackupError):
        b.restore_backup(archive, source)
    assert b.digest(source / b.DB_NAME) == before
    with pytest.raises(b.BackupError):
        b.create_backup(source, archive)


@pytest.mark.parametrize("mode", ["missing", "changed", "outside"])
def test_incomplete_or_wrong_receipt_prevents_backup(source, tmp_path, mode):
    receipt = source / "private_docs" / RECEIPT
    if mode == "missing":
        receipt.unlink()
    elif mode == "changed":
        receipt.write_bytes(b"unexpected data")
    else:
        outside = tmp_path / RECEIPT
        outside.write_bytes(receipt.read_bytes())
        with closing(sqlite3.connect(source / b.DB_NAME)) as c:
            c.execute("UPDATE document_versions SET storage_path=?", (str(outside),))
            c.commit()
    dest = tmp_path / "invalid.zip"
    with pytest.raises(b.BackupError):
        b.create_backup(source, dest)
    assert not dest.exists()


@pytest.mark.parametrize("mode", ["tampered", "traversal", "unlisted"])
def test_invalid_archive_cannot_restore(source, tmp_path, mode):
    good = b.create_backup(source, tmp_path / "good.zip")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(good) as z, zipfile.ZipFile(bad, "w") as out:
        for name in z.namelist():
            raw = z.read(name)
            if mode == "tampered" and name == "private_docs/" + RECEIPT:
                raw = bytes([raw[0] ^ 1]) + raw[1:]
            out.writestr(name, raw)
        if mode == "traversal":
            out.writestr("../escape.txt", b"invalid")
        if mode == "unlisted":
            out.writestr("exports/33333333-3333-4333-8333-333333333333.xlsx", b"invalid")
    target = tmp_path / "new"
    with pytest.raises(b.BackupError):
        b.restore_backup(bad, target)
    assert not target.exists()
    assert not (tmp_path / "escape.txt").exists()


def test_daily_retention_and_no_duplicate_archive(source):
    folder = b.backup_directory(source)
    for i in range(1, 10):
        old = date(2000, 1, 1) + timedelta(days=i)
        (folder / f"mhs-daily-{old.isoformat()}.zip").write_bytes(b"old fixture")
    manual = folder / "manual.zip"
    manual.write_bytes(b"manual fixture")
    first = b.daily_once(source)
    old_hash = b.digest(first)
    again = b.daily_once(source)
    assert again == first and b.digest(again) == old_hash
    assert len(b.daily_archives(source)) == 7
    assert manual.exists()
    assert b.verify_backup(first)["files"] == 3


def test_missing_export_does_not_publish_partial_archive(source, tmp_path):
    (source / "exports" / EXPORT).unlink()
    dest = tmp_path / "incomplete.zip"
    with pytest.raises(b.BackupError):
        b.create_backup(source, dest)
    assert not dest.exists()
