import test from 'node:test';
import assert from 'node:assert/strict';
import {period} from '../../frontend/pages-workspace.mjs';
import {workbook} from '../../frontend/pages-excel.mjs';
import ExcelJS from '../../frontend/node_modules/exceljs/excel.js';

test('filtered snapshot reconciles with the downloaded XLSX including cancelled income and contract fields',async()=>{
 const entry={id:'tx-1',document_id:'receipt-1',description:'=SUM(1,2)',amount_cents:12345,transaction_date:'2026-01-31',activity_id:'a',category_name:'ATK',contract_number:'00009',contract_name:'Kontrak A'};
 const snapshot={expenses:[entry,{...entry,id:'tx-2',transaction_date:'2026-02-01'}],incomes:[{...entry,amount_cents:20000},{...entry,amount_cents:5000,reversed_at:'2026-02-01'}]};
 const summary=period(snapshot,2026,1);
 assert.equal(summary.total_cents,12345);assert.equal(summary.income_cents,20000);assert.equal(summary.net_cents,7655);
 const file=await workbook(summary,'https://example.org');
 const wb=new ExcelJS.Workbook();await wb.xlsx.load(await file.arrayBuffer());
 assert.equal(wb.getWorksheet('Ringkasan').getCell('B4').value,123.45);
 const sheet=wb.getWorksheet('Pengeluaran');
 assert.equal(sheet.getCell('M2').value,'00009');assert.equal(sheet.getCell('B2').type,ExcelJS.ValueType.String);
 assert.equal(sheet.getCell('I2').value.hyperlink,'https://example.org/api/receipts/receipt-1');
});
