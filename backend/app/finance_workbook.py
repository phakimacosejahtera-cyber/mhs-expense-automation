"""Local finance workbook: dated entries, reconciled integer totals, immutable snapshot."""
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

MONEY = '"Rp" #,##0.00;[Red]("Rp" #,##0.00)'
ORANGE = "DA6510"
DARK = "242424"

def safe(value):
    if value is None:
        return ""
    s = str(value)
    return "'" + s if s.lstrip()[:1] in ("=", "+", "-", "@") or s[:1] in ("\t", "\r", "\n") else s

def table(ws, headings, rows, widths, money=(), dates=(), table_name=None):
    ws.append(headings)
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=DARK)
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "C2"
    if table_name:
        # An empty export has one blank input-free row, not a transaction.
        last = max(2, len(rows)+1)
        t = Table(displayName=table_name, ref=f'A1:{get_column_letter(len(headings))}{last}')
        t.tableStyleInfo = TableStyleInfo(name='TableStyleMedium9', showFirstColumn=False,
                                         showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        ws.add_table(t)
    else:
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
    if table_name:
        last = max(2, len(rows)+1)
        # Outside the filter range: remains visible when a filter hides rows.
        for offset, label, fn in ((2, "TOTAL", "SUM"), (3, "TOTAL TERFILTER", "SUBTOTAL")):
            row = last+offset
            ws.cell(row, 1, label)
            for col in money:
                letter = get_column_letter(col)
                rng = f"{letter}2:{letter}{last}"
                cell = ws.cell(row, col, f"=ROUND(SUM({rng}),2)" if fn == "SUM" else f"=ROUND(SUBTOTAL(109,{rng}),2)")
                cell.number_format = MONEY
            for cell in ws[row][:len(headings)]:
                cell.fill = PatternFill("solid", fgColor="FFF0DF" if offset==2 else "F1F5F9")
                cell.font = Font(bold=True, color=DARK)

def build_workbook(data, expenses, base, snapshot_at):
    incomes = [i for i in data["incomes"] if not i["reversed_at"]]
    if sum(i["amount_cents"] for i in incomes) != data["income_cents"] or sum(e["amount_cents"] or 0 for e in expenses) != data["total_cents"]:
        raise ValueError("Snapshot totals do not reconcile")
    wb = Workbook()
    ws = wb.active
    ws.title = "Ringkasan"
    period = (str(data["year"]) + (f"-{data['month']:02d}" if data["month"] else "")) if data["year"] else "Semua Tahun"
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
    table(wb.create_sheet("Semua Transaksi"),["Tanggal","Keterangan","Jenis","Pemasukan","Pengeluaran","Pengirim","Vendor","ID"],combined,[24,42,18,22,22,28,28,40],money=(4,5),dates=(1,),table_name="MHS_Transaksi")
    table(wb.create_sheet("Pemasukan"),["Tanggal","Keterangan","Nominal","Pengirim","ID"],inc_rows,[24,42,22,30,40],money=(3,),dates=(1,),table_name="MHS_Pemasukan")
    ex = wb.create_sheet("Pengeluaran")
    table(ex,["Tanggal","Keterangan","Nominal","Vendor","Kategori","Aktivitas","Metode bayar","Nomor invoice","Tautan kuitansi","Catatan","ID"],exp_rows,[16,42,22,28,25,30,22,24,60,32,40],money=(3,),dates=(1,),table_name="MHS_Pengeluaran")
    ex.column_dimensions["A"].width = 24
    for row in ex.iter_rows(min_row=2, max_row=max(2,len(exp_rows)+1), max_col=9):
        cell = row[8]
        if cell.value:
            cell.hyperlink = cell.value
            cell.style = "Hyperlink"
    # The top summary retains server-computed values as an immutable audit reference.
    # Monthly formula area uses the transaction detail rows, not subtotal rows.
    ws["A11"] = "REKAP BULANAN — FORMULA EXCEL" if data["year"] else "REKAP TAHUNAN — FORMULA EXCEL"
    ws.merge_cells("A11:D11")
    ws["A11"].font = Font(bold=True, color=ORANGE)
    for col, label in enumerate(("Bulan" if data["year"] else "Tahun", "Pemasukan", "Pengeluaran", "Selisih"), 1):
        cell = ws.cell(12, col, label)
        cell.fill = PatternFill("solid", fgColor=DARK)
        cell.font = Font(bold=True, color="FFFFFF")
    selected = ([data["month"]] if data["month"] else list(range(1,13))) if data["year"] else sorted({r[0].year for r in inc_rows+exp_rows})
    months = ("Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember")
    end_inc, end_exp = max(2,len(inc_rows)+1), max(2,len(exp_rows)+1)
    year = data["year"]
    for row, bucket in enumerate(selected, 13):
        ws.cell(row, 1, months[bucket-1] if year else bucket)
        begin = f"DATE({year},{bucket},1)" if year else f"DATE({bucket},1,1)"
        finish = f"DATE({year},{bucket+1},1)" if year else f"DATE({bucket+1},1,1)"
        for col, sheet, end in ((2,"Pemasukan",end_inc),(3,"Pengeluaran",end_exp)):
            dates = f"'{sheet}'!$A$2:$A${end}"
            amounts = f"'{sheet}'!$C$2:$C${end}"
            ws.cell(row, col, f'=ROUND(SUMIFS({amounts},{dates},">="&{begin},{dates},"<"&{finish}),2)')
        ws.cell(row,4,f"=ROUND(B{row}-C{row},2)")
    total = 13+len(selected)
    ws.cell(total,1,"TOTAL PERIODE")
    for col in range(2,5):
        letter = get_column_letter(col)
        ws.cell(total,col,f"=ROUND(SUM({letter}13:{letter}{total-1}),2)" if selected else "=0")
        for row in range(13,total+1):
            ws.cell(row,col).number_format = MONEY
    for cell in ws[total][:4]:
        cell.fill = PatternFill("solid",fgColor="FFF0DF")
        cell.font = Font(bold=True,color=DARK)
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 24
    ws["B9"].alignment = Alignment(wrap_text=True,vertical="top")
    ws.row_dimensions[9].height=34
    ws.cell(total+2,1,"Selisih cek vs snapshot")
    ws.cell(total+2,2,f"=ROUND(B{total}-B3,2)")
    ws.cell(total+2,3,f"=ROUND(C{total}-B4,2)")
    ws.cell(total+2,4,f"=ROUND(D{total}-B5,2)")
    for col in range(2,5):
        ws.cell(total+2,col).number_format=MONEY
    ws.cell(total+3,1,"Nilai cek seharusnya nol; koreksi data melalui website.")
    ws.merge_cells(start_row=total+3,start_column=1,end_row=total+3,end_column=4)
    table(wb.create_sheet("Report Info"),["Informasi","Nilai"],[
        ["Periode mulai",data["start"] if data["year"] else "Seluruh tahun valid"],["Periode akhir (eksklusif)",data["end_exclusive"] if data["year"] else "Seluruh tahun valid"],
        ["Snapshot UTC",snapshot_at],["Status","SIMULASI LOKAL — bukan laporan pajak resmi"],
        ["Pengeluaran","APPROVED dan tidak dihapus"],["Pemasukan","Tercatat dan tidak dibatalkan"],
        ["Nilai legacy","Tidak dialokasikan atau dihitung"],["Histori","Snapshot; ekspor lama dipertahankan"],["Formula","SUM/SUMIFS/SUBTOTAL dihitung Excel saat dibuka; ringkasan atas adalah nilai snapshot server."],
        ["Tautan kuitansi","Memerlukan server lokal dan login berwenang"]],[36,78])
    return wb
