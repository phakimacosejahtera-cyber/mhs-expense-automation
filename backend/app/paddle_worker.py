"""Standalone local OCR worker. No database imports or network API calls."""
import argparse
import base64
import io
import json
import math
from pathlib import Path

def lines_from_result(result):
    texts=list(result.get("rec_texts",[]))
    scores=list(result.get("rec_scores",[]))
    boxes=list(result.get("rec_polys",[]))
    items=[]
    for i,text in enumerate(texts):
        text=" ".join(str(text).split())[:500]
        if not text:continue
        if i<len(boxes):
            xs=[float(p[0]) for p in boxes[i]]
            ys=[float(p[1]) for p in boxes[i]]
            if not xs or not all(math.isfinite(v) for v in xs+ys):continue
            items.append((min(xs),min(ys),max(xs),max(ys),text))
        else:items.append((0,i*20,100,i*20+12,text))
    # Join nearby cells on the same line while retaining original recognized spans.
    groups=[]
    for x,y,r,b,text in sorted(items,key=lambda p:((p[1]+p[3])/2,p[0])):
        mid=(y+b)/2; height=max(1,b-y)
        match=next((g for g in reversed(groups[-4:]) if abs(mid-g[0])<=min(height,g[1])*.5),None)
        if match is None:groups.append([mid,height,[(x,r,text)]])
        else:match[2].append((x,r,text))
    lines=[]
    for _,height,parts in groups:
        ordered=sorted(parts); chunk=[]; end=None
        for x,r,text in ordered:
            if end is not None and x-end>max(80,height*5):
                lines.append(" ".join(chunk));chunk=[]
            chunk.append(text);end=r
        if chunk:lines.append(" ".join(chunk))
        if len(ordered)>1:
            lines.extend(t for _,_,t in ordered)
    valid=[float(s) for s in scores if math.isfinite(float(s)) and 0<=float(s)<=1]
    return "\n".join(dict.fromkeys(lines)),valid

def make_engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(lang="id",ocr_version="PP-OCRv5",device="cpu",
        text_detection_model_name="PP-OCRv5_server_det",
        use_doc_orientation_classify=True,use_doc_unwarping=False,
        use_textline_orientation=True,enable_mkldnn=False,cpu_threads=4)

def image_array(raw):
    from PIL import Image, ImageOps
    import numpy as np
    Image.MAX_IMAGE_PIXELS=40000000
    with Image.open(io.BytesIO(raw)) as img:
        if img.width*img.height>40000000:raise ValueError("Image too large")
        img=ImageOps.exif_transpose(img).convert("RGBA")
        bg=Image.new("RGBA",img.size,"white");bg.alpha_composite(img)
        img=bg.convert("RGB")
        img.thumbnail((3000,3000),Image.Resampling.LANCZOS)
        if max(img.size)<1400:
            scale=min(2,1400/max(img.size))
            img=img.resize(tuple(max(1,round(x*scale)) for x in img.size),Image.Resampling.LANCZOS)
        return np.asarray(img)[:,:,::-1].copy()

def run(source,engine):
    raw=source.read_bytes()
    if not 0<len(raw)<=8*1024*1024:raise ValueError("Invalid source size")
    pages=[]
    if source.suffix.lower()==".pdf":
        from pdf_ocr import read_pdf_page
        count=read_pdf_page(raw,1)["page_count"]
        for i in range(1,count+1):
            page=read_pdf_page(raw,i,True)
            pages.append((i,base64.b64decode(page["png_base64"])))
    else:pages=[(1,raw)]
    texts=[];scores=[]
    for i,raw in pages:
        page_text=[]
        for result in engine.predict(image_array(raw)):
            text,conf=lines_from_result(result)
            if text:page_text.append(text);scores.extend(conf)
        if not page_text:raise ValueError("Page unreadable")
        texts.append("-- Halaman "+str(i)+" --\n"+"\n".join(page_text)[:max(1,7800//len(pages)-30)])
    return {"text":"\n".join(texts)[:8000],"confidence":round(100*sum(scores)/len(scores),1) if scores else None}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--warmup",action="store_true")
    parser.add_argument("source",type=Path,nargs="?")
    parser.add_argument("output",type=Path,nargs="?")
    args=parser.parse_args()
    engine=make_engine()
    if args.warmup:
        from PIL import Image, ImageDraw
        import numpy as np
        image=Image.new("RGB",(800,200),"white")
        ImageDraw.Draw(image).text((40,40),"TOTAL Rp 100.000",fill="black")
        list(engine.predict(np.asarray(image)[:,:,::-1].copy()))
        print("PaddleOCR CPU ready")
    else:
        if args.source is None or args.output is None:parser.error("source and output required")
        args.output.write_text(json.dumps(run(args.source,engine),ensure_ascii=False),encoding="utf-8")
