// Client-only enhancement. The original receipt file is never modified or replaced.
// Designed to help with low-contrast photos, NOT to guarantee handwriting recognition.
export async function enhancedImageBlob(file) {
  if (typeof createImageBitmap !== 'function') {
    throw new Error('Browser ini tidak mendukung createImageBitmap; OCR standar tetap digunakan.');
  }
  const bitmap = await createImageBitmap(file);
  try {
    const maxSide = Math.max(bitmap.width,bitmap.height);
    if(!maxSide) throw new Error('Gambar tidak dapat dibaca');
    const scale = Math.max(1,Math.min(2.4, 2400/maxSide));
    const width=Math.round(bitmap.width*scale),height=Math.round(bitmap.height*scale);
    const canvas=document.createElement('canvas');
    canvas.width=width;canvas.height=height;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});
    if(!ctx) throw new Error('Canvas tidak dapat diproses');
    ctx.imageSmoothingEnabled=true;
    ctx.imageSmoothingQuality='high';
    ctx.drawImage(bitmap,0,0,width,height);
    const picture=ctx.getImageData(0,0,width,height);
    const pixels=picture.data;
    // Red-dominant luminance helps distinguish blue pen ink from green tinted receipts.
    // Mild contrast; do not force binary threshold, which can erase weak strokes.
    for(let i=0;i<pixels.length;i+=4){
      const lum=0.62*pixels[i]+0.27*pixels[i+1]+0.11*pixels[i+2];
      const value=Math.min(255,Math.max(0,Math.round((lum-120)*1.65+155)));
      pixels[i]=value;pixels[i+1]=value;pixels[i+2]=value;
    }
    ctx.putImageData(picture,0,0);
    return await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Gagal membuat gambar OCR yang dipertajam')),'image/png'));
  } finally { bitmap.close?.(); }
}
