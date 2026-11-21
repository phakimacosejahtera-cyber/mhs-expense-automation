"""Local demo only: consistent SQLite backup, verified archive, non-destructive recovery."""
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DB_NAME = "mhs_expenses.sqlite3"
MANIFEST = "manifest.json"
MAX_TOTAL = 4 * 1024**3
MAX_MEMBERS = 100000
MAX_MANIFEST = 16 * 1024**2
FILE_NAME = re.compile(r"(private_docs|exports)/[A-Za-z0-9][A-Za-z0-9_.-]{0,239}")
DAILY_NAME = re.compile(r"mhs-daily-\d{4}-\d{2}-\d{2}\.zip")
LOCK = threading.Lock()
LOG = logging.getLogger("uvicorn.error")


class BackupError(RuntimeError):
    pass


def digest(path):
    h = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return {"size": size, "sha256": h.hexdigest()}


def connect_read(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=15)


def check_database(c):
    c.execute("PRAGMA trusted_schema=OFF")
    if c.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise BackupError("SQLite integrity check failed")
    if c.execute("PRAGMA foreign_key_check").fetchone():
        raise BackupError("Database contains broken references")
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"users", "sessions", "transactions", "documents", "document_versions", "export_logs", "audit_logs"}.issubset(tables):
        raise BackupError("Not an MHS database")


def safe_member(name):
    return name == DB_NAME or bool(FILE_NAME.fullmatch(name)) and not any(
        p in (".", "..") for p in name.split("/")
    )


def references(c):
    for key, path, sha, size in c.execute("SELECT id, storage_path, sha256, file_size FROM document_versions"):
        yield "document_versions", key, path, "private_docs", sha, size
    for key, path in c.execute("SELECT id, storage_path FROM export_logs"):
        yield "export_logs", key, path, "exports", None, None


def local_reference(root, raw, folder):
    source = Path(raw).resolve()
    parent = (root / folder).resolve()
    name = folder + "/" + source.name
    if source.parent != parent or not source.is_file() or not safe_member(name):
        raise BackupError("Referenced document or export missing/outside local storage")
    return source, name


def backup_directory(root):
    folder = Path(root).resolve() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or folder.resolve().parent != Path(root).resolve():
        raise BackupError("Invalid backup folder")
    return folder


def create_backup(data_dir, destination):
    """No source writes. A reserved lock excludes application DB writers during staging."""
    root = Path(data_dir).resolve()
    dest = Path(destination).resolve()
    if dest.exists() or not root.is_dir() or not (root / DB_NAME).is_file():
        raise BackupError("Backup destination already exists or database unavailable")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, tempfile.TemporaryDirectory(prefix="mhs-stage-", dir=dest.parent) as work:
        stage = Path(work)
        snapshot = stage / DB_NAME
        entries = {}
        total = 0
        with closing(sqlite3.connect(root / DB_NAME, timeout=15, isolation_level=None)) as guard:
            guard.execute("BEGIN IMMEDIATE")
            try:
                with closing(connect_read(root / DB_NAME)) as src, closing(sqlite3.connect(snapshot)) as copy:
                    src.backup(copy)
                    check_database(copy)
                    copy.execute("DELETE FROM sessions")
                    for table, key, raw, folder, sha, size in list(references(copy)):
                        source, name = local_reference(root, raw, folder)
                        if name not in entries:
                            target = stage / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            if source.stat().st_size + total > MAX_TOTAL:
                                raise BackupError("Backup exceeds local size limit")
                            shutil.copyfile(source, target)
                            entries[name] = digest(target)
                            total += entries[name]["size"]
                        if sha is not None and entries[name] != {"size": size, "sha256": sha}:
                            raise BackupError("Receipt integrity mismatch")
                        copy.execute("UPDATE " + table + " SET storage_path=? WHERE id=?", (name, key))
                    copy.commit()
                    check_database(copy)
            finally:
                guard.rollback()
        entries[DB_NAME] = digest(snapshot)
        total += entries[DB_NAME]["size"]
        if total > MAX_TOTAL or len(entries) + 1 > MAX_MEMBERS:
            raise BackupError("Backup exceeds local size limit")
        manifest = json.dumps({"format": "MHS_LOCAL_BACKUP_V1", "created_at": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(), "files": entries}, ensure_ascii=False).encode("utf-8")
        if len(manifest) > MAX_MANIFEST:
            raise BackupError("Backup manifest too large")
        partial = stage / "archive.zip"
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for name in sorted(entries):
                z.write(stage / name, name)
            z.writestr(MANIFEST, manifest)
        with zipfile.ZipFile(partial) as z:
            if z.testzip() is not None:
                raise BackupError("Archive CRC check failed")
        if dest.exists():
            raise BackupError("Backup destination already exists")
        os.replace(partial, dest)
        return dest


