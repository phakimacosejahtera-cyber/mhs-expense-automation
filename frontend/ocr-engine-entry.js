// Local-first receipt OCR. Original evidence is never overwritten.
import {createWorker} from 'tesseract.js';
import {enhancedImageBlob} from './ocr-preprocess.mjs';
import {reading,adequate,selectReadings,summarize} from './ocr-selection.mjs';
let activeWorker=null, progressCallback=()=>{};
async function worker(){
  const paths=document.body.dataset.host==='pages'?{workerPath:'/assets/ocr/worker.min.js',corePath:'/assets/ocr',langPath:'/assets/ocr'}:{};
  if(!activeWorker)activeWorker=await createWorker('ind+eng',1,{...paths,logger(m){
    const p=Number(m?.progress);
    progressCallback(String(m?.status||'Memproses...'),Number.isFinite(p)?Math.round(p*100):null);
  }});
  return activeWorker;
}
async function imageReadings(file,deep=false){
  const w=await worker(), results=[];
  const passes=[['Asli (ukuran dibatasi)',{variant:'original'},6],
    ['Kontras dan deskew',{variant:'contrast',deskew:true},3],
    ['Penajaman',{variant:'sharp',deskew:true},11],
    ['Reduksi noise',{variant:'denoise',deskew:true},6],
    ...[90,180,270].map(rotation=>['Rotasi '+rotation+'°',{variant:'contrast',rotation,deskew:true},3])];
  for(let i=0;i<passes.length;i++){
    const [label,options,psm]=passes[i];
    progressCallback(label,null);
    try{
      const prepared=await enhancedImageBlob(file,options);
      await w.setParameters({tessedit_pageseg_mode:String(psm)});
      const {data}=await w.recognize(prepared);
      results.push(reading(data.text,data.confidence,label));
    }catch(err){
      if(i===0&&!results.length)throw err;
    }
    const best=selectReadings(results)[0];
    // Normal upload checks original + contrast. Difficult images try all orientations.
    if(!deep&&i>=1&&adequate(best))break;
  }
  return selectReadings(results);
}
async function recognize(file,notify=()=>{},options={}){
  progressCallback=notify;
  const type=String(file?.type||'').toLowerCase();
  if(!['image/png','image/jpeg','image/webp'].includes(type))throw Error('Format gambar tidak didukung');
  const result=summarize([await imageReadings(file,!!options.deep)]);
  if(!result.text.trim())throw Error('Teks tidak terbaca; isi manual');
  return result;
}
async function recognizePdf(loadPage,notify=()=>{},options={}){
  progressCallback=notify;
  const pages=[];
  let count=1;
  for(let i=1;i<=count;i++){
    notify('PDF halaman '+i,null);
    const data=await loadPage(i,false);
    if(!Number.isInteger(data.page_count)||data.page_count<1||data.page_count>5)throw Error('PDF maksimum 5 halaman untuk OCR otomatis');
    if(i===1)count=data.page_count;
    if(count!==data.page_count)throw Error('Dokumen berubah saat dibaca');
    const digital=reading(data.text,null,'Teks PDF digital');
    const candidates=digital.text?[digital]:[];
    // Text layers may have only headers or partial OCR. Read the image if key fields are missing.
    if(options.deep||!digital.suggestions.amounts.length||!digital.suggestions.dates.length){
      try{
        const raster=await loadPage(i,true);
        if(raster.page_count!==count||raster.document_sha256!==data.document_sha256)throw Error('Dokumen berubah saat dibaca');
        const blob=new Blob([Uint8Array.from(atob(raster.png_base64),c=>c.charCodeAt(0))],{type:'image/png'});
        candidates.push(...await imageReadings(blob,!!options.deep));
      }catch(err){
        if(!candidates.length)throw err;
        // Preserve available digital text, explicitly flag incomplete reading.
        candidates[0].label+=' (OCR raster gagal; periksa manual)';
      }
    }
    pages.push(selectReadings(candidates));
  }
  const result=summarize(pages);
  if(!result.text.trim())throw Error('PDF tidak terbaca; isi manual');
  if(pages.some(p=>!p.length))throw Error('Ada halaman PDF tidak terbaca; isi manual');
  return result;
}
async function close(){
  if(activeWorker){const w=activeWorker;activeWorker=null;await w.terminate()}
  progressCallback=()=>{};
}
window.MHSReceiptOCR={recognize,recognizePdf,close,release:'phase3-final'};
