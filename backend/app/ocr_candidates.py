"""Conservative OCR text candidates; no trusted extraction or inferred values."""
import re

FIELDS = {
    "vendor": r"(?:nama\s+(?:toko|merchant|vendor|penjual)|merchant|vendor|penjual|toko)",
    "description": r"(?:keterangan|deskripsi|uraian|keperluan|untuk\s+pembayaran)",
    "payment_method": r"(?:metode\s+pembayaran|cara\s+bayar|payment\s+method)",
    "invoice_number": r"(?:nomor\s+(?:invoice|faktur|kuitansi|kwitansi|dokumen)|no\.?\s*(?:invoice|faktur|kuitansi|kwitansi|dokumen|dok\.?)|invoice\s*(?:no\.?|number)?)",
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
    if re.fullmatch(r"\d{1,3}(?:[ \u00a0]+\d{3})+(?:,\d{2})?", token):
        token = re.sub(r"[ \u00a0]+", "", token)
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
            m = re.fullmatch(r"\s*"+label+r"\s*[:=]?\s*(?:Rp\.?\s*)?(\d[\d., \u00a0]*\d|\d)(?:[,.]?[-–—])?\s*", line, re.IGNORECASE)
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
        if re.search(r"\b(?:surat keputusan|SK|referensi|nomor surat|tanggal surat)\b",line,re.I) and re.search(r"\b(?:19|20)\d{2}\b",line):
            results.append(line.strip()[:300])
        if len(results)>=3:
            break
    return results


# Strict Indonesian integer grammar. Do not guess missing or misspelled words.
_UNITS = dict(zip("satu dua tiga empat lima enam tujuh delapan sembilan".split(),range(1,10)))
_SCALES = {"ribu":1000,"juta":1000000,"miliar":1000000000}
def parse_terbilang(phrase):
    words=phrase.lower().split()
    if not words or len(words)>28:return None
    def small(tokens):
        if not tokens:return None
        n=0
        if tokens[0]=="seratus":n=100;tokens=tokens[1:]
        elif len(tokens)>=2 and tokens[0] in _UNITS and tokens[1]=="ratus":
            n=100*_UNITS[tokens[0]];tokens=tokens[2:]
        if not tokens:return n or None
        if tokens==["sepuluh"]:return n+10
        if tokens==["sebelas"]:return n+11
        if len(tokens)==2 and tokens[0] in _UNITS and tokens[0]!="satu" and tokens[1]=="belas":return n+10+_UNITS[tokens[0]]
        if len(tokens)>=2 and tokens[0] in _UNITS and tokens[1]=="puluh":
            n+=10*_UNITS[tokens[0]];tokens=tokens[2:]
            if not tokens:return n
        if len(tokens)==1 and tokens[0] in _UNITS:return n+_UNITS[tokens[0]]
        return None
    total=0;group=[];previous=10**12
    for word in words:
        if word in _SCALES or word=="seribu":
            scale=1000 if word=="seribu" else _SCALES[word]
            value=(1 if not group else None) if word=="seribu" else small(group)
            if value is None or scale>=previous:return None
            total+=value*scale;previous=scale;group=[]
        else:group.append(word)
    if group:
        value=small(group)
        if value is None:return None
        total+=value
    return total if 0<total<=999999999999 else None

def terbilang_candidates(text):
    out=[]
    for line in text.splitlines():
        clean=line.strip().strip("=|:;#*(). -").strip()
        clean=re.sub(r"^terbilang\s*[:=]?\s*","",clean,flags=re.I)
        clean=re.sub(r"\s+rupiah\s*$","",clean,flags=re.I)
        if not re.search(r"\b(?:ribu|seribu|juta|miliar|ratus|seratus)\b",clean,re.I):continue
        value=parse_terbilang(clean)
        if value is not None and not any(x["value"]==value for x in out):
            out.append({"kind":"terbilang","value":value,"label":line.strip()[:150]})
        if len(out)>=4:break
    return out

def receipt_fields(text):
    fields=field_candidates(text)
    for line in text.splitlines():
        clean=line.strip(" |:;=-")
        if "vendor" not in fields and re.match(r"^(?:PT\.?|CV\.?|UD\.?|Toko)\s+[\w]",clean,re.I) and 4<=len(clean)<=100:
            fields["vendor"]=[clean]
        if "description" not in fields and re.match(r"^(?:\d+\s+)?(?:laptop|notebook|komputer|printer|honorarium|insentif)\b",clean,re.I) and len(clean)<=160 and not re.search(r"\bRp\b",clean,re.I):
            fields["description"]=[clean]
    if "vendor" not in fields:
        lines=[x.strip(" |:;=-") for x in text.splitlines() if x.strip(" |:;=-")]
        for a,b in zip(lines,lines[1:]):
            if re.fullmatch(r"(?:komputer|computer|elektronik|electronics)",b,re.I) and re.fullmatch(r"[A-Za-z][A-Za-z .&'-]{2,65}",a):
                if not re.search(r"\b(?:alamat|tanggal|kuitansi|kwitansi|invoice|total)\b",a,re.I):
                    fields["vendor"]=[a+" "+b];break
    return fields

def amount_review(text, suggestions, labelled, words, confidence):
    rows=[dict(x) for x in labelled+words]
    candidates=suggestions.get("amounts")
    for x in candidates[:12] if isinstance(candidates,list) else []:
        if not isinstance(x,dict):continue
        value=x.get("value");label=x.get("label")
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<value<=999999999999 or not isinstance(label,str) or not label or label not in text:continue
        if any(y["value"]==value for y in rows):continue
        rows.append({"kind":"generic","value":value,"label":label[:150]})
    taxes={x["value"] for x in rows if x["kind"]=="potongan_pajak"}
    word_values={x["value"] for x in words}
    labelled_by_kind={}
    for x in labelled:
        labelled_by_kind.setdefault(x["kind"],set()).add(x["value"])
    payment_values=set().union(*(labelled_by_kind.get(k,set()) for k in ("total","bruto","neto")))
    mismatch=bool(len(word_values)>1 or any(len(v)>1 for k,v in labelled_by_kind.items() if k!="potongan_pajak"))
    if word_values and payment_values and not word_values.issubset(payment_values):mismatch=True
    generic_conflict=any(x["kind"]=="generic" and x["value"] not in word_values|payment_values|taxes for x in rows)
    for x in rows:
        k=x["kind"];v=x["value"]
        x["usable"]=bool(not mismatch and k in ("total","bruto","neto","terbilang") and v not in taxes)
        if k=="terbilang" and not payment_values:x["usable"]=False
        if k=="potongan_pajak":x["reason"]="Potongan pajak, bukan nominal transaksi"
        elif v in taxes:x["reason"]="Nilai juga terdeteksi sebagai pajak; periksa manual";x["usable"]=False
        elif mismatch:x["reason"]="Bukti nominal bertentangan; isi manual"
        elif k=="generic":x["reason"]="Nominal tanpa label total yang jelas; isi manual"
        elif not x["usable"]:x["reason"]="Belum ada nominal numerik pembanding; isi manual"
        elif v in word_values and v in payment_values:x["reason"]="Angka sesuai terbilang; tetap periksa asli"
        else:x["reason"]="Kandidat berlabel; tetap periksa asli"
    notes=[]
    if mismatch:notes.append("Nominal berlabel atau terbilang saling bertentangan. Jangan pilih otomatis.")
    if generic_conflict:notes.append("Ada angka tanpa bukti total yang jelas. Periksa kuitansi asli.")
    if not any(x["usable"] for x in rows):notes.append("Belum ada nominal yang layak dipilih. Masukkan nilai dari kuitansi asli.")
    return rows,notes

def enrich_observation(observation):
    text=observation.get("text") or ""
    labelled=labelled_amounts(text)
    words=terbilang_candidates(text)
    suggestions=observation.get("suggestions")
    if not isinstance(suggestions,dict):suggestions={}
    review,notes=amount_review(text,suggestions,labelled,words,observation.get("confidence"))
    return {**observation,"field_candidates":receipt_fields(text),
            "labelled_amounts":labelled,"terbilang_amounts":words,
            "amount_review":review,"amount_warnings":notes,"date_context":date_context(text)}
