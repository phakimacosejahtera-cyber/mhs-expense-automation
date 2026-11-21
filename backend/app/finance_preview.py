"""Dated income and period-scoped reporting for the local synthetic demo only."""
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from .db import DATA, allrows, audit, js, now, one, tx, uid
from .security import admin_only, get_auth

router = APIRouter(prefix="/api/finance")

SCHEMA = """CREATE TABLE IF NOT EXISTS income_entries(
    id TEXT PRIMARY KEY, transaction_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
    description TEXT NOT NULL, sender TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
    reversed_at TEXT, reversal_reason TEXT
)"""

def initialize():
    with tx() as c:
        c.execute(SCHEMA)
        c.execute("CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_income_date ON income_entries(transaction_date)")
        for category in ("Peralatan Kantor / IT", "Honorarium / Insentif"):
            c.execute("INSERT INTO categories(id,name,active) VALUES (?,?,1) ON CONFLICT(name) DO NOTHING", (uid(), category))

def owner(request, write=False):
    u = get_auth(request, unsafe=write)
    admin_only(u)
    return u

def bounds(year, month=None):
    if month is None:
        return f"{year:04d}-01-01", f"{year+1:04d}-01-01"
    start = date(year, month, 1)
    end = date(year+1, 1, 1) if month == 12 else date(year, month+1, 1)
    return start.isoformat(), end.isoformat()

class IncomeIn(BaseModel):
    request_id: UUID
    transaction_date: str = Field(min_length=10, max_length=10)
    amount_cents: int = Field(strict=True, gt=0, le=99999999999900)
    description: str = Field(min_length=1, max_length=500)
    sender: str = Field(default="", max_length=200)

class ReverseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)

@router.post("/income")
def create_income(request: Request, data: IncomeIn):
    u = owner(request, True)
    try:
        day = date.fromisoformat(data.transaction_date)
        if day.isoformat() != data.transaction_date or not 1900 <= day.year <= 9998:
            raise ValueError()
        if day > datetime.now(ZoneInfo("Asia/Jakarta")).date():
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Tanggal pemasukan tidak valid atau di masa depan")
    desc, sender = data.description.strip(), data.sender.strip()
    if not desc:
        raise HTTPException(422, "Keterangan wajib diisi")
    entry_id = str(data.request_id)
    values = (day.isoformat(), data.amount_cents, desc, sender)
    with tx() as c:
        previous = one(c, "SELECT * FROM income_entries WHERE id=?", (entry_id,))
        if previous:
            existing = tuple(previous[k] for k in ("transaction_date", "amount_cents", "description", "sender"))
            if previous["created_by"] != u["id"] or existing != values:
                raise HTTPException(409, "ID pencatatan sudah digunakan")
            return {"id": entry_id, "replayed": True}
        c.execute("""INSERT INTO income_entries(id,transaction_date,amount_cents,description,sender,created_by,created_at)
                     VALUES (?,?,?,?,?,?,?)""", (entry_id, *values, u["id"], now()))
        audit(c, u["id"], "INCOME_RECORDED", "income", entry_id,
              {"transaction_date": values[0], "amount_cents": data.amount_cents})
    return {"id": entry_id, "replayed": False}

@router.post("/income/{entry_id}/reverse")
def reverse_income(request: Request, entry_id: UUID, data: ReverseIn):
    u = owner(request, True)
    reason = data.reason.strip()
    if len(reason) < 5:
        raise HTTPException(422, "Alasan pembatalan minimal 5 karakter")
    key = str(entry_id)
    with tx() as c:
        row = one(c, "SELECT * FROM income_entries WHERE id=?", (key,))
        if not row:
            raise HTTPException(404, "Pemasukan tidak ditemukan")
        if row["reversed_at"]:
            raise HTTPException(409, "Pemasukan sudah dibatalkan")
        c.execute("UPDATE income_entries SET reversed_at=?, reversal_reason=? WHERE id=?", (now(), reason, key))
        audit(c, u["id"], "INCOME_REVERSED", "income", key, {"reason": reason, "amount_cents": row["amount_cents"]})
    return {"ok": True}

@router.get("/summary")
def summary(request: Request, year: int | None = Query(None, ge=0, le=9998),
            month: int | None = Query(None, ge=1, le=12)):
    owner(request)
    data, _ = period_snapshot(year, month)
    return data

