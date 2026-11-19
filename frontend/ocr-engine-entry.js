// Browser OCR enhancement v0.3. No API keys or extra npm packages are required.
// The file uploaded and stored on the backend is always the ORIGINAL receipt.
import { createWorker } from 'tesseract.js';
import { extractSuggestions } from './ocr-parser.mjs';
import { enhancedImageBlob } from './ocr-preprocess.mjs';

let activeWorker=null;
let progressCallback=()=>{};
async function worker(){
  if(!activeWorker){
    activeWorker=await createWorker('ind+eng',1,{
      logger(message){
        const status=String(message?.status||'Memproses...');
        const fraction=Number(message?.progress);
        progressCallback(status,Number.isFinite(fraction)?Math.round(fraction*100):null);
      }
    });
  }
  return activeWorker;
}

function mergeSuggestions(first,second){
  const amounts=new Map();
  for(const group of [first?.amounts||[],second?.amounts||[]]){
    for(const item of group){
      if(!Number.isFinite(Number(item.value))) continue;
      const key=String(item.value);
      if(!amounts.has(key)) amounts.set(key,item);
    }
  }
  const dates=[...new Set([...(first?.dates||[]),...(second?.dates||[])])].sort();
  return {amounts:[...amounts.values()].slice(0,12),dates};
}
async function recognize(file,notify=()=>{}){
  const type=String(file?.type||'').toLowerCase();
  if(!['image/png','image/jpeg','image/webp'].includes(type)){
    throw new Error('OCR gambar mendukung JPG/PNG/WebP. PDF masih memakai pemeriksaan manual.');
  }
  progressCallback=notify;
  const w=await worker();
  notify('Membaca kuitansi asli',null);
  const original=(await w.recognize(file)).data;
  const primary=extractSuggestions(String(original?.text||''));
  let improved=null;
  // Try a second pass ONLY if crucial fields are missing. Do not slow down successful reads.
  if(!primary.amounts.length || !primary.dates.length){
    try{
      notify('Mencoba meningkatkan kontras gambar',null);
      const prepared=await enhancedImageBlob(file);
      improved=(await w.recognize(prepared)).data;
    }catch(error){
      // Failure to enhance an image must never block the original OCR or manual editing.
      console.warn('Peningkatan kontras tidak tersedia:',error?.message||error);
    }
  }
  const secondary=improved?extractSuggestions(String(improved?.text||'')):{amounts:[],dates:[]};
  const suggestions=mergeSuggestions(primary,secondary);
  const originalText=String(original?.text||'');
  const improvedText=String(improved?.text||'');
  const chosen=(Number(improved?.confidence)>Number(original?.confidence))?improved:original;
  const mergedText=improvedText && improvedText!==originalText
    ? `-- OCR KUITANSI ASLI --\n${originalText}\n\n-- OCR KONTRAS DIPERBAIKI --\n${improvedText}`
    :originalText;
  return {
    text:mergedText,
    confidence:Number.isFinite(chosen?.confidence)?Math.round(chosen.confidence):null,
    suggestions
  };
}
async function close(){
  if(activeWorker){const w=activeWorker;activeWorker=null;await w.terminate();}
  progressCallback=()=>{};
}
window.MHSReceiptOCR={recognize,close};
