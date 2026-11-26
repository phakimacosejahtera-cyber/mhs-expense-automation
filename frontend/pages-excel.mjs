import ExcelJS from 'exceljs/dist/exceljs.min.js';

export async function workbook(d,origin,legacy=false){
 const active=d.incomes.filter(i=>!i.reversed_at);
 const total=rows=>rows.reduce((sum,r)=>sum+r.amount_cents,0);
 if(total(d.expenses)!==d.total_cents||total(active)!==d.income_cents)throw Error('Rekonsiliasi total Excel gagal');
 const wb=new ExcelJS.Workbook();
 function sheet(name,headers,rows){
  const ws=wb.addWorksheet(name,{views:[{state:'frozen',ySplit:1}]});
  ws.addRow(headers);ws.addRows(rows);
  ws.getRow(1).font={bold:true,color:{argb:'FFFFFFFF'}};
  ws.getRow(1).fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF272727'}};
  ws.columns.forEach(col=>{col.width=24});
  ws.autoFilter={from:{row:1,column:1},to:{row:Math.max(1,rows.length+1),column:headers.length}};
  return ws;
 }
 const safe=v=>String(v??'');
 const date=r=>new Date(r.transaction_date+'T00:00:00Z');
 const summary=sheet(legacy?'Summary':'Ringkasan',['Keterangan','Nilai'],legacy?[['Total pengeluaran',d.total_cents/100]]:[
 ['Periode',d.year?String(d.year)+(d.month?'-'+d.month:''):'Semua Tahun'],['Total pemasukan',d.income_cents/100],['Total pengeluaran',d.total_cents/100],
 ['Selisih tercatat',d.net_cents/100],['Jumlah pemasukan',active.length],['Jumlah pengeluaran',d.expenses.length]]);
 const money='"Rp" #,##0.00';summary.getColumn(1).width=34;
 const combined=[...active.map(r=>[date(r),safe(r.description),'Pemasukan',r.amount_cents/100,0,safe(r.sender),'',r.id,safe(r.contract_name),safe(r.contract_number)]),
 ...d.expenses.map(r=>[date(r),safe(r.description),'Pengeluaran',0,r.amount_cents/100,'',safe(r.vendor),r.id,safe(r.contract_name),safe(r.contract_number)])].sort((a,b)=>a[0]-b[0]||a[7].localeCompare(b[7]));
 if(!legacy){
  const all=sheet('Semua Transaksi',['Tanggal','Keterangan','Jenis','Pemasukan','Pengeluaran','Pengirim','Vendor','ID','Nama Kontrak','Nomor Kontrak'],combined);
  for(const i of [4,5])all.getColumn(i).numFmt=money;
  const incomes=sheet('Pemasukan',['Tanggal','Keterangan','Nominal','Pengirim','ID','Nama Kontrak','Nomor Kontrak'],active.map(r=>[date(r),safe(r.description),r.amount_cents/100,safe(r.sender),r.id,safe(r.contract_name),safe(r.contract_number)]));
  incomes.getColumn(3).numFmt=money;
 }
 const expenses=sheet(legacy?'Transactions':'Pengeluaran',['Tanggal','Keterangan','Nominal','Vendor','Kategori','Aktivitas','Metode bayar','Nomor invoice','Tautan kuitansi','Catatan','ID','Nama Kontrak','Nomor Kontrak'],d.expenses.map(r=>[
 date(r),safe(r.description),r.amount_cents/100,safe(r.vendor),safe(r.category_name),safe(r.activity_name),safe(r.payment_method),safe(r.invoice_number),
 {text:'Buka kuitansi',hyperlink:origin+'/api/receipts/'+r.document_id},safe(r.notes),r.id,safe(r.contract_name),safe(r.contract_number)]));
 expenses.getColumn(3).numFmt=money;
 for(const ws of wb.worksheets.filter(s=>['Transactions','Pengeluaran','Pemasukan','Semua Transaksi'].includes(s.name))){
  ws.getColumn(1).numFmt='dd/mm/yyyy';
  const end=ws.rowCount,cols=ws.name==='Semua Transaksi'?[4,5]:[3];
  for(const [i,label] of ['TOTAL','TOTAL TERFILTER'].entries()){
   const row=ws.getRow(end+2+i);row.getCell(1).value=label;
   for(const c of cols){const col=ws.getColumn(c).letter;row.getCell(c).value=end===1?0:{formula:i?'ROUND(SUBTOTAL(109,'+col+'2:'+col+end+'),2)':'ROUND(SUM('+col+'2:'+col+end+'),2)'};}
  }
 }
 sheet('Report Info',['Keterangan','Nilai'],[['Perusahaan','PT Mulia Hakimaco Sejahtera'],['Dibuat',new Date()],['Mulai',d.start],['Akhir eksklusif',d.end_exclusive],['Pengeluaran','APPROVED'],['ID snapshot',d.snapshot_id]]);
 return new Blob([await wb.xlsx.writeBuffer()],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
