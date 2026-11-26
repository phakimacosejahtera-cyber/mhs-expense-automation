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

test('owner dashboard returns the selected totals and five recent approved expenses in one RPC',async t=>{
 const {workspace}=await import('../../frontend/pages-workspace.mjs');
 const expenses=Array.from({length:7},(_,i)=>({
   id:String(i),status:'APPROVED',activity_id:'a',amount_cents:1500,category_name:'ATK',
   transaction_date:i===6?'2026-02-01':'2026-01-01',created_at:'2026-01-0'+(i+1)
 }));
 let calls=0;
 t.mock.method(globalThis,'fetch',async(url,options)=>{
   calls++;
   assert.equal(JSON.parse(options.body).op,'finance');
   return Response.json({expenses,incomes:[],drafts:2,pending_review:1});
 });
 const res=await workspace(new Request('https://test.pages.dev/api/dashboard?year=2026&month=1'),{base:'https://db.test',headers:{}},'test',{});
 const data=await res.json();
 assert.equal(res.status,200);
 assert.equal(calls,1);
 assert.equal(data.total_cents,9000);
 assert.equal(data.drafts,2);
 assert.deepEqual(data.recent_approved.map(x=>x.id),['5','4','3','2','1']);
 assert.equal('expenses' in data,false);
});

test('database read errors keep their diagnostic code without returning private database details',async t=>{
 const {workspace}=await import('../../frontend/pages-workspace.mjs');
 t.mock.method(globalThis,'fetch',async()=>Response.json({code:'42501',message:'private SQL details'},{status:403}));
 const res=await workspace(new Request('https://test.pages.dev/api/dashboard'),{base:'https://db.test',headers:{}},'test',{});
 assert.equal(res.status,403);
 assert.equal((await res.json()).detail,'Akses database Owner ditolak. (42501)');
});
