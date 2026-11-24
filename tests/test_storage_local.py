"""Storage optimization checks; all data lives in pytest temporary directories."""
import sqlite3
from contextlib import closing
from pathlib import Path
import pytest
from backend.app import storage_local as s

NAME = "11111111-1111-4111-8111-111111111111.png"
OTHER = "22222222-2222-4222-8222-222222222222.png"

@pytest.fixture
def root(tmp_path):
    with closing(sqlite3.connect(tmp_path / s.DB_NAME)) as c:
        c.executescript("""
        CREATE TABLE document_versions(document_id TEXT,storage_path TEXT,file_size INTEGER,sha256 TEXT);
        CREATE TABLE export_logs(storage_path TEXT);
        """)
    return tmp_path

def add(root, doc, path, size, sha="same"):
    with closing(sqlite3.connect(root / s.DB_NAME)) as c:
        c.execute("INSERT INTO document_versions VALUES (?,?,?,?)",(doc,str(path),size,sha))
        c.commit()

def test_atomic_original(root):
    p=Path(s.write_receipt(root,NAME,b"example"))
    assert p.read_bytes()==b"example"
    assert list(p.parent.iterdir())==[p]
    with pytest.raises(FileExistsError):
        s.write_receipt(root,NAME,b"replacement")
    assert p.read_bytes()==b"example"

@pytest.mark.parametrize("name",["../bad.png","bad.png","a/b.png"])
def test_invalid_filename(root,name):
    with pytest.raises(ValueError):
        s.write_receipt(root,name,b"example")

def test_missing_size_duplicate_and_orphan(root):
    p=Path(s.write_receipt(root,NAME,b"example"))
    q=Path(s.write_receipt(root,OTHER,b"orphan"))
    add(root,"d1",p,8)
    add(root,"d2",p.parent/"missing.png",7)
    add(root,"d1",p,7)
    temp=p.parent/".mhs-upload-stale"
    temp.write_bytes(b"x")
    d=s.storage_status(root)
    assert d["receipt_versions"]==3
    assert d["missing_receipt_versions"]==1
    assert d["receipt_size_mismatches"]==1
    assert d["duplicate_hash_groups"]==1
    assert d["unlinked_receipt_files"]==1
    assert d["temporary_upload_files"]==1
    assert d["receipt_bytes"]==14
    assert q.exists() and temp.exists() and p.exists()

def test_empty_database_and_report_inventory(root):
    d=s.storage_status(root)
    assert d["receipt_versions"]==0 and d["duplicate_hash_groups"]==0
    folder=root/"exports"
    folder.mkdir()
    p=folder/"report.xlsx"
    p.write_bytes(b"sample")
    with closing(sqlite3.connect(root/s.DB_NAME)) as c:
        c.execute("INSERT INTO export_logs VALUES (?)",(str(p),))
        c.execute("INSERT INTO export_logs VALUES (?)",(str(folder/"missing.xlsx"),))
        c.commit()
    d=s.storage_status(root)
    assert d["export_bytes"]==6 and d["missing_exports"]==1
    assert d["unlinked_export_files"]==0

def test_failed_write_removes_temporary_file(root,monkeypatch):
    def fail(*args):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(s.os,"fsync",fail)
    with pytest.raises(OSError):
        s.write_receipt(root,NAME,b"example")
    assert not list((root/"private_docs").iterdir())

def test_backup_inventory(root):
    folder=root/"backups"
    folder.mkdir()
    (folder/"mhs-daily-2026-11-21.zip").write_bytes(b"123")
    (folder/"manual.zip").write_bytes(b"4567")
    d=s.storage_status(root)
    assert d["daily_backup_count"]==1 and d["daily_backup_bytes"]==3
    assert d["disk_free_bytes"]>=0
