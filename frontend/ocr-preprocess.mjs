// Bounded browser-only preprocessing. The saved receipt is never changed.
export const MAX_SIDE=2400;
export const MAX_PIXELS=4500000;
export function targetSize(width,height){
  if(!Number.isFinite(width)||!Number.isFinite(height)||width<=0||height<=0)throw new Error('Dimensi gambar tidak valid');
  const scale=Math.min(2.4,MAX_SIDE/Math.max(width,height),Math.sqrt(MAX_PIXELS/(width*height)));
  return [Math.max(1,Math.floor(width*scale)),Math.max(1,Math.floor(height*scale))];
}
function canvasOf(width,height){
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  if(!ctx)throw new Error('Canvas tidak dapat diproses');
  ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);
  ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
  return [canvas,ctx];
}
// Estimate only small text skew; abstain on sparse or non-text images.
export function estimateSkew(gray,w,h){
  const points=[];
  for(let y=1;y<h-1;y+=2)for(let x=1;x<w-1;x+=2){
    if(gray[y*w+x]<115)points.push([x-w/2,y-h/2]);
  }
  if(points.length<70||points.length>w*h*.16)return 0;
  const score=angle=>{
    const rad=angle*Math.PI/180, sn=Math.sin(rad),cs=Math.cos(rad);
    const bins=new Uint32Array(Math.ceil(Math.hypot(w,h))+4);
    for(const [x,y] of points)bins[Math.round(x*sn+y*cs+bins.length/2)]++;
    return bins.reduce((sum,n)=>sum+n*n,0);
  };
  const base=score(0);let best=base, angle=0;
  for(let a=-8;a<=8;a++){if(!a)continue;const s=score(a);if(s>best){best=s;angle=a}}
  return best>base*1.18?angle:0;
}
export function enhancePixels(pixels,width,height,variant='contrast'){
  const n=width*height, gray=new Uint8ClampedArray(n),hist=new Uint32Array(256);
  for(let i=0;i<n;i++){const p=i*4;const v=Math.round(.62*pixels[p]+.27*pixels[p+1]+.11*pixels[p+2]);gray[i]=v;hist[v]++}
  const percentile=q=>{let sum=0;for(let i=0;i<256;i++){sum+=hist[i];if(sum>=n*q)return i}return 255};
  const lo=percentile(.02),hi=percentile(.98),span=Math.max(45,hi-lo);
  const clamp=v=>Math.max(0,Math.min(255,v));
  for(let i=0;i<n;i++){
    const x=i%width,y=Math.floor(i/width), v=gray[i];
    let sharpen=v;
    if(variant==='denoise'&&x>0&&x<width-1&&y>0&&y<height-1){
      const near=[gray[i-1],gray[i+1],gray[i-width],gray[i+width]];
      const avg=near.reduce((a,b)=>a+b,0)/4;
      // Suppress isolated speckles only where all four neighbors agree.
      if(Math.max(...near)-Math.min(...near)<18&&Math.abs(v-avg)>65)sharpen=avg;
    }
    if(variant==='sharp'&&x>0&&x<width-1&&y>0&&y<height-1){
      const avg=(gray[i-1]+gray[i+1]+gray[i-width]+gray[i+width])/4;
      sharpen=clamp(v+.65*(v-avg));
    }
    const value=hi-lo<12?v:clamp((sharpen-lo)*255/span);
    const p=i*4;pixels[p]=pixels[p+1]=pixels[p+2]=value;pixels[p+3]=255;
  }
  return pixels;
}
export async function enhancedImageBlob(file,{variant='contrast',rotation=0,deskew=false}={}){
  if(typeof createImageBitmap!=='function')throw new Error('Browser tidak mendukung preprocessing');
  const bitmap=await createImageBitmap(file);
  try{
    if(bitmap.width*bitmap.height>40000000)throw new Error('Resolusi gambar terlalu besar untuk preprocessing');
    const [w,h]=targetSize(bitmap.width,bitmap.height);
    let angle=rotation;
    if(deskew){
      const q=Math.min(1,420/Math.max(w,h)),sw=Math.max(1,Math.round(w*q)),sh=Math.max(1,Math.round(h*q));
      const [sample,sc]=canvasOf(sw,sh);sc.drawImage(bitmap,0,0,sw,sh);
      const p=sc.getImageData(0,0,sw,sh).data,g=new Uint8Array(sw*sh);
      for(let i=0;i<g.length;i++)g[i]=Math.round(.299*p[i*4]+.587*p[i*4+1]+.114*p[i*4+2]);
      angle+=estimateSkew(g,sw,sh);sample.width=1;sample.height=1;
    }
    const rad=angle*Math.PI/180,cs=Math.abs(Math.cos(rad)),sn=Math.abs(Math.sin(rad));
    const bw=Math.ceil(w*cs+h*sn),bh=Math.ceil(w*sn+h*cs);
    const fit=Math.min(1,MAX_SIDE/Math.max(bw,bh),Math.sqrt(MAX_PIXELS/(bw*bh)));
    const [canvas,ctx]=canvasOf(Math.max(1,Math.floor(bw*fit)),Math.max(1,Math.floor(bh*fit)));
    ctx.translate(canvas.width/2,canvas.height/2);ctx.rotate(rad);
    ctx.drawImage(bitmap,-w*fit/2,-h*fit/2,w*fit,h*fit);
    if(variant!=='original'){
      const img=ctx.getImageData(0,0,canvas.width,canvas.height);
      enhancePixels(img.data,canvas.width,canvas.height,variant);ctx.putImageData(img,0,0);
    }
    try{return await new Promise((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Gagal memproses gambar')),'image/png'))}
    finally{canvas.width=1;canvas.height=1}
  }finally{bitmap.close?.()}
}
