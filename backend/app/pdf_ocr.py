"""Bounded local PDF extraction; native rendering is serialized."""
import base64
import io
import math
import threading

_lock = threading.Lock()

def read_pdf_page(raw, index, raster=False):
    import pypdfium2 as pdfium
    if not raw or len(raw)>8*1024*1024:
        raise ValueError("Ukuran PDF tidak didukung")
    with _lock:
        doc=pdfium.PdfDocument(raw)
        try:
            count=len(doc)
            if not 1<=count<=5 or not 1<=index<=count:
                raise ValueError("OCR PDF mendukung maksimum 5 halaman")
            page=doc[index-1]
            try:
                w,h=page.get_size()
                if not all(math.isfinite(x) and 0<x<=14400 for x in (w,h)):
                    raise ValueError("Dimensi PDF tidak didukung")
                tp=page.get_textpage()
                try:
                    text=tp.get_text_bounded()[:16000]
                finally:
                    tp.close()
                result={"page_count":count,"text":text}
                if raster:
                    scale=min(3,2400/max(w,h),math.sqrt(4500000/(w*h)))
                    bitmap=page.render(scale=scale)
                    try:
                        image=bitmap.to_pil()
                        out=io.BytesIO()
                        image.save(out,format="PNG")
                        result["png_base64"]=base64.b64encode(out.getvalue()).decode("ascii")
                    finally:
                        bitmap.close()
                return result
            finally:
                page.close()
        finally:
            doc.close()
