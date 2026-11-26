import {getDocument,GlobalWorkerOptions} from 'pdfjs-dist/build/pdf.mjs';
GlobalWorkerOptions.workerSrc='/assets/pages-pdf.worker.mjs';
export async function recognize(file,engine,progress,options){
 const pdf=await getDocument({data:new Uint8Array(await file.arrayBuffer()),isEvalSupported:false}).promise;
 try{
  if(pdf.numPages>5)throw Error('PDF maksimum 5 halaman untuk OCR otomatis');
  return await engine.recognizePdf(async(i,raster)=>{
   const page=await pdf.getPage(i);
   const out={page_count:pdf.numPages,document_sha256:pdf.fingerprints[0]};
   if(!raster){out.text=(await page.getTextContent()).items.map(x=>x.str+(x.hasEOL?'\n':' ')).join('');return out;}
   const size=page.getViewport({scale:1}),scale=Math.min(2,2200/Math.max(size.width,size.height));
   const viewport=page.getViewport({scale}),canvas=document.createElement('canvas');
   canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
   await page.render({canvas,viewport}).promise;out.png_base64=canvas.toDataURL('image/png').split(',')[1];
   canvas.width=canvas.height=0;return out;
  },progress,options);
 }finally{await pdf.destroy()}
}
