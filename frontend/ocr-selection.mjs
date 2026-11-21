// Pure candidate ranking, not an accuracy measure. Keep alternative evidence.
import {extractSuggestions} from './ocr-parser.mjs';
export function reading(text,confidence,label){
  text=String(text||'').trim().slice(0,16000);
  const suggestions=extractSuggestions(text);
  const score=Number.isFinite(confidence)?Math.max(0,Math.min(100,confidence)):null;
  const words=(text.match(/[\p{L}\p{N}]{2,}/gu)||[]).length;
  const rank=(score??65)+Math.min(words,20)*.5+(suggestions.amounts.length?12:0)+(suggestions.dates.length?12:0);
  return {text,confidence:score,label,suggestions,rank};
}
export function adequate(r){
  return !!r&&r.confidence!==null&&r.confidence>=82&&r.suggestions.amounts.some(x=>x.priority===2)&&r.suggestions.dates.length>0;
}
export function selectReadings(readings){
  const ranked=readings.filter(r=>r.text).sort((a,b)=>b.rank-a.rank);
  if(!ranked.length)return [];
  const best=ranked[0];
  // Keep other meaningful alternatives; do not promote low-quality rotated noise.
  return ranked.filter((r,i)=>i===0||(r.rank>=best.rank-25&&r.text!==best.text&&
    (r.suggestions.amounts.length||r.suggestions.dates.length))).slice(0,3);
}
export function summarize(pages){
  const amounts=new Map(),dates=new Set(),sections=[];
  let confidenceSum=0,confidenceCount=0,containsDigital=false;
  const budget=Math.floor(15800/Math.max(1,pages.length));
  for(let i=0;i<pages.length;i++){
    const readings=pages[i];if(!readings.length)continue;
    const first=readings[0];
    if(first.confidence===null)containsDigital=true;else{confidenceSum+=first.confidence;confidenceCount++}
    const per=Math.floor((budget-100)/readings.length);
    for(const r of readings){
      const evidence=r.text.slice(0,Math.max(0,per));
      sections.push('-- Halaman '+(i+1)+' / '+r.label+' --\n'+evidence);
      // Derive all suggestions from the same bounded evidence we will store.
      const suggestions=extractSuggestions(evidence);
      for(const a of suggestions.amounts){
        const prev=amounts.get(String(a.value));
        if(!prev||a.priority>prev.priority)amounts.set(String(a.value),a);
      }
      for(const d of suggestions.dates)dates.add(d);
    }
  }
  return {text:sections.join('\n\n').slice(0,16000),
    confidence:containsDigital||!confidenceCount?null:Math.round(confidenceSum/confidenceCount),
    suggestions:{amounts:[...amounts.values()].sort((a,b)=>b.priority-a.priority).slice(0,12),dates:[...dates].sort().slice(0,20)}};
}
