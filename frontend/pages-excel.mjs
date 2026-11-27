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
 const money='"Rp" #,##0.00;[Red]("Rp" #,##0.00)';summary.getColumn(1).width=34;
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
  const bodyRows=ws.rowCount-1;
  if(!legacy){
   const columns=ws.getRow(1).values.slice(1).map(name=>({name,filterButton:true}));
   const rows=Array.from({length:bodyRows},(_,i)=>ws.getRow(i+2).values.slice(1));
   ws.autoFilter=undefined;
   ws.addTable({name:'MHS_'+(ws.name==='Semua Transaksi'?'Transaksi':ws.name),ref:'A1',columns,
    rows:rows.length?rows:[columns.map(()=>null)],style:{theme:'TableStyleLight1',showRowStripes:false}});
  }
  const end=legacy?ws.rowCount:Math.max(bodyRows+1,2),cols=ws.name==='Semua Transaksi'?[4,5]:[3];
  for(const [i,label] of ['TOTAL','TOTAL TERFILTER'].entries()){
   const row=ws.getRow(end+2+i);row.getCell(1).value=label;
   for(const c of cols){const col=ws.getColumn(c).letter;row.getCell(c).value=end===1?0:{formula:i?'ROUND(SUBTOTAL(109,'+col+'2:'+col+end+'),2)':'ROUND(SUM('+col+'2:'+col+end+'),2)'};}
  }
 }
 if(legacy)sheet('Report Info',['Keterangan','Nilai'],[['Perusahaan','PT Mulia Hakimaco Sejahtera'],['Dibuat',new Date()],['Mulai',d.start],['Akhir eksklusif',d.end_exclusive],['Pengeluaran','APPROVED'],['ID snapshot',d.snapshot_id]]);
 if(!legacy){
  const fill=color=>({type:'pattern',pattern:'solid',fgColor:{argb:'FF'+color}});
  function paint(row,width,bg,fg,bold=false){
   for(let i=1;i<=width;i++){
    const cell=row.getCell(i);
    cell.fill=fill(bg);cell.font={name:'Calibri',size:11,bold,color:{argb:'FF'+fg}};
    cell.alignment={vertical:'middle',wrapText:true};
   }
  }
  const period=d.year?String(d.year)+(d.month?'-'+String(d.month).padStart(2,'0'):''):'Semua Tahun';
  const info=sheet('Report Info',['Informasi','Nilai'],[
   ['Periode mulai',d.year?d.start:'Seluruh tahun valid'],['Periode akhir (eksklusif)',d.year?d.end_exclusive:'Seluruh tahun valid'],
   ['Snapshot UTC',new Date().toISOString()],['Status','Rekap operasional perusahaan'],['Pengeluaran','APPROVED dan tidak dihapus'],
   ['Pemasukan','Tercatat dan tidak dibatalkan'],['Nilai legacy','Tidak dialokasikan atau dihitung'],['Histori','Snapshot saat ekspor'],
   ['Formula','SUM, SUMIFS dan SUBTOTAL dihitung saat dibuka di Excel.'],['Tautan kuitansi','Memerlukan login Owner'],['ID snapshot',d.snapshot_id]]);
  const widths={'Semua Transaksi':[24,42,18,22,22,28,28,40,40,28],Pemasukan:[24,42,22,30,40,40,28],Pengeluaran:[24,42,22,28,25,30,22,24,60,32,40,40,28],'Report Info':[36,78]};
  for(const ws of wb.worksheets){
   ws.properties.tabColor={argb:'FFF4831E'};
   ws.pageSetup={paperSize:9,orientation:ws.columnCount>5?'landscape':'portrait',fitToPage:true,fitToWidth:1,fitToHeight:0};
   if(ws===summary)continue;
   ws.pageSetup.printTitlesRow='1:1';
   ws.views=[{state:'frozen',xSplit:2,ySplit:1,showGridLines:false}];
   widths[ws.name].forEach((width,i)=>ws.getColumn(i+1).width=width);
   ws.eachRow((row,n)=>{
    const label=row.getCell(1).value,footer=label==='TOTAL'||label==='TOTAL TERFILTER';
    paint(row,widths[ws.name].length,n===1?'171717':label==='TOTAL'?'FFF0DF':n%2?'F5F5F5':'FFFFFF',n===1?'FFFFFF':'242424',n===1||footer);
    row.height=n===1?30:Math.min(120,Math.max(21,...row.values.slice(1).map((v,i)=>6+15*Math.ceil(String(v?.text??v??'').length/(widths[ws.name][i]*0.8)))));
    if(ws===expenses && row.getCell(9).hyperlink)row.getCell(9).font={color:{argb:'FFA64B00'},underline:true};
   });
  }
  summary.autoFilter=undefined;
  summary.views=[{state:'frozen',xSplit:1,ySplit:2,showGridLines:false}];
  [46,30,24,24].forEach((width,i)=>summary.getColumn(i+1).width=width);
  summary.getCell('B1').value=null;
  summary.mergeCells('A1:D1');summary.getCell('A1').value='PT MULIA HAKIMACO SEJAHTERA';
  paint(summary.getRow(1),4,'171717','FFFFFF',true);summary.getCell('A1').font={size:15,bold:true,color:{argb:'FFFFFFFF'}};summary.getRow(1).height=32;
  summary.getCell('B2').value=period;
  summary.addRow(['Nilai lama tanpa tanggal (tidak dihitung)',(d.legacy_income_cents||0)/100]);
  summary.addRow(['Catatan','Selisih periode, bukan saldo bank atau laba kena pajak.']);
  summary.mergeCells('B9:D9');
  for(let n=2;n<=9;n++){paint(summary.getRow(n),2,n===5?'FFF0DF':n%2?'F5F5F5':'FFFFFF','242424',n>=3&&n<=5);summary.getRow(n).height=n===9?32:23}
  for(const n of [3,4,5,8])summary.getCell('B'+n).numFmt=money;
  summary.mergeCells('A11:D11');summary.getCell('A11').value=d.year?'REKAP BULANAN — FORMULA EXCEL':'REKAP TAHUNAN — FORMULA EXCEL';
  paint(summary.getRow(11),4,'FFF0DF','242424',true);summary.getRow(11).height=25;
  summary.getRow(12).values=[d.year?'Bulan':'Tahun','Pemasukan','Pengeluaran','Selisih'];paint(summary.getRow(12),4,'171717','FFFFFF',true);
  const buckets=d.year?(d.month?[Number(d.month)]:Array.from({length:12},(_,i)=>i+1)):[...new Set(combined.map(r=>r[0].getUTCFullYear()))].sort((a,b)=>a-b);
  const months='Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember'.split(' ');
  const incomeBy=new Map(),expenseBy=new Map();
  for(const [rows,map] of [[active,incomeBy],[d.expenses,expenseBy]])for(const row of rows){
   const key=Number(d.year?row.transaction_date.slice(5,7):row.transaction_date.slice(0,4));map.set(key,(map.get(key)||0)+row.amount_cents);
  }
  for(const [i,key] of buckets.entries()){
   const n=13+i,row=summary.getRow(n),year=d.year||key,m=d.year?key:1;
   row.getCell(1).value=d.year?months[key-1]:key;
   const begin='DATE('+year+','+m+',1)',end=d.year?'DATE('+year+','+(m+1)+',1)':'DATE('+(year+1)+',1,1)';
   for(const [col,name,length,value] of [[2,'Pemasukan',active.length,incomeBy.get(key)],[3,'Pengeluaran',d.expenses.length,expenseBy.get(key)]]){
    const dates=name+'!$A$2:$A$'+Math.max(2,length+1),amounts=name+'!$C$2:$C$'+Math.max(2,length+1);
    row.getCell(col).value={formula:'ROUND(SUMIFS('+amounts+','+dates+',">="&'+begin+','+dates+',"<"&'+end+'),2)',result:(value||0)/100};
   }
   row.getCell(4).value={formula:'ROUND(B'+n+'-C'+n+',2)',result:((incomeBy.get(key)||0)-(expenseBy.get(key)||0))/100};
   paint(row,4,n%2?'F5F5F5':'FFFFFF','242424');row.height=21;
  }
  const last=13+buckets.length,footer=summary.getRow(last),check=summary.getRow(last+2);
  footer.getCell(1).value='TOTAL PERIODE';check.getCell(1).value='Selisih cek vs snapshot';
  for(const [i,col] of ['B','C','D'].entries()){
   footer.getCell(col).value={formula:buckets.length?'ROUND(SUM('+col+'13:'+col+(last-1)+'),2)':'0',result:[d.income_cents,d.total_cents,d.net_cents][i]/100};
   check.getCell(col).value={formula:'ROUND('+col+last+'-B'+(3+i)+',2)',result:0};
   for(let n=13;n<=last;n++)summary.getCell(col+n).numFmt=money;
   check.getCell(col).numFmt=money;
  }
  paint(footer,4,'FFF0DF','171717',true);paint(check,4,'F5F5F5','475569',true);
  summary.mergeCells(last+3,1,last+3,4);summary.getCell('A'+(last+3)).value='Nilai cek seharusnya nol; koreksi data melalui website.';
  wb.calcProperties.fullCalcOnLoad=true;
 }
 return new Blob([await wb.xlsx.writeBuffer()],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
}
