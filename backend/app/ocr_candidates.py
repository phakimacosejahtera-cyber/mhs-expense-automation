"""Conservative OCR text candidates; no trusted extraction or inferred values."""
import re

FIELDS = {
    "vendor": r"(?:nama\s+(?:toko|merchant|vendor|penjual)|merchant|vendor|penjual|toko)",
    "description": r"(?:keterangan|deskripsi|uraian|keperluan|untuk\s+pembayaran)",
    "payment_method": r"(?:metode\s+pembayaran|cara\s+bayar|payment\s+method)",
    "invoice_number": r"(?:nomor\s+(?:invoice|faktur|kuitansi)|no\.?\s*(?:invoice|faktur|kuitansi)|invoice\s*(?:no\.?|number)?)",
}
LIMITS = {"vendor": 200, "description": 500, "payment_method": 100, "invoice_number": 100}

def field_candidates(text):
    """Return only explicit label/value evidence, preserve alternatives."""
    output = {}
    for field, label in FIELDS.items():
        found = []
        for line in str(text).splitlines():
            m = re.fullmatch(r"\s*" + label + r"\s*[:=]\s*(.+?)\s*", line, re.IGNORECASE)
            if not m:
                continue
            value = m.group(1).strip()
            if not value or len(value) > LIMITS[field] or not any(ch.isalnum() for ch in value):
                continue
            if value not in found:
                found.append(value)
            if len(found) >= 3:
                break
        if found:
            output[field] = found
    return output
