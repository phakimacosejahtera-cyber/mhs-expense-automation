import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
import {workbook} from './pages-excel.mjs';
const income={id:'i',description:'Pemasukan',transaction_date:'2026-11-26',amount_cents:400000000};
const expense={id:'e',description:'Pengeluaran',document_id:'doc',transaction_date:'2011-10-20',amount_cents:319999992,contract_number:'00012'};
const source={year:0,month:0,incomes:[income],expenses:[expense],income_cents:400000000,total_cents:319999992,net_cents:80000008,snapshot_id:'test'};
for(const d of [source,{...source,year:2026,month:11,expenses:[],total_cents:0,net_cents:400000000},{...source,incomes:[],expenses:[],total_cents:0,net_cents:0,income_cents:0}]){
 const file=await workbook(d,'https://example.test');
 const wb=new ExcelJS.Workbook();await wb.xlsx.load(await file.arrayBuffer());
 assert.deepEqual(wb.worksheets.map(s=>s.name),['Ringkasan','Semua Transaksi','Pemasukan','Pengeluaran','Report Info']);
 const summary=wb.getWorksheet('Ringkasan');
 assert.equal(summary.getCell('A1').value,'PT MULIA HAKIMACO SEJAHTERA');
 for(const [row,cents] of [[3,d.income_cents],[4,d.total_cents],[5,d.net_cents]]){
   assert.equal(summary.getCell('B'+row).value,cents/100);assert.match(summary.getCell('B'+row).numFmt,/0\.00/);
 }
 assert.ok(wb.getWorksheet('Pengeluaran').getTable('MHS_Pengeluaran'));
 if(d===source){
   assert.equal(summary.getCell('A13').value,2011);
   assert.equal(summary.getCell('C13').result,3199999.92);
   assert.equal(summary.getCell('B14').result,4000000);
   assert.match(summary.getCell('C13').formula,/SUMIFS/);
   assert.equal(wb.getWorksheet('Pengeluaran').getCell('M2').value,'00012');
   assert.equal(wb.getWorksheet('Pengeluaran').getCell('I2').hyperlink,'https://example.test/api/receipts/doc');
 }
}
