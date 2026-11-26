const noStore={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'};
const json=(value,status=200)=>Response.json(value,{status,headers:noStore});
const routes={
 'POST corrections/#/replacement':'replacement','GET admin/storage/status':'storage','GET admin/drafts/empty-trash':'trash_preview','POST admin/drafts/empty-trash':'empty_trash','DELETE admin/drafts/#/permanent':'purge','GET config':'config','GET transactions':'transactions','GET notifications':'notifications','GET admin/audit':'audit',
 'GET admin/review-queue':'queue','GET admin/drafts/deleted':'deleted','POST admin/activities':'activities','POST admin/categories':'categories',
 'PATCH admin/activities/#':'activity_edit','POST batches':'batch','POST transactions/submit-batch':'submit',
 'PATCH transactions/#/draft':'draft','DELETE transactions/#/draft':'trash','POST admin/transactions/#/restore':'restore',
 'GET transactions/#/history':'history','GET transactions/#/ocr-result':'ocr_get','POST transactions/#/ocr-result':'ocr',
 'POST admin/transactions/#/decision':'decision','POST admin/transactions/#/reverse':'reverse',
 'POST transactions/#/corrections':'correction','POST admin/corrections/#/decision':'correction_decision',
 'POST transactions/#/reinstatement':'reinstatement','POST finance/income':'income_create','POST finance/income/#/reverse':'income_reverse',
 'GET finance/summary':'finance','GET dashboard':'finance','POST finance/export':'export','POST reports/export':'export',
 'GET receipts/#':'receipt','POST batches/#/documents':'upload','GET admin/calendar':'calendar',
 'POST admin/calendar/stage':'stage','POST admin/calendar/#/publish':'publish'
};
export function period(data,year,month,activity){
 const y=Number(year??0), m=Number(month??0);
 if(!Number.isInteger(y)||y!==0&&(y<1900||y>9998)||!Number.isInteger(m)||m<0||m>12||m&&!y)throw Error('Periode tidak valid');
 const iso=(y,m)=>String(y).padStart(4,'0')+'-'+String(m).padStart(2,'0')+'-01';
 const start=iso(y||1900,m||1),end=y?(m&&m<12?iso(y,m+1):iso(y+1,1)):iso(9999,1);
 const inside=r=>r.transaction_date>=start&&r.transaction_date<end;
 const expenses=data.expenses.filter(r=>inside(r)&&(!activity||r.activity_id===activity));
 const incomes=data.incomes.filter(inside),active=incomes.filter(r=>!r.reversed_at);
 const monthly_income=Array(12).fill(0),monthly_expense=Array(12).fill(0),annual=new Map(),cats=new Map();
 function add(a,b){if(!Number.isSafeInteger(a+b))throw Error('Total melebihi batas presisi');return a+b}
 function sum(items,key,months){let total=0;for(const r of items){const n=r.amount_cents;if(!Number.isSafeInteger(n)||n<=0)throw Error('Nominal tidak valid');
 total=add(total,n);const year=Number(r.transaction_date.slice(0,4)),i=Number(r.transaction_date.slice(5,7))-1;
 const bucket=annual.get(year)||{year,income_cents:0,expense_cents:0};bucket[key]=add(bucket[key],n);annual.set(year,bucket);
 if(y)months[i]=add(months[i],n);if(key==='expense_cents')cats.set(r.category_name,add(cats.get(r.category_name)||0,n));
 }return total}
 const income_cents=sum(active,'income_cents',monthly_income),total_cents=sum(expenses,'expense_cents',monthly_expense);
 return {snapshot_id:data.snapshot_id,year:y,month:m||null,start,end_exclusive:end,income_cents,total_cents,net_cents:income_cents-total_cents,
 expenses,incomes,income_count:active.length,receipt_count:expenses.length,monthly_income,monthly_expense,
 available_years:[...new Set([Number(new Intl.DateTimeFormat('en',{year:'numeric',timeZone:'Asia/Jakarta'}).format(new Date())),...data.incomes.concat(data.expenses).map(r=>Number(r.transaction_date.slice(0,4)))])].sort((a,b)=>b-a),
 categories:[...cats].map(([category,total_cents])=>({category,total_cents})).sort((a,b)=>b.total_cents-a.total_cents),
 annual:[...annual.values()].sort((a,b)=>a.year-b.year),legacy_income_cents:0,drafts:data.drafts,pending_review:data.pending_review};
}
async function hash(bytes){const h=await crypto.subtle.digest('SHA-256',bytes);return Array.from(new Uint8Array(h),b=>b.toString(16).padStart(2,'0')).join('')}
function media(bytes){
 const b=new Uint8Array(bytes), starts=(...v)=>v.every((x,i)=>b[i]===x);
 if(starts(137,80,78,71,13,10,26,10))return 'image/png';
 if(starts(255,216,255))return 'image/jpeg';
 const h=String.fromCharCode(...b.slice(0,12));
 if(h.startsWith('%PDF-'))return 'application/pdf';
 if(h.startsWith('RIFF')&&h.slice(8)==='WEBP')return 'image/webp';
}
export async function workspace(request,config,token,user){
 const url=new URL(request.url),parts=url.pathname.slice(5).split('/');let item=null;
 const route=request.method+' '+parts.map(s=>{if(/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/i.test(s)){item=s;return '#'}return s}).join('/');
 if(route==='GET health')return json({mode:'CLOUDFLARE',finance:true});
 if(route==='POST transactions/#/paddle-ocr')return json({status:'UNAVAILABLE',error_code:'OCR browser'});
 if(route.includes('reinstatements/')&&route.endsWith('/decision'))return json({detail:'Permintaan menunggu pemeriksa lain.'},403);
 const op=routes[route];if(!op)return json({detail:'Fitur ini belum tersedia di workspace hosted.'},404);
 const headers={...config.headers,Authorization:'Bearer '+token};
 const objBase=config.base+'/storage/v1/object/';
 const rpc=(op,body={},item=null)=>fetch(config.base+'/rest/v1/rpc/mhs_pages_api',{method:'POST',redirect:'manual',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({op,body,item})});
 let body={};
 if(op==='upload'||op==='replacement'){
  if(Number(request.headers.get('Content-Length'))>8500000)return json({detail:'Batas kuitansi 8 MB'},413);
  const f=(await request.formData()).get('file');if(!f?.size||f.size>8388608)return json({detail:'Batas kuitansi 8 MB'},422);
  const bytes=await f.arrayBuffer(),mime=media(bytes);if(!mime)return json({detail:'Format kuitansi tidak didukung'},422);
  const reservation=await rpc('reserve',{},item);if(!reservation.ok)return json({detail:'Reservasi unggahan gagal'},409);
  const id=await reservation.json();const uploaded=await fetch(objBase+'mhs-pages-receipts/'+user.id+'/'+id,{method:'POST',headers:{...headers,'Content-Type':mime,'x-upsert':'false'},body:bytes,redirect:'manual'});
  if(!uploaded.ok)return json({detail:'Penyimpanan privat menolak unggahan. Periksa pemasangan database.'},502);
  body={document_id:id,sha256:await hash(bytes),media_type:mime,filename:f.name,file_size:f.size};
 }else if(['POST','PATCH'].includes(request.method)){
  try{body=await request.json()}catch{return json({detail:'JSON tidak valid'},400)}
 }else if(op==='export'||op==='receipt'){body=Object.fromEntries(url.searchParams)}
 if(op==='export')body=Object.fromEntries(url.searchParams);
 const res=await rpc(op,body,item);
 if(!res.ok){
  const e=await res.json().catch(()=>({}));
  const detail=e.code==='PGRST202'?'Skema workspace belum dipasang di Supabase.':e.code==='P0001'?e.message:e.code==='42501'?'Akses database Owner ditolak.':e.code==='23505'?'Permintaan atau nama sudah terdaftar.':'Operasi database gagal. Periksa data dan status terbaru.';
  const code=/^(?:PGRST[0-9X]{3}|[0-9A-Z]{5})$/.test(e.code)?e.code:'HTTP '+res.status;
  return json({detail:detail+' ('+code+')'},e.code==='PGRST202'?503:res.status);
 }
 const value=await res.json();
 if(['purge','empty_trash','storage'].includes(op)){
  const jobs=await rpc('cleanup');const paths=jobs.ok?await jobs.json():[];
  if(paths.length){
   const removed=await fetch(objBase+'mhs-pages-receipts',{method:'DELETE',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify({prefixes:paths}),redirect:'manual'});
   if(removed.ok){await rpc('cleanup_done',{paths});value.files_removed=paths.length;}
  }
 }
 if(op==='receipt'){
  const stored=await fetch(objBase+'authenticated/mhs-pages-receipts/'+value.path,{headers,redirect:'manual'});
  if(!stored.ok)return json({detail:'Bukti tidak tersedia'},502);
  const bytes=await stored.arrayBuffer();if(bytes.byteLength!==value.file_size||await hash(bytes)!==value.sha256||media(bytes)!==value.media_type)return json({detail:'Integritas bukti gagal'},409);
  return new Response(bytes,{headers:{...noStore,'Content-Type':value.media_type,'Content-Disposition':"inline; filename*=UTF-8''"+encodeURIComponent(value.filename),'Content-Security-Policy':"sandbox; frame-ancestors 'self'"}});
 }
 if(op==='ocr_get'&&value.suggestions?.amounts){
  value.amount_review=value.suggestions.amounts.map(a=>({...a,kind:'generic',usable:true,reason:'Kandidat OCR, periksa kuitansi asli'}));
 }
 if(op==='finance'||op==='export'){
  const report=period(value,url.searchParams.get('year'),url.searchParams.get('month'),url.searchParams.get('activity_id'));
  if(route==='GET dashboard'){
   report.recent_approved=report.expenses.slice().sort((a,b)=>
    b.created_at.localeCompare(a.created_at)||a.id.localeCompare(b.id)).slice(0,5);
  }
  if(op==='finance')delete report.expenses;
  return json(report);
 }
 return json(value);
}
