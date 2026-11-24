import pytest
from backend.app.ocr_candidates import enrich_observation
from backend.app.pdf_ocr import read_pdf_page

def test_receipt_labels():
    data=enrich_observation({"text":"Insentif: Rp35.000.000\nPotongan PPh 15%: Rp5.250.000\nJumlah diterima: Rp29.750.000\nVendor: Contoh\nSK tanggal 05/09/2016"})
    assert {x["kind"]:x["value"] for x in data["labelled_amounts"]}=={"bruto":35000000,"potongan_pajak":5250000,"neto":29750000}
    assert data["field_candidates"]["vendor"]==["Contoh"]
    assert data["date_context"]

def sample_pdf(n=1):
    # Minimal self-contained PDF fixture with text, no external generator.
    objs=[b"<< /Type /Catalog /Pages 2 0 R >>",
          ("<< /Type /Pages /Count %d /Kids [%s] >>"%(n," ".join(f"{4+i} 0 R" for i in range(n)))).encode(),
          b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    stream=b"BT /F1 18 Tf 20 100 Td (Total Rp 100.000) Tj ET"
    for i in range(n):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 3 0 R >> >> /Contents {4+n} 0 R >>".encode())
    objs.append(b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream")
    pdf=b"%PDF-1.4\n"; offsets=[0]
    for i,obj in enumerate(objs,1):
        offsets.append(len(pdf));pdf+=f"{i} 0 obj\n".encode()+obj+b"\nendobj\n"
    xref=len(pdf)
    pdf+=f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for o in offsets[1:]:pdf+=f"{o:010d} 00000 n \n".encode()
    return pdf+f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()

def test_pdf_text_and_raster():
    import base64
    raw=sample_pdf()
    result=read_pdf_page(raw,1,True)
    assert result["page_count"]==1
    assert "100.000" in result["text"]
    assert base64.b64decode(result["png_base64"]).startswith(b"\x89PNG")
    with pytest.raises(ValueError):read_pdf_page(raw,2)
    with pytest.raises(ValueError):read_pdf_page(sample_pdf(6),1)
