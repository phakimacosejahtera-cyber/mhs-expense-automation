import test from 'node:test';
import assert from 'node:assert/strict';
import { parseDates,parseAmounts,extractSuggestions } from '../frontend/ocr-parser.mjs';

test('Indonesian rupiah amounts are parsed without fabricating one official total',()=>{
  const r=parseAmounts('Insentif Rp. 35.000.000,-\nPotongan PPh 15% Rp. -5250000-\nJumlah yang diterima Rp. 20.750.000,-');
  assert(r.some(x=>x.value===35000000));
  assert(r.some(x=>x.value===20750000));
  assert(r.length>=2);
});
test('Does not use plain invoice numbers as amount',()=>{
  assert.deepEqual(parseAmounts('No Invoice 51999188\nTanggal: 18-11-2026'),[]);
});
test('Recognizes multiple dates without guessing which is transaction date',()=>{
  assert.deepEqual(parseDates('5 September 2026\n25/12/2026'),['2026-09-05','2026-12-25']);
});
test('Invalid dates are not accepted',()=>{
  assert.deepEqual(parseDates('31/02/2026'),[]);
});
test('Handles empty/garbled OCR',()=>{
  assert.deepEqual(extractSuggestions(''),{amounts:[],dates:[]});
});
test('Recognizes amount on a total line without Rp',()=>{
  const r=parseAmounts('TOTAL BAYAR 125.000');
  assert.equal(r[0]?.value,125000);
});

test('Handwritten-style separated thousand groups produce an unverified candidate',()=>{
  assert(parseAmounts('Rp. 7 800 000').some(x=>x.value===7800000));
  assert(parseAmounts('Uang sebesar 7 800 000').some(x=>x.value===7800000));
});
test('Date from the sample receipt is proposed, not automatically saved',()=>{
  assert(parseDates('DUMAI, 23 AGUSTUS 2019').includes('2019-08-23'));
});
test('Do not derive money solely from numbered motor ID',()=>{
  assert.deepEqual(parseAmounts('NO RANGKA MH1JFH234567\n2014'),[]);
});
