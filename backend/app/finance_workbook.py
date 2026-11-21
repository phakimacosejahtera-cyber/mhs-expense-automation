"""Local finance workbook: dated entries, reconciled integer totals, immutable snapshot."""
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

MONEY = '"Rp" #,##0.00;[Red]("Rp" #,##0.00)'
ORANGE = "DA6510"
DARK = "242424"

def safe(value):
    if value is None:
        return ""
    s = str(value)
    return "'" + s if s.lstrip()[:1] in ("=", "+", "-", "@") or s[:1] in ("\t", "\r", "\n") else s

def table(ws, headings, rows, widths, money=(), dates=()):
    ws.append(headings)
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=DARK)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in money:
                cell.number_format = MONEY
            elif cell.column in dates:
                cell.number_format = "dd/mm/yyyy"
            cell.alignment = Alignment(vertical="top", wrap_text=True)

def build_workbook(data, expenses, base, snapshot_at):
    incomes = [i for i in data["incomes"] if not i["reversed_at"]]
    if sum(i["amount_cents"] for i in incomes) != data["income_cents"] or sum(e["amount_cents"] or 0 for e in expenses) != data["total_cents"]:
        raise ValueError("Snapshot totals do not reconcile")
    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan"
    period = str(data["year"]) + (f"-{data['month']:02d}" if data["month"] else "")
    ws.merge_cells("A1:B1")
    ws["A1"] = "PT MULIA HAKIMACO SEJAHTERA"
    ws["A1"].fill = PatternFill("solid", fgColor=DARK)
    ws["A1"].font = Font(color="FFFFFF", bold=True, size=15)
    ws.row_dimensions[1].height = 32
    ws.append(["Periode", period])
    ws.append(["Total pemasukan", data["income_cents"]/100])
    ws.append(["Total pengeluaran", data["total_cents"]/100])
    ws.append(["Selisih tercatat", data["net_cents"]/100])
    ws.append(["Jumlah pemasukan", len(incomes)])
    ws.append(["Jumlah pengeluaran", len(expenses)])
    ws.append(["Nilai lama tanpa tanggal (tidak dihitung)", data["legacy_income_cents"]/100])
    ws.append(["Catatan", "Selisih periode, bukan saldo bank atau laba kena pajak."])
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 66
    ws.freeze_panes = "B3"
    for row in (3,4,5,8):
        ws[f"B{row}"].number_format = MONEY
        ws[f"B{row}"].font = Font(bold=True, color=ORANGE)
    inc_rows = [[date.fromisoformat(i["transaction_date"]), safe(i["description"]), i["amount_cents"]/100, safe(i["sender"]), safe(i["id"])] for i in incomes]
    exp_rows = [[date.fromisoformat(e["transaction_date"]), safe(e["description"]), (e["amount_cents"] or 0)/100, safe(e["vendor"]), safe(e["category_name"]), safe(e["activity_name"]), safe(e["payment_method"]), safe(e["invoice_number"]), base+"/api/receipts/"+e["document_id"], safe(e["notes"]), safe(e["id"])] for e in expenses]
    combined = [[r[0],r[1],"Pemasukan",r[2],0,r[3],"",r[4]] for r in inc_rows] + [[r[0],r[1],"Pengeluaran",0,r[2],"",r[3],r[10]] for r in exp_rows]
    combined.sort(key=lambda r:(r[0],r[-1]))
    table(wb.create_sheet("Semua Transaksi"),["Tanggal","Keterangan","Jenis","Pemasukan","Pengeluaran","Pengirim","Vendor","ID"],combined,[16,42,18,22,22,28,28,40],money=(4,5),dates=(1,))
    table(wb.create_sheet("Pemasukan"),["Tanggal","Keterangan","Nominal","Pengirim","ID"],inc_rows,[16,42,22,30,40],money=(3,),dates=(1,))
    ex = wb.create_sheet("Pengeluaran")
    table(ex,["Tanggal","Keterangan","Nominal","Vendor","Kategori","Aktivitas","Metode bayar","Nomor invoice","Tautan kuitansi","Catatan","ID"],exp_rows,[16,42,22,28,25,30,22,24,60,32,40],money=(3,),dates=(1,))
    for row in ex.iter_rows(min_row=2, max_col=9):
        cell = row[8]
        if cell.value:
            cell.hyperlink = cell.value
            cell.style = "Hyperlink"
    table(wb.create_sheet("Report Info"),["Informasi","Nilai"],[
        ["Periode mulai",data["start"]],["Periode akhir (eksklusif)",data["end_exclusive"]],
        ["Snapshot UTC",snapshot_at],["Status","SIMULASI LOKAL — bukan laporan pajak resmi"],
        ["Pengeluaran","APPROVED dan tidak dihapus"],["Pemasukan","Tercatat dan tidak dibatalkan"],
        ["Nilai legacy","Tidak dialokasikan atau dihitung"],["Histori","Snapshot; ekspor lama dipertahankan"],
        ["Tautan kuitansi","Memerlukan server lokal dan login berwenang"]],[36,78])
    return wb
