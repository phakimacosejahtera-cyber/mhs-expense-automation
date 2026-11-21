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


# Explicitly labelled amounts only; distinguish gross, withheld and received.
MONEY_LABELS = (
    ("potongan_pajak", r"(?:potongan\s+(?:pph|pajak)|pph(?:\s+\d+(?:[.,]\d+)?\s*%)?|pajak\s+dipotong)(?:\s+\d+(?:[.,]\d+)?\s*%)?"),
    ("neto", r"(?:jumlah\s+(?:yang\s+)?diterima|total\s+diterima|neto|netto|bersih)"),
    ("bruto", r"(?:insentif|honorarium|jumlah\s+bruto|total\s+bruto|bruto)"),
    ("total", r"(?:grand\s+total|total(?:\s+(?:pembayaran|bayar|akhir))?|jumlah\s+(?:dibayar|pembayaran)|uang\s+sebesar)"),
)
def idr_amount(token):
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?", token):
        token = token.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d+(?:,\d{2})?", token):
        token = token.replace(",", ".")
    else:
        return None
    from decimal import Decimal
    value = Decimal(token)
    if 0 < value <= 999999999999:
        return float(value)

def labelled_amounts(text):
    results = []
    seen = set()
    for line in str(text).splitlines():
        for kind, label in MONEY_LABELS:
            m = re.fullmatch(r"\s*"+label+r"\s*[:=]?\s*(?:Rp\.?\s*)?(\d[\d.,]*\d|\d)(?:[,.]?[-–—])?\s*", line, re.IGNORECASE)
            if not m:
                continue
            value = idr_amount(m.group(1))
            if value is not None and (kind,value) not in seen:
                results.append({"kind":kind,"value":value,"label":line.strip()[:150]})
                seen.add((kind,value))
            break
        if len(results)>=12:
            break
    return results

def date_context(text):
    """Flag dates in reference-letter lines; do not call them payment dates."""
    results = []
    for line in str(text).splitlines():
        if re.search(r"\b(?:surat keputusan|SK\s|referensi|nomor surat|tanggal surat)\b",line,re.I) and re.search(r"\b(?:19|20)\d{2}\b",line):
            results.append(line.strip()[:300])
        if len(results)>=3:
            break
    return results

def enrich_observation(observation):
    text = observation.get("text") or ""
    return {**observation, "field_candidates":field_candidates(text),
            "labelled_amounts":labelled_amounts(text),
            "date_context":date_context(text)}
