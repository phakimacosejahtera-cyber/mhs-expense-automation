"""Local storage diagnostics. Read-only, no deletion or deduplication of evidence."""
import os
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from .backup_local import DB_NAME, DAILY_NAME, safe_member


def write_receipt(data_dir, filename, raw):
    """Publish a complete original atomically on the same volume."""
    root = Path(data_dir).resolve()
    folder = root / "private_docs"
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or folder.resolve() != folder:
        raise ValueError("Invalid receipt storage directory")
    if not safe_member("private_docs/" + filename):
        raise ValueError("Invalid receipt name")
    target = folder / filename
    if target.exists():
        raise FileExistsError("Receipt already exists")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".mhs-upload-", delete=False) as stream:
            tmp = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if target.exists():
            raise FileExistsError("Receipt already exists")
        os.replace(tmp, target)
        return str(target)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _folder_files(root, name):
    folder = root / name
    if not folder.exists():
        return {}, 0
    if folder.is_symlink() or folder.resolve() != folder or not folder.is_dir():
        return {}, 1
    result, errors = {}, 0
    for path in folder.iterdir():
        try:
            if path.is_symlink():
                errors += 1
            elif path.is_file():
                result[path] = path.stat().st_size
        except OSError:
            errors += 1
    return result, errors


def storage_status(data_dir):
    root = Path(data_dir).resolve()
    db = root / DB_NAME
    if not db.is_file() or db.is_symlink():
        raise ValueError("Local database unavailable")
    # Hold a short writer reservation while inspecting receipt references and
    # directory metadata. No database rows are modified and no file contents
    # are read. Backups may still rotate independently.
    with closing(sqlite3.connect(db, timeout=15, isolation_level=None)) as c:
        c.execute("BEGIN IMMEDIATE")
        try:
            versions = c.execute("SELECT document_id, storage_path, file_size, sha256 FROM document_versions").fetchall()
            exports = c.execute("SELECT storage_path FROM export_logs").fetchall()
            docs, doc_errors = _folder_files(root, "private_docs")
            reports, report_errors = _folder_files(root, "exports")
        finally:
            c.rollback()
    backups, backup_errors = _folder_files(root, "backups")
    referenced_docs, referenced_reports = set(), set()
    missing_docs = missing_reports = size_mismatches = 0
    hashes = defaultdict(set)
    for doc_id, raw, expected_size, sha in versions:
        hashes[sha].add(doc_id)
        path = Path(os.path.abspath(raw))
        if path not in docs:
            missing_docs += 1
        else:
            referenced_docs.add(path)
            if docs[path] != expected_size:
                size_mismatches += 1
    for (raw,) in exports:
        path = Path(os.path.abspath(raw))
        if path not in reports:
            missing_reports += 1
        else:
            referenced_reports.add(path)
    disk = shutil.disk_usage(root)
    db_bytes = 0
    for p in (db, root/(DB_NAME+"-wal"), root/(DB_NAME+"-shm"), root/(DB_NAME+"-journal")):
        try:
            if p.is_file() and not p.is_symlink():
                db_bytes += p.stat().st_size
        except OSError:
            doc_errors += 1
    daily = {p:s for p,s in backups.items() if DAILY_NAME.fullmatch(p.name)}
    temporary = {p for p in docs if p.name.startswith(".mhs-upload-") and p not in referenced_docs}
    unlinked = set(docs)-referenced_docs-temporary
    return {
        "database_bytes": db_bytes,
        "receipt_bytes": sum(docs.values()),
        "temporary_upload_files": len(temporary),
        "temporary_upload_bytes": sum(docs[p] for p in temporary),
        "export_bytes": sum(reports.values()),
        "daily_backup_bytes": sum(daily.values()),
        "daily_backup_count": len(daily),
        "disk_free_bytes": disk.free,
        "disk_total_bytes": disk.total,
        "receipt_versions": len(versions),
        "missing_receipt_versions": missing_docs,
        "receipt_size_mismatches": size_mismatches,
        "missing_exports": missing_reports,
        "duplicate_hash_groups": sum(len(ids)>1 for ids in hashes.values()),
        "unlinked_receipt_files": len(unlinked),
        "unlinked_receipt_bytes": sum(docs[p] for p in unlinked),
        "unlinked_export_files": len(set(reports)-referenced_reports),
        "scan_warnings": doc_errors+report_errors+backup_errors,
    }
