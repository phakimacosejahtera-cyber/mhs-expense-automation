// Parsers are deliberately conservative. OCR text is untrusted and may be incorrect.
// Suggestions are never authoritative transaction values until a human checks them.
const months = {
  januari:1, februari:2, maret:3, april:4, mei:5, juni:6,
  juli:7, agustus:8, september:9, oktober:10, november:11, desember:12,
  jan:1, feb:2, mar:3, apr:4, jun:6, jul:7, agu:8, agt:8, sep:9, okt:10, nov:11, des:12,
};

function dateISO(y,m,d) {
  const yy=Number(y), mm=Number(m), dd=Number(d);
  const dt = new Date(Date.UTC(yy, mm-1, dd));
  if (yy<1990 || yy>2100 || dt.getUTCFullYear()!==yy || dt.getUTCMonth()!==mm-1 || dt.getUTCDate()!==dd) return null;
  return `${yy}-${String(mm).padStart(2,'0')}-${String(dd).padStart(2,'0')}`;
}

export function parseDates(rawText='') {
  const text=String(rawText);
  const values=new Set(); let match;
  const iso=/\b((?:19|20)\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b/g;
  while((match=iso.exec(text))){const v=dateISO(match[1],match[2],match[3]);if(v)values.add(v)}
  const dmy=/\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.]((?:19|20)\d{2})\b/g;
  while((match=dmy.exec(text))){const v=dateISO(match[3],match[2],match[1]);if(v)values.add(v)}
  const named=/\b(0?[1-9]|[12]\d|3[01])\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agu|agt|sep|okt|nov|des)\s+((?:19|20)\d{2})\b/gi;
  while((match=named.exec(text))){const v=dateISO(match[3],months[match[2].toLowerCase()],match[1]);if(v)values.add(v)}
  return [...values].sort();
}

function parseIDR(token) {
  const trimmed=String(token).trim().replace(/[\s,\-–—]+$/,'').replace(/\s+(?=\d{3}(?:\D|$))/g,'.').replace(/\s+/g,'');
  // Indonesian thousand separators and optional decimal fraction.
  // Do not guess mixed 1,234.56/1.234,56 when OCR is ambiguous.
  let digits;
  if(/^\d{1,3}(?:\.\d{3})+(?:,\d{2})?$/.test(trimmed)) digits=trimmed.replaceAll('.','').replace(',','.');
  else if(/^\d{1,3}(?:,\d{3})+$/.test(trimmed)) digits=trimmed.replaceAll(',','');
  else if(/^\d+(?:,\d{2})?$/.test(trimmed)) digits=trimmed.replace(',','.');
  else if(/^\d+$/.test(trimmed)) digits=trimmed;
  else return null;
  const num=Number(digits);
  return Number.isFinite(num) && num>0 && num<=999999999999 ? num : null;
}

export function parseAmounts(rawText='') {
  const lines=String(rawText).split(/\r?\n/);
  const grouped=new Map();
  // Require an Rp prefix or a specific total/payment label to avoid picking invoice IDs and dates.
  const withRp=/\bRp\.?\s*[:.]?\s*(\d(?:[\d.,]|\s+(?=\d{3}\b))*(?:\s*[-–—])?)/gi;
  const withLabel=/(?:total(?:\s+(?:pembayaran|bayar|akhir))?|jumlah\s+(?:dibayar|diterima|pembayaran)|grand\s+total|uang\s+sebesar)\s*[:=]?\s*(?:Rp\.?\s*)?(\d(?:[\d.,]|\s+(?=\d{3}\b))*(?:\s*[-–—])?)/gi;
  lines.forEach((line,index)=>{
    for(const [regex,label] of [[withRp,'Rp'],[withLabel,'TOTAL']]){
      regex.lastIndex=0;let match;
      while((match=regex.exec(line))){
        const value=parseIDR(match[1]);if(value===null)continue;
        const key=String(value);const prev=grouped.get(key);
        const priority=label==='TOTAL' || /\b(?:total|dibayar|diterima|jumlah|pembayaran)\b/i.test(line) ? 2 : 1;
        if(!prev || priority>prev.priority) grouped.set(key,{value,label:line.trim().slice(0,130),priority,line:index+1});
      }
    }
  });
  return [...grouped.values()].sort((a,b)=>b.priority-a.priority || a.line-b.line).slice(0,12);
}

export function extractSuggestions(text=''){
  return {amounts:parseAmounts(text),dates:parseDates(text)};
}