def unpack_verified(archive, stage):
    """Only explicitly named regular data files; never extract arbitrary paths."""
    stage = Path(stage)
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [x.filename for x in infos]
        if len(names) != len(set(names)) or len(names) > MAX_MEMBERS or MANIFEST not in names:
            raise BackupError("Invalid backup members")
        manifest_info = z.getinfo(MANIFEST)
        if manifest_info.file_size > MAX_MANIFEST:
            raise BackupError("Backup manifest too large")
        manifest = json.loads(z.read(MANIFEST))
        files = manifest.get("files")
        if manifest.get("format") != "MHS_LOCAL_BACKUP_V1" or not isinstance(files, dict) or DB_NAME not in files:
            raise BackupError("Unsupported backup format")
        if set(names) != set(files) | {MANIFEST} or any(not safe_member(n) for n in files):
            raise BackupError("Unexpected archive path")
        if sum(z.getinfo(n).file_size for n in files) > MAX_TOTAL:
            raise BackupError("Backup exceeds local size limit")
        for name, expected in files.items():
            info = z.getinfo(name)
            if not isinstance(expected, dict) or info.file_size != expected.get("size") or info.is_dir():
                raise BackupError("Backup file size mismatch")
            out = stage / name
            out.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, out.open("xb") as dst:
                remaining = info.file_size
                while chunk := src.read(min(1024 * 1024, remaining + 1)):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise BackupError("Backup expands beyond declared size")
                    dst.write(chunk)
            if digest(out) != expected:
                raise BackupError("Backup hash mismatch")
    with closing(connect_read(stage / DB_NAME)) as c:
        check_database(c)
        expected_names = {DB_NAME}
        for _, _, name, folder, sha, size in references(c):
            if not isinstance(name, str) or not safe_member(name) or not name.startswith(folder + "/") or name not in files:
                raise BackupError("Database references missing archive member")
            expected_names.add(name)
            if sha is not None and files[name] != {"size": size, "sha256": sha}:
                raise BackupError("Receipt hash mismatch")
        if expected_names != set(files):
            raise BackupError("Unreferenced archive member")
    return manifest


def verify_backup(archive):
    with tempfile.TemporaryDirectory(prefix="mhs-verify-") as work:
        manifest = unpack_verified(archive, Path(work))
        return {"created_at": manifest["created_at"], "files": len(manifest["files"])}


def restore_backup(archive, target):
    """Restore ONLY to a new directory. Never replace an existing database."""
    target = Path(target).resolve()
    if target.exists():
        raise BackupError("Recovery target must be a new directory")
    if not target.parent.is_dir():
        raise BackupError("Recovery target parent must already exist")
    stage = Path(tempfile.mkdtemp(prefix="mhs-recovery-", dir=target.parent))
    try:
        manifest = unpack_verified(archive, stage)
        with closing(sqlite3.connect(stage / DB_NAME)) as c:
            check_database(c)
            for table, key, name, _, _, _ in list(references(c)):
                c.execute("UPDATE " + table + " SET storage_path=? WHERE id=?", (str(target / name), key))
            c.execute("DELETE FROM sessions")
            c.commit()
            check_database(c)
        if target.exists():
            raise BackupError("Recovery target already exists")
        stage.rename(target)
        return {"created_at": manifest["created_at"], "files": len(manifest["files"]), "target": str(target)}
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def daily_archives(data_dir):
    folder = backup_directory(data_dir)
    return sorted((p for p in folder.iterdir() if DAILY_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()), reverse=True)


def daily_once(data_dir):
    day = datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()
    folder = backup_directory(data_dir)
    destination = folder / ("mhs-daily-" + day + ".zip")
    if not destination.exists():
        create_backup(data_dir, destination)
    for old in daily_archives(data_dir)[7:]:
        old.unlink()
    return destination


def daily_loop(data_dir, stop):
    while not stop.is_set():
        try:
            daily_once(data_dir)
        except Exception as exc:
            LOG.warning("MHS daily backup failed: %s", type(exc).__name__)
        stop.wait(3600)


def main():
    parser = argparse.ArgumentParser(description="MHS local backup recovery; trusted archives only.")
    sub = parser.add_subparsers(dest="action", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("archive")
    restore = sub.add_parser("restore")
    restore.add_argument("archive")
    restore.add_argument("target")
    args = parser.parse_args()
    try:
        result = verify_backup(args.archive) if args.action == "verify" else restore_backup(args.archive, args.target)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        parser.exit(1, "Recovery failed: " + type(exc).__name__ + "\n")


if __name__ == "__main__":
    main()