def period_snapshot(year=None, month=None):
    current_year = datetime.now(ZoneInfo("Asia/Jakarta")).year
    year = current_year if year is None else year
    if year != 0 and not 1900 <= year <= 9998:
        raise HTTPException(422, "Tahun tidak valid")
    if year == 0 and month is not None:
        raise HTTPException(422, "Pilih tahun tertentu untuk filter bulan")
    start, end = bounds(year, month) if year else ("1900-01-01", "9999-01-01")
    where = "status='APPROVED' AND deleted_at IS NULL AND transaction_date>=? AND transaction_date<?"
    params = (start, end)
    # One isolated SQLite transaction provides a consistent snapshot.
    with tx() as c:
        expenses = allrows(c, """SELECT id,transaction_date,amount_cents,description,vendor,category_id,
             document_id,activity_id,payment_method,invoice_number,notes
             FROM transactions WHERE """+where+" ORDER BY transaction_date,id", params)
        incomes = allrows(c, """SELECT id,transaction_date,amount_cents,description,sender,reversed_at,reversal_reason
             FROM income_entries WHERE transaction_date>=? AND transaction_date<?
             ORDER BY transaction_date DESC,created_at DESC,id""", params)
        date_rows = allrows(c, """SELECT DISTINCT transaction_date FROM transactions
            WHERE deleted_at IS NULL AND transaction_date IS NOT NULL
            UNION SELECT DISTINCT transaction_date FROM income_entries""")
        categories = allrows(c, "SELECT id,name FROM categories")
        activities = allrows(c, "SELECT id,name FROM activities")
        old = one(c, "SELECT value FROM app_settings WHERE key='total_income_cents'")
        pending = one(c, "SELECT count(*) AS n FROM transactions WHERE deleted_at IS NULL AND status='PENDING_REVIEW'")["n"]
        drafts = one(c, "SELECT count(*) AS n FROM transactions WHERE deleted_at IS NULL AND status='DRAFT'")["n"]
    names = {x["id"]: x["name"] for x in categories}
    monthly_in, monthly_out, cats = [0]*12, [0]*12, {}
    annual = {}
    years = {current_year}
    for entry in date_rows:
        try:
            day = date.fromisoformat(entry["transaction_date"])
            if day.isoformat() == entry["transaction_date"] and 1900 <= day.year <= 9998:
                years.add(day.year)
        except (ValueError, TypeError):
            pass
    if year:
        years.add(year)

    def bucket(item, direction, amount):
        try:
            day = date.fromisoformat(item["transaction_date"])
            if day.isoformat() != item["transaction_date"]:
                raise ValueError()
        except (ValueError, TypeError):
            raise HTTPException(409, "Ada tanggal transaksi resmi tidak valid. Koreksi sebelum membuat laporan.")
        row = annual.setdefault(day.year, {"year": day.year, "income_cents": 0, "expense_cents": 0})
        row[direction] += amount
        if year:
            (monthly_in if direction == "income_cents" else monthly_out)[day.month-1] += amount
    activity_names = {x["id"]: x["name"] for x in activities}
    for item in expenses:
        key = names.get(item["category_id"], "Belum dikategorikan")
        item["category_name"] = key
        item["activity_name"] = activity_names.get(item["activity_id"], "")
        amount = int(item["amount_cents"] or 0)
        bucket(item, "expense_cents", amount)
        cats[key] = cats.get(key, 0)+amount
    active = [i for i in incomes if not i["reversed_at"]]
    for item in active:
        bucket(item, "income_cents", item["amount_cents"])
    inc = sum(v["income_cents"] for v in annual.values())
    out = sum(v["expense_cents"] for v in annual.values())
    return {"year": year, "month": month, "start": start, "end_exclusive": end,
            "income_cents": inc, "total_cents": out, "net_cents": inc-out,
            "income_count": len(active), "receipt_count": len(expenses),
            "monthly_income": monthly_in, "monthly_expense": monthly_out,
            "available_years": sorted(years, reverse=True),
            "annual": [annual[y] for y in sorted(annual)],
            "categories": [{"category": k, "total_cents": v} for k,v in sorted(cats.items(), key=lambda kv: (-kv[1],kv[0]))],
            "incomes": incomes, "drafts": drafts, "pending_review": pending,
            "legacy_income_cents": int(old["value"]) if old else 0}, expenses


@router.get("/export")
def export_finance(request: Request, year: int | None = Query(None, ge=0, le=9998),
                   month: int | None = Query(None, ge=1, le=12)):
    from .finance_workbook import build_workbook
    from fastapi.responses import FileResponse
    u = owner(request)
    data, expenses = period_snapshot(year, month)
    # Never take the receipt origin from an untrusted Host header.
    server = request.scope.get("server")
    port = server[1] if server and isinstance(server[1], int) else 8001
    base = f"http://127.0.0.1:{port}"
    snapshot_at = now()
    wb = build_workbook(data, expenses, base, snapshot_at)
    key = uid()
    directory = DATA / "exports"
    directory.mkdir(exist_ok=True)
    path = directory / (key + ".xlsx")
    try:
        wb.save(path)
        with tx() as c:
            filters = {"year": data["year"], "month": data["month"], "report": "finance"}
            c.execute("INSERT INTO export_logs VALUES (?,?,?,?,?,?)",
                      (key, u["id"], "all", js(filters), str(path), snapshot_at))
            audit(c, u["id"], "FINANCE_EXPORTED", "export", key,
                  {**filters, "income_cents": data["income_cents"], "expense_cents": data["total_cents"]})
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        wb.close()
    period = str(data["year"]) + (f"-{data['month']:02d}" if data["month"] else "") if data["year"] else "Semua_Tahun"
    return FileResponse(path, filename=f"MHS_Rekap_Keuangan_{period}.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Cache-Control": "private, no-store"})
