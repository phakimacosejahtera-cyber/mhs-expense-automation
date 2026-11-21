import test from 'node:test';
import assert from 'node:assert/strict';
import {targetSize,enhancePixels,estimateSkew} from './ocr-preprocess.mjs';
import {reading,adequate,selectReadings,summarize} from './ocr-selection.mjs';
test('dimensions bounded',()=>{for(const [w,h] of [[100,100],[8000,6000],[12000,20]]){const [a,b]=targetSize(w,h);assert.ok(a*b<=4500000);assert.ok(Math.max(a,b)<=2400)}});
test('flat white background preserved',()=>{const a=new Uint8ClampedArray(36).fill(255);enhancePixels(a,3,3);assert.ok(a.every(x=>x===255));assert.equal(estimateSkew(new Uint8Array(100).fill(255),10,10),0)});
test('meaningful alternatives retained without adding totals',()=>{const a=reading('Total Rp 35.000.000\nTanggal 05/09/2016',92,'original');const b=reading('Total Rp 29.750.000\nTanggal 05/09/2016',87,'enhanced');assert.ok(adequate(a));const result=summarize([selectReadings([a,b])]);assert.deepEqual(result.suggestions.amounts.map(x=>x.value),[35000000,29750000]);assert.deepEqual(result.suggestions.dates,['2016-09-05']);assert.ok(result.text.includes('35.000.000'))});
test('digital text has no fabricated OCR score',()=>{const result=summarize([[reading('Total Rp 100.000\nTanggal 20/10/2011',null,'digital')]]);assert.equal(result.confidence,null);assert.equal(result.suggestions.amounts[0].value,100000)});
