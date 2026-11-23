// PT Mulia Hakimaco Sejahtera. Local V0.1: no fabricated OCR or fake financial results.
const $ = s => document.querySelector(s);
const h = (v='') => String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const rp = cents => new Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR',maximumFractionDigits:0}).format((Number(cents)||0)/100);
const short = s => s ? new Date(s).toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short'}) : '—';
const state={me:null,config:null,page:'dashboard',transactions:[],queue:null,selected:new Set(),
  ocrResults:new Map(),ocrStatus:new Map()};
const navUploader=[['dashboard','◫','Ringkasan'],['upload','↥','Upload Receipt'],['transactions','▤','My Transactions'],['reports','▥','My Reports'],['notifications','♧','Notifications']];
const navAdmin=[['dashboard','◫','Dashboard'],['upload','⬆','Upload Receipt'],['reviews','☑','Review Queue'],['transactions','▤','All Transactions'],['reports','▥','Reports & Excel'],['management','⚙','Management'],['audit','☷','Audit Trail'],['notifications','♧','Notifications']];

async function api(path,opts={}){
  let headers={...(opts.headers||{})};if(opts.method && opts.method!=='GET')headers['X-CSRF-Token']=state.me?.csrf||'';
  if(opts.body && !(opts.body instanceof FormData))headers['Content-Type']='application/json';
  let res=await fetch('/api'+path,{...opts,credentials:'same-origin',headers});
  if(res.status===401 && state.me){state.me=null;showLogin();throw new Error('Sesi berakhir. Silakan login kembali.');}
  if(!res.ok){let j=await res.json().catch(()=>({}));let d=j.detail||'Terjadi kesalahan';throw new Error(typeof d==='string'?d:JSON.stringify(d));}
  return res;
}
async function json(path,opts={}){let r=await api(path,opts);return r.json();}
async function post(path,obj){return json(path,{method:'POST',body:JSON.stringify(obj)});}
async function patch(path,obj){return json(path,{method:'PATCH',body:JSON.stringify(obj)});}
function toast(msg,bad=false){const t=$('#toast');t.innerText=msg;t.style.display='block';t.style.borderLeft='4px solid '+(bad?'#ef6262':'#f4831e');setTimeout(()=>{if(t.innerText===msg)t.style.display='none'},5500)}
let wibClockTimer=null;
const wibTimeFormat=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Jakarta',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
const wibDateFormat=new Intl.DateTimeFormat('id-ID',{timeZone:'Asia/Jakarta',weekday:'long',day:'numeric',month:'long',year:'numeric'});
function wibClockParts(now){
 return {time:wibTimeFormat.format(now),date:wibDateFormat.format(now)};
}
function updateWibClock(){
 const clock=$('#wib-clock'),date=$('#today');if(!clock||!date)return;
 const wib=wibClockParts(new Date());
 clock.textContent=wib.time;
 if(date.textContent!==wib.date)date.textContent=wib.date;
}
function startWibClock(){
 stopWibClock();updateWibClock();
 wibClockTimer=setInterval(updateWibClock,1000);
}
function stopWibClock(){
 if(wibClockTimer!==null){clearInterval(wibClockTimer);wibClockTimer=null}
}
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&wibClockTimer!==null)updateWibClock()});
function showLogin(){stopWibClock();$('#login-screen').classList.remove('hidden');$('#app').classList.add('hidden')}
const navigationIcons={
 dashboard:'<rect x="3" y="3" width="7" height="7" rx="1.2"/><rect x="14" y="3" width="7" height="7" rx="1.2"/><rect x="3" y="14" width="7" height="7" rx="1.2"/><rect x="14" y="14" width="7" height="7" rx="1.2"/>',
 upload:'<path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5"/>',
 reviews:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 2 2 5-5M8 17h8"/>',
 transactions:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11M15 9v11M3 14h18"/>',
 reports:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 17l3-4 3 4m-6-4 3 4 3-4"/>',
 management:'<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/><circle cx="12" cy="12" r="7"/>',
 audit:'<path d="M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5m4-1v5l3 2"/>',
 notifications:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 12a2 2 0 0 0 4 0"/>'
};
function navigationIcon(id){
 return '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'+(navigationIcons[id]||navigationIcons.management)+'</svg>';
}
function showApp(){
 $('#login-screen').classList.add('hidden');$('#app').classList.remove('hidden');
 $('#role-chip').innerText=state.me.role.toUpperCase();
 const name=String(state.me.name||'Pengguna').trim()||'Pengguna';
 $('#avatar').innerText=name[0].toUpperCase();
 const profile=$('#profile-name');if(profile)profile.textContent=name;
 startWibClock();
 renderNav();
}
function renderNav(){
 const items=state.me.role==='admin'?navAdmin:navUploader;
 const primary=new Set(['dashboard','upload','reviews','transactions','reports']);
 const button=([id,icon,name])=>`<button type="button" class="navbutton ${id===state.page?'active':''}" data-nav="${id}" ${id===state.page?'aria-current="page"':''}><span class="navicon">${navigationIcon(id)}</span><span class="navlabel">${h(name)}</span></button>`;
 $('#navigation').innerHTML=items.filter(x=>primary.has(x[0])).map(button).join('')+'<div class="nav-section" aria-hidden="true">PENGELOLAAN</div>'+items.filter(x=>!primary.has(x[0])).map(button).join('');
}
function setHead(name,desc){$('#page-title').innerText=name;$('#page-desc').innerText=desc;$('#crumb-title').innerText=name}
const pill=s=>`<span class="pill ${h(s)}">${h(s?.replaceAll('_',' ')||'—')}</span>`;
function modal(title,body,foot=''){ $('#dialog-title').innerText=title;$('#dialog-body').innerHTML=body;$('#dialog-foot').innerHTML=foot;$('#dialog-overlay').classList.remove('hidden') }
function closeModal(){$('#dialog-overlay').classList.add('hidden')}
function field(label,name,value='',type='text',required=false,extra=''){return `<div class="field"><label for="d-${name}">${h(label)}</label><input id="d-${name}" name="${h(name)}" type="${type}" value="${h(value)}" ${required?'required':''} ${extra}></div>`}
function opts(values,selected=null,placeholder='Pilih...'){return `<option value="">${h(placeholder)}</option>`+values.map(v=>`<option value="${h(v.id)}" ${v.id===selected?'selected':''}>${h(v.name)}</option>`).join('')}
function selectF(label,name,values,selected,required=false){return `<div class="field"><label>${h(label)}</label><select name="${h(name)}" ${required?'required':''}>${opts(values,selected)}</select></div>`}
function txTable(rows,showActions=true){
 if(!rows.length)return '<div class="empty">Belum ada transaksi yang sesuai.</div>';
 return `<div class="tablescroll"><table class="data-table"><thead><tr><th>TANGGAL</th><th>KETERANGAN</th><th>NAMA KONTRAK</th><th>NOMOR KONTRAK</th><th>AKTIVITAS</th><th>KATEGORI</th><th>NOMINAL</th><th>STATUS</th>${showActions?'<th>AKSI</th>':''}</tr></thead><tbody>${rows.map(t=>`<tr><td class="nowrap">${h(t.transaction_date||'—')}</td><td><strong class="clamp" title="${h(t.description||'Belum diisi')}">${h(t.description||'Belum diisi')}</strong><div class="tiny muted">${h(t.uploader_name||'')} ${t.correction_pending?'· Koreksi pending':t.reinstatement_pending?'· Pemulihan pending':''}</div></td><td>${h(t.contract_name||'—')}</td><td>${h(t.contract_number||'—')}</td><td>${h(t.activity_name||'')}</td><td>${h(t.category_name||'—')}</td><td class="nowrap"><strong>${rp(t.amount_cents)}</strong></td><td>${pill(t.status)}</td>${showActions?`<td><div class="inline-actions"><button class="btn outline" data-detail="${t.id}">Detail</button>${t.status==='DRAFT'?`<button class="btn soft" data-edit="${t.id}">Edit</button>`:''}${['APPROVED','PENDING_REVIEW','REJECTED'].includes(t.status)&&!t.correction_pending?`<button class="btn outline" data-correction="${t.id}">Koreksi</button>`:''}${t.status==='REVERSED'&&!t.reinstatement_pending?`<button class="btn soft" data-reinstate="${t.id}">Reinstatement</button>`:''}${state.me.role==='admin'&&t.status==='APPROVED'?`<button class="btn danger" data-reverse="${t.id}">Reverse</button>`:''}</div></td>`:''}</tr>`).join('')}</tbody></table></div>`;
}
async function nav(page){
 state.page=page;renderNav();setMobileNav(false);
 try{
 if(page==='dashboard')await dashboard();else if(page==='upload')await uploadPage();else if(page==='transactions')await transactionsPage();else if(page==='reviews')await reviewsPage();else if(page==='reports')await reportsPage();else if(page==='calendar')await calendarPage();else if(page==='management')await managementPage();else if(page==='audit')await auditPage();else if(page==='notifications')await notificationsPage();
 }catch(e){toast(e.message,true);$('#page-content').innerHTML=`<div class="notice danger-notice">${h(e.message)}</div>`}
}
async function loadTx(){state.transactions=await json('/transactions');return state.transactions}
let financeYear=0, financeMonth=0;
function yearOptions(d){return '<option value="0" '+(financeYear===0?'selected':'')+'>Semua Tahun</option>'+d.available_years.map(y=>'<option value="'+y+'" '+(financeYear===y?'selected':'')+'>'+y+'</option>').join('')}
function financePeriodChange(e,page){financeYear=Number(e.target.value);financeMonth=0;return nav(page)}
async function dashboard(){
 setHead('Dashboard','Ringkasan keuangan dan status pencatatan bukti transaksi');
 const isAdmin=state.me.role==='admin';
 const health=await json('/health');
 const finance=isAdmin && health.mode==='DEMO LOCAL';
 const [d,allTx]=await Promise.all([json(finance?'/finance/summary?year='+financeYear+(financeMonth?'&month='+financeMonth:''):'/dashboard'),loadTx()]);
 if(state.page!=='dashboard')return;
 const rows=finance?allTx.filter(t=>t.transaction_date>=d.start && t.transaction_date<d.end_exclusive):allTx;
 const scope=finance?(financeYear===0?'Semua Tahun':financeMonth?String(financeMonth).padStart(2,'0')+'/'+financeYear:String(financeYear)):'Seluruh periode';
 const months=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
 const chartRows=finance?(financeYear===0?d.annual.map(x=>({label:String(x.year),inc:x.income_cents,out:x.expense_cents})):months.map((m,i)=>({label:m,inc:d.monthly_income[i],out:d.monthly_expense[i]})).filter((_,i)=>!financeMonth||financeMonth===i+1)):[];
 const peak=chartRows.reduce((v,x)=>Math.max(v,x.inc,x.out),0);
 const step=peak?Math.pow(10,Math.floor(Math.log10(peak/4))):100;
 const maxBar=4*Math.ceil((peak||400)/(4*step))*step;
 const drafts=finance?d.drafts:rows.filter(t=>t.status==='DRAFT').length;
 const pending=d.pending_review||0;
 const recentApproved=rows.filter(t=>t.status==='APPROVED').slice(0,5);
 const shortRp=cents=>{
   const val=(cents||0)/100;
   if(val>=1e9)return 'Rp'+(val/1e9).toFixed(1)+'M';
   if(val>=1e6)return 'Rp'+(val/1e6).toFixed(1)+'jt';
   if(val>=1e3)return 'Rp'+(val/1e3).toFixed(0)+'rb';
   return 'Rp'+val.toLocaleString('id-ID');
 };
 const fmtRp=cents=>'Rp'+((cents||0)/100).toLocaleString('id-ID');

 // Donut chart SVG segments
 const palette=['#14b8a6','#f4831e','#3b82f6','#f43f5e','#8b5cf6','#eab308'];
 const totalOut=Math.max(1,d.total_cents||0);
 let offset=0;
 const radius=62, circ=2*Math.PI*radius;
 const segments=(d.categories||[]).map((c,idx)=>{
   const pct=(c.total_cents||0)/totalOut;
   const dash=pct*circ;
   const seg=`<circle cx="88" cy="88" r="${radius}" fill="none" stroke="${palette[idx%palette.length]}" stroke-width="22" stroke-dasharray="${dash} ${circ-dash}" stroke-dashoffset="${-offset}" transform="rotate(-90 88 88)"></circle>`;
   offset+=dash;
   return {...c,pct:Math.round(pct*100),color:palette[idx%palette.length],svg:seg};
 });

 $('#page-content').innerHTML=`
 <div class="dash-toolbar">
   <div><h2>Ringkasan keuangan</h2><p>${h(scope)} · pengeluaran disetujui saja</p></div>
   <div class="dash-toolbar-actions">
     ${finance?`<label class="finance-filter">Tahun <select id="finance-year" aria-label="Tahun laporan">${yearOptions(d)}</select></label><label class="finance-filter">Bulan <select id="finance-month" ${financeYear===0?'disabled':''}><option value="0">Semua</option>${months.map((m,i)=>`<option value="${i+1}" ${financeMonth===i+1?'selected':''}>${m}</option>`).join('')}</select></label>`:''}
     <button class="btn primary" data-nav="upload">+ Upload Bukti</button>
     <button class="btn outline" data-nav="reports">Laporan Excel</button>
   </div>
 </div>

 <div class="dash-kpi-grid">
   <div class="dash-card">
     <div class="dash-card-head">
       <span class="dash-card-title">Total Dana Masuk</span>
       <span class="dash-icon-box dash-icon-in">↓</span>
     </div>
     <div class="dash-val">${fmtRp(d.income_cents||0)}</div>
     <div class="dash-meta">
       <span class="tag-pill tag-in">↗ Dana masuk</span>
       <span>${finance?`${d.income_count} transaksi`:'Nilai global manual'}</span>
       ${isAdmin?`<button class="edit-income-btn" id="btn-set-income">${finance?'+ Catat':'Atur'}</button>`:''}
     </div>
   </div>

   <div class="dash-card">
     <div class="dash-card-head">
       <span class="dash-card-title">Total Pengeluaran</span>
       <span class="dash-icon-box dash-icon-out">↑</span>
     </div>
     <div class="dash-val">${fmtRp(d.total_cents||0)}</div>
     <div class="dash-meta">
       <span class="tag-pill tag-out">↗ Dana keluar</span>
       <span>${d.receipt_count||0} transaksi</span>
     </div>
   </div>

   <div class="dash-card">
     <div class="dash-card-head">
       <span class="dash-card-title">Selisih Tercatat</span>
       <span class="dash-icon-box dash-icon-net">▣</span>
     </div>
     <div class="dash-val">${fmtRp(d.net_cents||0)}</div>
     <div class="dash-meta">
       <span> Dana masuk − pengeluaran</span><span> Bukan saldo bank</span>
     </div>
   </div>
 </div>

 ${finance && d.legacy_income_cents? `<div class="notice mt">Dana masuk lama tanpa tanggal: ${fmtRp(d.legacy_income_cents)}. Tidak dihitung dalam laporan periode. Nilai lama tetap tersimpan.</div>`:''}
 ${finance?`<section class="dash-card mt"><div class="chart-header"><div><h3>Arus Kas ${h(scope)}</h3><small>Pemasukan tercatat dan pengeluaran disetujui</small></div><div class="chart-legend"><span><i class="dot-sq" style="background:#14b8a6"></i>Pemasukan</span><span><i class="dot-sq" style="background:#f4831e"></i>Pengeluaran</span></div></div>
 <div class="finance-chart-scroll"><div class="finance-chart" style="min-width:${Math.max(280,chartRows.length*38+82)}px"><div class="finance-axis">${[4,3,2,1,0].map(n=>`<span>${shortRp(maxBar*n/4)}</span>`).join('')}</div><div class="finance-plot"><div class="finance-gridlines">${[0,1,2,3,4].map(()=>'<i></i>').join('')}</div><div class="finance-bars" style="grid-template-columns:repeat(${Math.max(1,chartRows.length)}, minmax(0,1fr))">${chartRows.map(x=>`<div class="month-col"><div class="finance-bar-pair"><div class="bar-in" style="height:${x.inc/maxBar*100}%;min-height:0" title="${h(x.label)}: ${fmtRp(x.inc)}"></div><div class="bar-out" style="height:${x.out/maxBar*100}%;min-height:0;background:#f4831e" title="${h(x.label)}: ${fmtRp(x.out)}"></div></div><span class="month-lbl">${h(x.label)}</span></div>`).join('')}</div></div></div></div>${chartRows.length?'':'<p class="tiny muted">Belum ada transaksi resmi.</p>'}
 <p class="tiny muted">Grafik mengikuti periode pilihan. Arahkan kursor ke batang untuk nominal.</p></section>`:''}
 <div class="analytics-grid">
   <section class="dash-card dash-work-panel">
     <div class="chart-header"><div><h3>Perlu perhatian</h3><small>Selesaikan pencatatan sebelum masuk laporan</small></div></div>
     <div class="dash-work-row"><div><strong>Draft kuitansi</strong><small>Belum diajukan untuk pemeriksaan</small></div><b>${drafts}</b><button class="btn outline" data-nav="upload">Periksa</button></div>
     ${isAdmin?`<div class="dash-work-row"><div><strong>Menunggu review</strong><small>Belum masuk total pengeluaran</small></div><b>${pending}</b><button class="btn outline" data-nav="reviews">Review</button></div>`:`<div class="dash-work-row"><div><strong>Menunggu review</strong><small>Belum masuk total pengeluaran</small></div><b>${pending}</b></div>`}
     <p class="dash-period-note">${finance?'Antrean draft dan review mencakup semua periode.':'Grafik bulanan tersedia hanya pada preview lokal; ringkasan ini belum difilter berdasarkan tahun.'}</p>
   </section>

   <section class="dash-card">
     <div class="chart-header">
       <div>
         <h3>Pengeluaran Terbesar</h3>
         <small>Distribusi berdasarkan kategori</small>
       </div>
       <span class="year-badge">${h(scope)}</span>
     </div>
     <div class="donut-box">
       <div class="donut-svg-wrap">
         <svg width="176" height="176" viewBox="0 0 176 176">
           <circle cx="88" cy="88" r="${radius}" fill="none" stroke="#f1f5f9" stroke-width="22"></circle>
           ${segments.map(s=>s.svg).join('')}
         </svg>
         <div class="donut-center">
           <small>TOTAL</small>
           <strong>${shortRp(d.total_cents||0)}</strong>
         </div>
       </div>
       <div class="donut-legends">
         ${segments.length?segments.map(s=>`
           <div class="donut-leg-item">
             <span><i class="dot-sq" style="background:${s.color};border-radius:50%"></i>${h(s.category)}</span>
             <strong>${s.pct}%</strong>
           </div>`).join(''):'<div class="tiny muted" style="text-align:center">Belum ada pengeluaran disetujui</div>'}
       </div>
     </div>
   </section>
 </div>

 ${finance?`<section class="dash-card mt"><div class="chart-header"><div><h3>Riwayat Pemasukan</h3><small>Catatan dana masuk pada periode pilihan</small></div></div>
 ${d.incomes.length?`<div class="tablescroll"><table class="data-table"><thead><tr><th>Tanggal</th><th>Keterangan</th><th>Pengirim</th><th>Nama Kontrak</th><th>Nomor Kontrak</th><th>Nominal</th><th>Status</th><th>Aksi</th></tr></thead><tbody>${d.incomes.map(i=>`<tr><td>${h(i.transaction_date)}</td><td>${h(i.description)}</td><td>${h(i.sender||'—')}</td><td>${h(i.contract_name||'—')}</td><td>${h(i.contract_number||'—')}</td><td>${fmtRp(i.amount_cents)}</td><td>${pill(i.reversed_at?'REVERSED':'APPROVED')}</td><td>${i.reversed_at?h(i.reversal_reason):`<button class="btn danger" data-income-reverse="${h(i.id)}">Batalkan</button>`}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">Belum ada pemasukan pada periode ini.</div>'}</section>`:''}
 <section class="dash-card mt">
   <div class="chart-header" style="margin-bottom:10px">
     <div>
       <h3>Pengeluaran Terbaru</h3>
       <small>Transaksi pengeluaran yang sudah disetujui</small>
     </div>
     <button class="btn outline" style="border:none;color:#10b981;font-weight:700" data-nav="transactions">Lihat semua →</button>
   </div>
   ${recentApproved.length?`<div class="tablescroll"><table class="data-table">
     <thead><tr><th>TANGGAL</th><th>KETERANGAN</th><th>VENDOR</th><th>JENIS</th><th>NOMINAL</th><th>STATUS</th></tr></thead>
     <tbody>${recentApproved.map(t=>`<tr>
       <td class="nowrap">${h(t.transaction_date||'—')}</td>
       <td>
         <strong>${t.invoice_number?'No. Dokumen : '+h(t.invoice_number):h(t.description||'Belum diisi')}</strong>
         <div class="tiny muted">${h(t.description||'')}</div>
       </td>
       <td>${h(t.vendor||'—')}</td>
       <td><span class="tag-pill tag-out">↗ Pengeluaran</span></td>
       <td class="nowrap"><strong>${fmtRp(t.amount_cents||0)}</strong></td>
       <td>${pill(t.status)}</td>
     </tr>`).join('')}</tbody>
   </table></div>`:'<div class="empty">Belum ada pengeluaran disetujui pada periode ini.</div>'}
 </section>`;

 if(finance){
   $('#finance-year').onchange=e=>financePeriodChange(e,'dashboard');
   $('#finance-month').onchange=async e=>{financeMonth=Number(e.target.value);await nav('dashboard')};
   document.querySelectorAll('[data-income-reverse]').forEach(btn=>btn.onclick=async()=>{const reason=prompt('Alasan pembatalan pemasukan (minimal 5 karakter):');if(!reason)return;if(!confirm('Batalkan pemasukan ini? Histori tetap tersimpan.'))return;btn.disabled=true;try{await post('/finance/income/'+btn.dataset.incomeReverse+'/reverse',{reason});await nav('dashboard')}catch(e){toast(e.message,true);btn.disabled=false}});
 }
 const incBtn=$('#btn-set-income');
 if(incBtn)incBtn.onclick=async()=>{
   if(finance){
     const requestId=crypto.randomUUID();
     const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Jakarta',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
     modal('Catat Pemasukan',`<form id="income-form" class="grid2">${field('Tanggal','transaction_date',today,'date',true)}${field('Nominal (rupiah, tanpa pemisah)','amount','','number',true,'min="1" max="999999999999" step="1"')}${field('Keterangan','description','','text',true,'maxlength="500"')}${field('Transfer dari / pengirim','sender','','text',false,'maxlength="200"')}${field('Nama Kontrak','contract_name','','text',false,'maxlength="300"')}${field('Nomor Kontrak','contract_number','','text',false,'maxlength="120"')}<div><button class="btn primary" type="submit">Simpan Pemasukan</button></div></form><p class="tiny muted">Catat dana yang benar-benar diterima. Gunakan data simulasi saja.</p>`);
     $('#income-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const data=Object.fromEntries(new FormData(form));const amt=Number(data.amount);if(!Number.isSafeInteger(amt)||amt<=0||amt>999999999999)return toast('Nominal tidak valid',true);const btn=form.querySelector('button');btn.disabled=true;try{await post('/finance/income',{request_id:requestId,transaction_date:data.transaction_date,amount_cents:amt*100,description:data.description,sender:data.sender,contract_name:data.contract_name,contract_number:data.contract_number});closeModal();toast('Pemasukan tercatat');financeYear=0;financeMonth=0;await nav('dashboard')}catch(err){toast(err.message,true);btn.disabled=false}};
     return;
   }
   const raw=prompt('Masukkan total pemasukan / anggaran kas (IDR), contoh: 100000000', String((d.income_cents||0)/100));
   if(raw===null)return;
   const num=Number(raw.replace(/[^0-9.]/g,''));
   if(Number.isNaN(num)||num<0)return toast('Nominal tidak valid',true);
   try{
     await post('/dashboard/income',{income_cents:Math.round(num*100)});
     toast('Total pemasukan diperbarui');
     await dashboard();
   }catch(e){toast(e.message,true);}
 };
}
// Tesseract is loaded only when users upload an image. This preserves the main
// app's load time and keeps OCR processing out of the backend Gemini code path.
let ocrBundlePromise=null;
function loadBrowserOCR(){
  if(window.MHSReceiptOCR?.release==='phase3-final')return Promise.resolve(window.MHSReceiptOCR);
  if(!ocrBundlePromise){
    ocrBundlePromise=new Promise((resolve,reject)=>{
      const script=document.createElement('script');
      script.src='/assets/ocr-engine.final.bundle.js';
      script.onload=()=>window.MHSReceiptOCR?.release==='phase3-final' ? resolve(window.MHSReceiptOCR) : reject(new Error('Bundle OCR tidak menyiapkan mesin Tesseract.'));
      script.onerror=()=>reject(new Error('Bundle OCR belum dibangun. Jalankan npm.cmd exec -- esbuild .\\ocr-engine-entry.js --bundle --platform=browser --format=iife --outfile=.\\assets\\ocr-engine.final.bundle.js dari folder frontend.'));
      document.head.appendChild(script);
    }).catch(err=>{ocrBundlePromise=null;throw err});
  }
  return ocrBundlePromise;
}

function isImageOCRFile(file){return ['image/png','image/jpeg','image/webp','application/pdf'].includes(String(file?.type||'').toLowerCase())}
async function recognizeReceipt(engine,file,id,progress,deep=false){
  if(file.type==='application/pdf')return engine.recognizePdf((page,raster)=>json('/transactions/'+encodeURIComponent(id)+'/pdf-ocr-page?page='+page+'&raster='+raster),progress,{deep});
  return engine.recognize(file,progress,{deep});
}

async function saveHybridOCR(id,result,progress){
  let run=null;
  if(result)run=await post('/transactions/'+id+'/ocr-result',{text:result.text.slice(0,16000),confidence:result.confidence,suggestions:result.suggestions});
  progress('Memeriksa dengan PaddleOCR lokal',null);
  const paddle=await post('/transactions/'+id+'/paddle-ocr',{browser_run_id:run?.run_id||null});
  if(paddle.status!=='EXTRACTED'&&!run)throw Error(paddle.message||'OCR tidak tersedia');
  const enriched=await json('/transactions/'+id+'/ocr-result');
  return {...enriched,paddle_status:paddle.status,paddle_error:paddle.error_code||null};
}


const uploadPending=new Set();
let uploadProgress='';
let draftSubmitting=false;
function draftMissing(t){
  return [['transaction_date','Tanggal'],['amount_cents','Nominal'],['description','Keterangan'],['category_id','Kategori']].filter(([key])=>t[key]===null||t[key]===undefined||String(t[key]).trim()==='').map(([,label])=>label);
}
function draftReady(t){return t.status==='DRAFT'&&!uploadPending.has(t.id)&&!draftMissing(t).length}
function updateDraftControls(){
  const grid=$('#draft-batch-grid');if(!grid||state.page!=='upload')return;
  const drafts=state.transactions.filter(t=>t.status==='DRAFT'),ready=drafts.filter(draftReady);
  for(const box of grid.querySelectorAll('.select-draft')){const t=drafts.find(x=>x.id===box.value);box.disabled=draftSubmitting||!t||!draftReady(t)}
  const checked=[...grid.querySelectorAll('.select-draft:checked:not(:disabled)')];
  const stats=$('#draft-readiness');if(stats)stats.textContent=ready.length+' lengkap · '+drafts.filter(t=>uploadPending.has(t.id)).length+' diproses OCR · '+drafts.filter(t=>!uploadPending.has(t.id)&&draftMissing(t).length).length+' belum lengkap';
  const count=$('#draft-selection-count');if(count)count.textContent=checked.length+' dipilih';
  const submit=$('#submit-selected');if(submit)submit.disabled=draftSubmitting||!checked.length;
  const all=$('#draft-select-ready');if(all)all.disabled=draftSubmitting||!ready.length;
}

function draftBatchRows(drafts,selected=new Set()){
  return drafts.length?drafts.map(t=>{
        const risks=(()=>{try{return JSON.parse(t.risk_reasons||'[]')}catch{return []}})();
        const ocr=state.ocrStatus.get(t.id);
        const pending=uploadPending.has(t.id);
        const missing=draftMissing(t);const ready=draftReady(t);
        return `<div class="draft-item"><div class="details"><label class="checkrow"><input type="checkbox" class="select-draft" value="${h(t.id)}" ${!ready?'disabled':(draftSubmitting?'disabled ':'')+(selected.has(t.id)?'checked':'')}><strong>${h(t.description||'Draft kuitansi')}</strong></label>
          <p>${h(t.activity_name)} • ${t.amount_cents==null?'Nominal belum diisi':rp(t.amount_cents)} • ${h(t.transaction_date||'Tanggal belum diisi')}</p>
          <div>${pill(t.status)} ${risks.map(x=>`<span class="pill PENDING">${h(x)}</span>`).join('')}</div>
          <p class="tiny"><b>${pending?'Sedang diproses':ready?'Data wajib lengkap — siap diajukan':'Belum lengkap: '+h(missing.join(', '))}</b></p>
          ${ocr?`<p class="tiny muted">OCR: ${h(ocr)}</p>`:''}</div>
          <div class="inline-actions"><button class="btn soft" data-edit="${h(t.id)}" ${pending?'disabled':''}>${pending?'OCR berlangsung…':'Periksa &amp; Edit'}</button><button class="btn danger" data-delete="${h(t.id)}" ${pending?'disabled':''}>Hapus Draft</button></div></div>`;
      }).join(''):'<div class="empty">Belum ada draft. Unggah kuitansi terlebih dahulu.</div>';
}
function refreshDraftBatch(){
  if(state.page!=='upload')return;
  const grid=$('#draft-batch-grid');
  if(!grid)return;
  const selected=new Set([...grid.querySelectorAll('.select-draft:checked')].map(x=>x.value));
  const drafts=state.transactions.filter(t=>t.status==='DRAFT');
  grid.innerHTML=draftBatchRows(drafts,selected);
  const count=$('#draft-batch-count');if(count)count.textContent=String(drafts.length);
  updateDraftControls();
}
function updateUploadProgress(message){
  uploadProgress=message;
  if(state.page==='upload'){
    const e=$('#ocr-upload-progress');if(e)e.textContent=message;
  }
}
async function reloadDraftBatch(){
  try{await loadTx();refreshDraftBatch();const retry=$('#draft-reload');if(retry)retry.hidden=true;return true}
  catch(err){console.warn('Draft refresh failed:',err.message);const retry=$('#draft-reload');if(retry)retry.hidden=false;return false}
}
let lastUploadActivity='';
function preferredUploadActivity(activities,previous){
 if(activities.some(a=>a.id===previous&&a.closure_status==='OPEN'))return previous;
 const open=activities.filter(a=>a.closure_status==='OPEN');
 return open.length===1?open[0].id:null;
}
async function uploadPage(){
  setHead('Upload Receipt','Unggah kuitansi, periksa data, lalu ajukan untuk pencatatan.');
  await loadTx();
  if(state.page!=='upload')return;
  const acts=state.config.activities;
  const drafts=state.transactions.filter(t=>t.status==='DRAFT');
  $('#page-content').innerHTML=`
    <div class="owner-steps" aria-label="Alur pencatatan kuitansi"><div><b>01</b><span><strong>Unggah</strong><small>Pilih aktivitas dan kuitansi</small></span></div><div><b>02</b><span><strong>Periksa</strong><small>Lengkapi hasil pembacaan</small></span></div><div><b>03</b><span><strong>Ajukan</strong><small>Masuk antrean persetujuan</small></span></div></div>
    <div class="two-panel owner-upload-panels">
      <section class="panel panelpad">
        <h3>Unggah kuitansi</h3>
        <p class="muted">Satu kuitansi menghasilkan satu transaksi. PDF, PNG, JPEG, atau WEBP — maksimal 8 MB.</p>
        <form id="batch-form">
          <div class="field mt"><label>Aktivitas*</label><select name="activity_id" required>${opts(acts,preferredUploadActivity(acts,lastUploadActivity),'Pilih aktivitas...')}</select></div>
          <div class="uploadbox"><strong>↥ Upload kuitansi</strong>
            <p class="muted tiny">Boleh pilih beberapa file sekaligus. Setiap kuitansi disimpan sebagai draft.</p>
            <input id="upload-files" name="files" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" multiple required>
          </div>
          <p id="upload-file-summary" class="tiny muted" aria-live="polite">Belum ada file dipilih.</p>
          <div class="mt row wrap"><button class="btn primary" id="batch-upload-button" type="submit" ${ocrBusy?'disabled':''}>Upload &amp; Buat Draft →</button>
            <span class="tiny muted">Pembacaan otomatis gambar dan PDF hingga 5 halaman. Data yang kurang dapat diisi manual.</span></div>
          <p id="ocr-upload-progress" role="status" aria-live="polite" class="tiny muted mt">${h(uploadProgress)}</p>
        </form>
      </section>
      <section class="panel panelpad"><h3>Setelah upload</h3>
        <p class="muted">Kuitansi yang siap dapat disubmit tanpa menunggu kuitansi lain.</p>
        <div class="notice mt">Cocokkan nominal dan tanggal dengan kuitansi asli. Hasil pembacaan otomatis belum menjadi data resmi sebelum disetujui.</div>
        <div class="owner-draft-total"><strong id="draft-batch-count">${drafts.length}</strong><span>draft aktif tersedia</span></div>
      </section>
    </div>
    <section class="panel mt"><div class="panelhead"><div><h3>Draft Batch Review</h3><small>Pilih draft lengkap untuk submit; dapat dilakukan sebagian.</small></div><div class="inline-actions"><button class="btn outline" id="draft-select-ready" type="button">Pilih semua yang lengkap</button><button class="btn primary" id="submit-selected" disabled>Submit Terpilih →</button></div></div><div class="panelpad"><div id="draft-readiness" class="tiny muted"></div><div id="draft-selection-count" class="tiny" aria-live="polite"></div><button id="draft-reload" type="button" class="btn outline mt" hidden>Muat ulang daftar draft</button></div>
      <div id="draft-batch-grid" class="panelpad draftgrid">
      ${draftBatchRows(drafts)}
      </div>
    </section>`;

  const form=$('#batch-form');
  const select=form.elements.activity_id,fileInput=form.elements.files,fileSummary=$('#upload-file-summary');
  select.onchange=()=>{lastUploadActivity=select.value};
  fileInput.onchange=()=>{const files=[...fileInput.files];fileSummary.textContent=files.length?files.length+' file dipilih · '+storageSize(files.reduce((n,f)=>n+f.size,0)):'Belum ada file dipilih.'};
  form.addEventListener('submit',async ev=>{
    ev.preventDefault();
    const activity_id=new FormData(form).get('activity_id');
    lastUploadActivity=activity_id;
    const files=[...$('#upload-files').files];
    if(!files.length)return toast('Pilih kuitansi terlebih dahulu',true);
    if(files.some(f=>f.size>8*1024*1024 || !f.size))return toast('Setiap file harus terisi dan berukuran maksimum 8 MB.',true);
    const btn=$('#batch-upload-button');
    const progress=updateUploadProgress;
    if(ocrBusy)return toast('OCR lain sedang berjalan. Tunggu proses selesai.',true);
    ocrBusy=true;btn.disabled=true;
    const successes=[],failures=[];
    try{
      progress(`Menyiapkan batch ${files.length} kuitansi...`);
      const batch=await post('/batches',{activity_id});
      for(const file of files){
        progress(`Mengunggah ${successes.length+failures.length+1}/${files.length}: ${file.name}`);
        try{
          const fd=new FormData();fd.append('file',file);
          const uploaded=await json('/batches/'+batch.id+'/documents',{method:'POST',body:fd});
          const id=uploaded.transaction_id;
          successes.push({file,id});
          uploadPending.add(id);
          state.ocrStatus.set(id,'Draft tersimpan — menunggu OCR');
          await reloadDraftBatch();
        }catch(err){failures.push(`${file.name}: ${err.message}`)}
      }

      // A failed OCR never removes the original file or its saved draft.
      const images=successes.filter(({file})=>isImageOCRFile(file));
      let ocr=null;
      if(images.length){
        try{ocr=await loadBrowserOCR()}
        catch(err){for(const item of images)state.ocrStatus.set(item.id,`Belum diproses: ${err.message}`)}
      }
      if(images.length){
        try{
          let count=0;
          for(const {file,id} of images){
            count++;
            const report=(status,pct)=>progress(`OCR ${count}/${images.length} — ${file.name}: ${status}${pct===null?'':' '+pct+'%'}`);
            try{
              state.ocrStatus.set(id,'Sedang diproses OCR…');refreshDraftBatch();
              let result=null;
              if(ocr)try{result=await recognizeReceipt(ocr,file,id,report)}catch(err){console.warn('Tesseract gagal:',err.message)}
              const enriched=await saveHybridOCR(id,result,report);
              state.ocrResults.set(id,enriched);
              state.ocrStatus.set(id,enriched.paddle_status==='EXTRACTED'?'PaddleOCR selesai; belum diverifikasi':'Tesseract saja — PaddleOCR '+(enriched.paddle_error||enriched.paddle_status));
            }catch(err){state.ocrStatus.set(id,`OCR gagal: ${err.message}. Isi manual.`)}
            finally{uploadPending.delete(id);refreshDraftBatch()}
          }
        }finally{
          if(ocr)try{await ocr.close()}catch(err){console.warn('Menutup OCR worker:',err)}
        }
      }
      for(const {file,id} of successes.filter(x=>!isImageOCRFile(x.file))){
        uploadPending.delete(id);
        state.ocrStatus.set(id,`${file.name}: Format tidak didukung OCR; isi manual.`);
      }
      const refreshed=await reloadDraftBatch();
      if(form.isConnected&&successes.length){form.elements.files.value='';fileSummary.textContent='Belum ada file dipilih.';}
      progress(`${successes.length} draft tersimpan; ${failures.length} gagal diunggah. ${refreshed?'Periksa hasil sebelum submit.':'Daftar belum tersinkron; gunakan Muat ulang daftar draft.'}`);
      toast(`${successes.length} draft berhasil dibuat${failures.length?`; ${failures.length} gagal diunggah`:''}. Periksa & Edit sebelum submit.`,!!failures.length);
      if(failures.length)console.warn('Upload gagal:',failures);
    }catch(err){
      toast(`Upload gagal: ${err.message}`,true);
      await reloadDraftBatch();
      progress('Proses terhenti; draft yang tersimpan tetap tersedia.');
    }finally{
      for(const {id} of successes)uploadPending.delete(id);
      ocrBusy=false;btn.disabled=false;
      if(state.page==='upload'){const current=$('#batch-upload-button');if(current)current.disabled=false;refreshDraftBatch()}
    }
  });

  $('#draft-reload').onclick=async()=>{if(!await reloadDraftBatch())toast('Daftar belum dapat dimuat. Coba lagi.',true)};
  $('#draft-batch-grid').addEventListener('change',updateDraftControls);
  $('#draft-select-ready').onclick=()=>{const boxes=[...$('#draft-batch-grid').querySelectorAll('.select-draft:not(:disabled)')];const select=boxes.some(x=>!x.checked);boxes.forEach(x=>x.checked=select);updateDraftControls()};
  updateDraftControls();
  $('#submit-selected').addEventListener('click',async()=>{
    if(draftSubmitting)return;
    const ids=[...document.querySelectorAll('.select-draft:checked')].map(x=>x.value);
    if(!ids.length)return toast('Pilih minimal satu draft',true);
    try{
      if(ids.some(id=>!state.transactions.some(t=>t.id===id&&draftReady(t))))throw Error('Pilih draft aktif dengan data wajib lengkap.');
      if(ids.length>100)throw Error('Pilih maksimal 100 draft per pengajuan.');
      const closed=ids.some(id=>{const t=state.transactions.find(t=>t.id===id);return state.config.activities.find(a=>a.id===t.activity_id)?.closure_status==='CLOSED'});
      const late_reason=closed?prompt('Aktivitas telah ditutup. Isi alasan keterlambatan (wajib):'):null;
      if(closed&&!late_reason?.trim())return;
      if(!confirm('Ajukan '+ids.length+' draft terpilih? Pengeluaran hanya masuk laporan setelah APPROVED.'))return;
      draftSubmitting=true;updateDraftControls();
      const result=await post('/transactions/submit-batch',{ids,late_reason});
      const pending=result.items.filter(x=>x.status==='PENDING_REVIEW').length;
      const approved=result.items.filter(x=>x.status==='APPROVED').length;
      toast(`${result.items.length} diajukan · ${pending} menunggu review · ${approved} disetujui`);
      await reloadDraftBatch();
    }catch(err){toast(err.message,true)}finally{draftSubmitting=false;refreshDraftBatch();updateDraftControls()}
  });
}

// OCR evidence is never an instruction or a verified accounting value.
let ocrBusy=false;
function renderOCREvidence(result){
  if(!result)return '<p class="tiny">Belum ada hasil OCR. Isi manual atau coba baca ulang dokumen asli.</p>';
  const suggestions=result.suggestions||{};
  const money=Array.isArray(result.amount_review)?result.amount_review:[];
  const warnings=Array.isArray(result.amount_warnings)?result.amount_warnings:[];
  const kindNames={bruto:'Bruto / insentif',neto:'Neto / diterima',total:'Total',potongan_pajak:'Potongan pajak',terbilang:'Terbilang',generic:'Angka tanpa label pasti'};
  const valid=x=>x&&Number.isFinite(Number(x.value))&&Number(x.value)>0&&Number(x.value)<=999999999999;
  const moneyRows=money.filter(valid).map(x=>`<div class="ocr-evidence-row"><div><b>${h(kindNames[x.kind]||'Kandidat nominal')} · ${rp(Math.round(Number(x.value)*100))}</b><small>${h(x.label||'Periksa dokumen asli')}</small><small>${h(x.reason||'Periksa manual')}</small></div>${x.usable===true?`<button type="button" class="btn soft" data-ocr-amount="${h(x.value)}">Pakai</button>`:'<span class="tiny">Periksa manual</span>'}</div>`).join('');
  const dates=(Array.isArray(suggestions.dates)?suggestions.dates:[]).filter(x=>typeof x==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x));
  const dateRows=dates.map(x=>`<button type="button" class="btn soft" data-ocr-date="${h(x)}">Pakai ${h(x)}</button>`).join(' ');
  const context=Array.isArray(result.date_context)?result.date_context:[];
  const fields=result.field_candidates||{};
  const fieldNames={vendor:'Vendor',description:'Keterangan',payment_method:'Metode pembayaran',invoice_number:'Nomor invoice / dokumen',contract_name:'Nama Kontrak',contract_number:'Nomor Kontrak'};
  const fieldRows=Object.entries(fieldNames).map(([key,label])=>{
    const values=Array.isArray(fields[key])?fields[key].filter(x=>typeof x==='string').slice(0,3):[];
    return values.length?`<div class="ocr-field-group"><b class="tiny">${label}</b>${values.map(v=>`<div class="ocr-evidence-row"><small>${h(v)}</small><button type="button" class="btn soft" data-ocr-field="${key}" data-ocr-value="${h(v)}">Pakai</button></div>`).join('')}</div>`:'';
  }).join('');
  // Keyword suggestions come exclusively from explicit description candidates.
  const descriptions=(Array.isArray(fields.description)?fields.description:[]).join(' ');
  const categoryRules=[[/\b(?:laptop|notebook|komputer|printer|alat\s+tulis|atk)\b/i,'Peralatan Kantor / IT'],[/\b(?:honorarium|insentif)\b/i,'Honorarium / Insentif'],[/\b(?:transportasi|taksi|parkir|tol)\b/i,'Transportasi']];
  const cats=categoryRules.filter(([rx])=>rx.test(descriptions)).map(([,name])=>state.config.categories.find(c=>c.name===name)).filter(Boolean);
  return `<p class="tiny">Cocokkan setiap saran dengan dokumen asli. Bruto, neto, dan potongan pajak bukan nilai yang dapat dipertukarkan.</p>
   ${warnings.length?`<div class="ocr-context"><b>Periksa nominal</b>${warnings.map(x=>`<p>${h(x)}</p>`).join('')}</div>`:''}
   ${result.engine_scores?`<p class="tiny">Skor mesin (bukan akurasi): ${Object.entries(result.engine_scores).map(([name,score])=>h(name)+': '+(Number.isFinite(score)?Math.round(score)+'%':'tidak tersedia')).join(' · ')}</p>`:''}
   <b class="tiny">Kandidat nominal</b>${moneyRows||'<p class="tiny muted">Tidak terdeteksi. Isi manual.</p>'}
   <b class="tiny">Kandidat tanggal</b><div class="row wrap" style="gap:6px">${dateRows||'<span class="tiny muted">Tidak terdeteksi. Isi manual.</span>'}</div>
   ${context.length?`<div class="ocr-context"><b>Tanggal referensi surat mungkin bukan tanggal pembayaran.</b>${context.map(x=>`<p>${h(x)}</p>`).join('')}</div>`:''}
   ${fieldRows||'<p class="tiny muted">Tidak ada kandidat vendor, keterangan, metode bayar atau nomor dokumen yang cukup jelas.</p>'}
   ${cats.length?`<b class="tiny">Saran kategori berdasarkan keterangan</b><div class="row wrap">${cats.map(c=>`<button type="button" class="btn soft" data-ocr-field="category_name" data-ocr-value="${h(c.name)}">${h(c.name)}</button>`).join('')}</div>`:''}
   <details class="mt"><summary>Teks mentah OCR (${Number.isFinite(result.confidence)?Math.round(result.confidence)+'% skor mesin':'tanpa skor'}; bukan akurasi terukur)</summary><pre style="white-space:pre-wrap;word-break:break-word;max-height:220px;overflow:auto">${h((result.text||'').slice(0,16000))}</pre></details>`;
}

async function editDraft(id){
  const t=state.transactions.find(x=>x.id===id)||(await loadTx()).find(x=>x.id===id);
  if(!t)return toast('Draft tidak ditemukan',true);
  let result=state.ocrResults.get(id);
  try{result=await json('/transactions/'+id+'/ocr-result');state.ocrResults.set(id,result)}
  catch(err){if(!result)result=null}
  function contractValue(key) {
    const candidates=result?.field_candidates?.[key];
    return t[key] ?? (candidates?.length===1 ? candidates[0] : '');
  }
  const ocrPanel=`<div class="notice" style="grid-column:1/-1"><b>Saran OCR — BELUM DIVERIFIKASI</b><div id="ocr-evidence">${renderOCREvidence(result)}</div><div class="mt row wrap"><button type="button" class="btn outline" id="retry-ocr">Baca ulang dokumen (mendalam)</button><span class="tiny" id="retry-ocr-status" role="status"></span></div></div>`;
  let existingRisks=[];try{existingRisks=JSON.parse(t.risk_reasons||'[]')}catch{}
  const mixed=existingRisks.some(x=>/beberapa kategori/i.test(x));
  const body=`<div class="notice">Semua hasil OCR merupakan saran. Data resmi belum berubah sampai kamu menyimpan draft dan mengikuti approval.</div>
    <div class="grid2 mt"><div><p><b>Kuitansi asli</b></p><iframe title="Kuitansi" src="/api/receipts/${h(t.document_id)}" style="width:100%;height:350px;border:1px solid #eee;border-radius:10px"></iframe><a class="document-link" href="/api/receipts/${h(t.document_id)}" target="_blank" rel="noopener">Lihat dokumen ukuran penuh ↗</a></div>
    <form id="draft-form" class="grid2" style="align-content:start">${ocrPanel}
      ${field('Tanggal transaksi*','transaction_date',t.transaction_date||'','date',true)}
      ${field('Nominal IDR*','amount',t.amount_cents===null?'':t.amount_cents/100,'number',true,'min="0" step="0.01"')}
      ${field('Kategori*','category_name',t.category_name||'','text',true,'maxlength="120"')}
      ${field('Vendor','vendor',t.vendor||'')}
      ${field('Keterangan*','description',t.description||'','text',true)}
      ${field('Metode Pembayaran','payment_method',t.payment_method||'')}
      ${field('Nama Kontrak','contract_name',contractValue('contract_name'),'text',false,'maxlength="300"')}${field('Nomor Kontrak','contract_number',contractValue('contract_number'),'text',false,'maxlength="120"')}
      ${field('Nomor Invoice','invoice_number',t.invoice_number||'')}
      <div class="field"><label>Catatan</label><textarea name="notes">${h(t.notes||'')}</textarea></div>
      <label class="checkrow" style="grid-column:1/-1"><input type="checkbox" name="mixed_receipt" ${mixed?'checked':''}>Kuitansi ini mencakup beberapa kategori</label>
      <button type="submit" class="btn primary" style="grid-column:1/-1">Simpan Draft</button>
    </form></div>`;
  modal('Periksa & Lengkapi Kuitansi',body,'<button class="btn outline" id="modal-done">Tutup</button>');
  $('#modal-done').onclick=closeModal;
  const draftForm=$('#draft-form');
  const editedFields=new Set();
  draftForm.addEventListener('input', event=>editedFields.add(event.target.name));
  draftForm.addEventListener('click',ev=>{
    const amount=ev.target.closest('[data-ocr-amount]');
    if(amount){draftForm.elements.amount.value=amount.dataset.ocrAmount;return}
    const date=ev.target.closest('[data-ocr-date]');
    if(date){draftForm.elements.transaction_date.value=date.dataset.ocrDate;return}
    const fieldBtn=ev.target.closest('[data-ocr-field]');
    if(fieldBtn && ['vendor','description','payment_method','invoice_number','contract_name','contract_number','category_name'].includes(fieldBtn.dataset.ocrField)){
      const field=draftForm.elements.namedItem(fieldBtn.dataset.ocrField);
      if(field){
        field.value=fieldBtn.dataset.ocrValue;
        editedFields.add(field.name);
      }
    }
  });
  $('#retry-ocr').onclick=async()=>{
    if(ocrBusy)return toast('OCR lain sedang berjalan. Tunggu proses selesai.',true);
    const btn=$('#retry-ocr'),status=$('#retry-ocr-status');
    let engine=null;ocrBusy=true;btn.disabled=true;
    try{
      status.textContent='Mengambil dokumen asli...';
      const response=await api('/receipts/'+encodeURIComponent(t.document_id));
      const blob=await response.blob();
      const type=blob.type.split(';')[0].toLowerCase();
      if(!['image/png','image/jpeg','image/webp','application/pdf'].includes(type))throw new Error('Format dokumen tidak didukung.');
      if(blob.size>8*1024*1024||!blob.size)throw new Error('Ukuran dokumen tidak didukung.');
      try{engine=await loadBrowserOCR()}catch(err){console.warn('Tesseract tidak tersedia:',err.message)}
      const file=new File([blob],'receipt.'+({'image/png':'png','image/jpeg':'jpg','image/webp':'webp','application/pdf':'pdf'}[type]),{type});
      const report=(msg,pct)=>{status.textContent=msg+(pct===null?'':' '+pct+'%')};
      let result=null;
      if(engine)try{result=await recognizeReceipt(engine,file,id,report,true)}catch(err){console.warn('Tesseract gagal:',err.message)}
      const enriched=await saveHybridOCR(id,result,report);
      state.ocrResults.set(id,enriched);
      state.ocrStatus.set(id,'OCR dibaca ulang; belum diverifikasi');
      if(draftForm.isConnected){
        for(const key of ['contract_name','contract_number']){
          const candidates=enriched.field_candidates?.[key];
          const input=draftForm.elements.namedItem(key);
          if(t[key]==null && !input.value && !editedFields.has(key) && candidates?.length===1){
            input.value=candidates[0];
          }
        }
        draftForm.querySelector('#ocr-evidence').innerHTML=renderOCREvidence(enriched);status.textContent=(enriched.paddle_status==='EXTRACTED'?'PaddleOCR selesai. ':'PaddleOCR '+(enriched.paddle_error||enriched.paddle_status)+'. ')+'Periksa hasil pembacaan sebelum menyimpan.'}
    }catch(err){status.textContent=err.message;toast(err.message,true)}
    finally{if(engine)try{await engine.close()}catch{}ocrBusy=false;btn.disabled=false}
  };
  draftForm.onsubmit=async ev=>{
    ev.preventDefault();
    const f=new FormData(draftForm);
    const o=Object.fromEntries(f.entries());
    o.mixed_receipt=!!f.get('mixed_receipt');
    const activity=state.config.activities.find(a=>a.id===t.activity_id);
    const activityYears=(activity?.name||'').match(/\b(?:19|20)\d{2}\b/g)||[];
    const receiptYear=String(o.transaction_date||'').slice(0,4);
    if(activityYears.length===1 && receiptYear && receiptYear!==activityYears[0] &&
       !confirm('Tanggal kuitansi '+receiptYear+' berbeda dari tahun pada nama aktivitas '+activityYears[0]+'. Laporan mengikuti tanggal kuitansi. Tetap simpan?'))return;

    o.category_name=o.category_name.trim();
    if(!o.category_name)return toast('Kategori wajib diisi',true);
    try{
      const {category}=await patch('/transactions/'+id+'/draft',o);
      if(category && !state.config.categories.some(c=>c.id===category.id)){
        state.config.categories.push(category);
        state.config.categories.sort((a,b)=>a.name.localeCompare(b.name,'id'));
      }
      toast('Draft berhasil disimpan. OCR tidak otomatis menjadi approval.');
      closeModal();await nav(state.page==='upload'?'upload':'transactions');
    }catch(err){toast(err.message,true)}
  };
}

const txFilter={q:'',status:'ALL',activity:'',category:'',from:'',to:'',sort:'newest'};
function filterTransactions(rows,f){
  const q=f.q.trim().toLowerCase();
  const result=rows.filter(t=>(f.status==='ALL'||t.status===f.status)&&(!f.activity||t.activity_id===f.activity)&&(!f.category||t.category_id===f.category)&&(!f.from||(t.transaction_date&&t.transaction_date>=f.from))&&(!f.to||(t.transaction_date&&t.transaction_date<=f.to))&&(!q||[t.description,t.vendor,t.invoice_number,t.contract_name,t.contract_number,t.activity_name,t.category_name,t.uploader_name].some(v=>String(v??'').toLowerCase().includes(q))));
  if(f.sort==='amount')result.sort((a,b)=>(b.amount_cents??-1)-(a.amount_cents??-1));
  if(f.sort==='date')result.sort((a,b)=>String(b.transaction_date||'').localeCompare(String(a.transaction_date||'')));
  return result;
}
async function transactionsPage(){
  setHead(state.me.role==='admin'?'All Transactions':'My Transactions','Cari, filter, dan periksa histori transaksi');
  const rows=await loadTx();if(state.page!=='transactions')return;
  $('#page-content').innerHTML=`<section class="panel panelpad">
  <div class="grid2"><div class="field"><label for="tx-search">Cari transaksi</label><input id="tx-search" placeholder="Keterangan, vendor, invoice, kontrak..." value="${h(txFilter.q)}"></div>
  <div class="field"><label>Status</label><select id="tx-status"><option value="ALL">Semua status</option>${['DRAFT','PENDING_REVIEW','APPROVED','REJECTED','REVERSED'].map(x=>'<option>'+x+'</option>').join('')}</select></div>
  <div class="field"><label>Aktivitas</label><select id="tx-activity">${opts(state.config.activities,txFilter.activity,'Semua aktivitas')}</select></div>
  <div class="field"><label>Kategori</label><select id="tx-category">${opts(state.config.categories,txFilter.category,'Semua kategori')}</select></div>
  <div class="field"><label>Tanggal mulai</label><input type="date" id="tx-from" value="${h(txFilter.from)}"></div>
  <div class="field"><label>Tanggal akhir</label><input type="date" id="tx-to" value="${h(txFilter.to)}"></div>
  <div class="field"><label>Urutkan</label><select id="tx-sort"><option value="newest">Terakhir dicatat</option><option value="date">Tanggal kuitansi terbaru</option><option value="amount">Nominal terbesar</option></select></div></div>
  <div class="inline-actions mt"><button class="btn outline" id="tx-reset">Reset Filter</button><button class="btn outline" id="tx-refresh">Muat Ulang Data</button><button class="btn outline" data-nav="${state.me.role==='admin'?'reviews':'upload'}">${state.me.role==='admin'?'Review Queue':'Upload Baru'}</button></div>
  <p class="tiny muted" id="tx-count" role="status"></p></section><section class="panel tx-compact mt" id="tx-results"></section>`;
  $('#tx-status').value=txFilter.status;$('#tx-sort').value=txFilter.sort;
  const fields={q:'search',status:'status',activity:'activity',category:'category',from:'from',to:'to',sort:'sort'};
  function filter(){
    for(const [key,id] of Object.entries(fields))txFilter[key]=$('#tx-'+id).value;
    const count=$('#tx-count');
    if(txFilter.from&&txFilter.to&&txFilter.from>txFilter.to){count.textContent='Tanggal mulai tidak boleh setelah tanggal akhir.';$('#tx-results').innerHTML='';return}
    const found=filterTransactions(rows,txFilter);
    count.textContent=found.length+' dari '+rows.length+' transaksi dimuat'+(rows.length>=500?' · Batas API 500 transaksi; hasil tidak mencakup seluruh histori.':'');
    $('#tx-results').innerHTML=txTable(found);
  }
  for(const [key,id] of Object.entries(fields))$('#tx-'+id).addEventListener(key==='q'?'input':'change',filter);
  $('#tx-reset').onclick=()=>{Object.assign(txFilter,{q:'',status:'ALL',activity:'',category:'',from:'',to:'',sort:'newest'});nav('transactions')};
  $('#tx-refresh').onclick=()=>nav('transactions');
  filter();
}
async function details(id){let t=state.transactions.find(t=>t.id===id)|| (await loadTx()).find(t=>t.id===id);if(!t)return;
 let data=await json('/transactions/'+id+'/history');modal('Detail Transaksi',`<div class="grid2"><div><h3>${h(t.description||'Transaksi')}</h3><table class="small-table"><tr><td>Status</td><td>${pill(t.status)}</td></tr><tr><td>Nominal</td><td><b>${rp(t.amount_cents)}</b></td></tr><tr><td>Tanggal</td><td>${h(t.transaction_date)}</td></tr><tr><td>Aktivitas</td><td>${h(t.activity_name)}</td></tr><tr><td>Uploader</td><td>${h(t.uploader_name)}</td></tr><tr><td>Kategori</td><td>${h(t.category_name)}</td></tr><tr><td>Vendor</td><td>${h(t.vendor||'—')}</td></tr><tr><td>Metode pembayaran</td><td>${h(t.payment_method||'—')}</td></tr><tr><td>Nama Kontrak</td><td>${h(t.contract_name||'—')}</td></tr><tr><td>Nomor Kontrak</td><td>${h(t.contract_number||'—')}</td></tr><tr><td>Invoice</td><td>${h(t.invoice_number||'—')}</td></tr><tr><td>Catatan</td><td>${h(t.notes||'—')}</td></tr></table><p class="tiny muted">${t.status==='APPROVED'?'Termasuk pengeluaran laporan terbaru sesuai periode.':'Tidak termasuk pengeluaran APPROVED.'}</p>${t.rejected_reason?`<p class="notice">Alasan penolakan: ${h(t.rejected_reason)}</p>`:''}<a target="_blank" href="/api/receipts/${t.document_id}">Buka kuitansi aktif ↗</a><h4>Versi dokumen</h4>${data.versions.map(v=>`<div class="tiny"><a target="_blank" href="/api/receipts/${t.document_id}?version=${v.version_number}">Versi ${v.version_number}: ${h(v.filename)}</a></div>`).join('')}</div><div><h3>Audit Trail</h3>${data.audit.length?data.audit.map(a=>`<div class="hint mb"><b>${h(a.action)}</b><div class="tiny muted">${short(a.created_at)}</div>${a.details?`<details class="tiny"><summary>Detail kejadian</summary><div style="overflow-wrap:anywhere;white-space:pre-wrap">${h(a.details)}</div></details>`:''}</div>`).join(''):'<p class="muted">Belum ada histori.</p>'}</div></div>`,'<button class="btn outline" id="modal-done">Tutup</button>');$('#modal-done').onclick=closeModal;
}
async function correctionForm(id){let t=state.transactions.find(x=>x.id===id);if(!t)return;
 modal('Ajukan Koreksi',`<div class="notice">Data resmi tidak berubah selama koreksi menunggu persetujuan admin.</div><div class="hint mt"><b>Data saat ini</b><p class="tiny">${h(t.transaction_date||'—')} · ${rp(t.amount_cents)} · ${h(t.category_name||'—')}</p><p>${h(t.description||'—')}</p><p class="tiny">Vendor: ${h(t.vendor||'—')} · Invoice: ${h(t.invoice_number||'—')}</p></div><form id="correction-form" class="mt"><div class="field"><label>Alasan koreksi*</label><textarea name="reason" required minlength="5" placeholder="Jelaskan alasan perubahan"></textarea></div><div class="grid2 mt">${field('Nominal baru (kosong = tidak diubah)','amount','','number',false,'min="0" step="0.01"')}${field('Keterangan baru','description','')}${field('Tanggal baru','transaction_date','','date')}${selectF('Kategori baru','category_id',state.config.categories,null)}${field('Vendor baru','vendor','')}${field('Metode pembayaran baru','payment_method','')}${field('Nomor invoice baru','invoice_number','')}${field('Catatan baru','notes','')}</div><div class="field mt"><label>File kuitansi pengganti (opsional)</label><input type="file" name="replacement" accept=".pdf,.png,.jpg,.jpeg,.webp"></div><button type="submit" class="btn primary mt">Kirim Permintaan Koreksi</button></form>`);
 $('#correction-form').onsubmit=async e=>{e.preventDefault();let form=e.currentTarget;let f=new FormData(form),p={};for(let key of ['amount','description','transaction_date','category_id','vendor','payment_method','invoice_number','notes'])if(f.get(key)!=='')p[key]=f.get(key);let file=form.elements.replacement.files[0];if(file&&(!file.size||file.size>8*1024*1024))return toast('Lampiran harus terisi dan maksimal 8 MB.',true);if(file && !Object.keys(p).length)p.notes=t.notes||'';
 if(!Object.keys(p).length)return toast('Isi data yang dikoreksi atau pilih kuitansi pengganti',true);
 const btn=form.querySelector('button[type=submit]');if(btn.disabled)return;btn.disabled=true;
 let requestId=null;
 try{let r=await post('/transactions/'+id+'/corrections',{reason:f.get('reason'),proposed:p});requestId=r.id;if(file){let fd=new FormData();fd.append('file',file);await json('/corrections/'+r.id+'/replacement',{method:'POST',body:fd})}toast('Permintaan koreksi dikirim dan menunggu admin');if(form.isConnected)closeModal();if(state.page==='transactions')await nav('transactions')}catch(ex){if(requestId){toast('Permintaan koreksi sudah dibuat, tetapi lampiran belum terkonfirmasi. Periksa bersama admin sebelum keputusan.',true);if(form.isConnected)closeModal();if(state.page==='transactions')await nav('transactions')}else{toast(ex.message,true);btn.disabled=false}}};
}
let financialBusy=false;
async function financialAction(id,reverse){
  if(financialBusy)return;
  const page=state.page,rows=await loadTx();if(page!==state.page)return;
  const t=rows.find(x=>x.id===id);
  if(!t||t.status!==(reverse?'APPROVED':'REVERSED'))return toast('Status berubah. Muat ulang daftar.',true);
  if(reverse&&state.me?.role!=='admin')return toast('Hanya admin dapat membatalkan.',true);
  if(!reverse&&t.reinstatement_pending)return toast('Permintaan pemulihan sudah pending.',true);
  const impact=reverse?'Pengeluaran keluar dari laporan terbaru. Kuitansi dan histori tetap tersimpan; koreksi pending ditutup.':'Pengeluaran tetap tidak dihitung sampai permintaan pemulihan disetujui.';
  modal(reverse?'Batalkan Persetujuan':'Ajukan Pemulihan',`<div class="hint"><b>${h(t.description||'Transaksi')}</b><p>${rp(t.amount_cents)} · ${h(t.transaction_date||'—')} · ${pill(t.status)}</p><a target="_blank" rel="noopener" href="/api/receipts/${h(t.document_id)}">Periksa kuitansi ↗</a></div><p class="notice mt">${impact}</p><form id="financial-form" class="mt"><div class="field"><label>Alasan (minimal 5 karakter)*</label><textarea name="reason" minlength="5" required></textarea></div><label class="checkrow mt"><input type="checkbox" name="confirmed" required> Saya memahami dampaknya terhadap laporan.</label><button type="submit" class="btn ${reverse?'danger':'primary'} mt">${reverse?'Batalkan Persetujuan':'Ajukan Pemulihan'}</button><p id="financial-status" role="status" class="tiny muted"></p></form>`,'<button id="modal-done" class="btn outline">Tutup</button>');
  $('#modal-done').onclick=closeModal;
  const form=$('#financial-form');
  form.onsubmit=async e=>{
    e.preventDefault();if(financialBusy)return;
    const fd=new FormData(form),reason=String(fd.get('reason')||'').trim();
    if(reason.length<5||!fd.get('confirmed'))return toast('Lengkapi alasan dan konfirmasi.',true);
    const btn=form.querySelector('button[type=submit]'),status=form.querySelector('#financial-status');
    financialBusy=true;btn.disabled=true;status.textContent='Memproses…';
    let saved=false;
    try{
      const r=await post(reverse?'/admin/transactions/'+id+'/reverse':'/transactions/'+id+'/reinstatement',{reason});
      saved=true;toast(reverse?'Persetujuan dibatalkan dan dicatat.':'Pemulihan diajukan · SLA '+r.sla_status);
      if(form.isConnected)closeModal();if(state.page===page)await nav(page);
    }catch(err){status.textContent=err.message;toast(err.message,true)}
    finally{financialBusy=false;if(!saved)btn.disabled=false}
  };
}
async function actionReverse(id){await financialAction(id,true)}
async function actionReinstate(id){await financialAction(id,false)}
async function actionDelete(id){if(!confirm('Soft-delete draft? Admin dapat memulihkannya dalam 30 hari.'))return;try{await json('/transactions/'+id+'/draft',{method:'DELETE'});toast('Draft soft-deleted');await nav('upload')}catch(e){toast(e.message,true)}}
// Phase 3.5: contextual review; existing backend is the authority.
let reviewSubmitting=false;
function reviewRisks(raw){
  try{const v=JSON.parse(raw||'[]');return Array.isArray(v)?v.map(String):[]}catch{return ['Alasan risiko tidak dapat ditampilkan; periksa detail transaksi.']}
}
function reviewProposal(raw){
  try{
    const p=JSON.parse(raw||'{}');
    if(!p||typeof p!=='object'||Array.isArray(p))throw Error();
    const labels={transaction_date:'Tanggal',amount_cents:'Nominal',description:'Keterangan',category_id:'Kategori',activity_id:'Aktivitas',vendor:'Vendor',payment_method:'Metode pembayaran',invoice_number:'Nomor invoice',notes:'Catatan'};
    return Object.entries(p).map(([k,v])=>{
      let shown=v;
      if(k==='amount_cents')shown=rp(v);
      if(k==='category_id')shown=state.config.categories.find(c=>c.id===v)?.name||v;
      if(k==='activity_id')shown=state.config.activities.find(c=>c.id===v)?.name||v;
      return '<div class="tiny"><b>'+h(labels[k]||k)+':</b> '+h(shown??'—')+'</div>';
    }).join('')||'<p class="tiny muted">Tidak ada perubahan kolom.</p>';
  }catch{return '<p class="tiny muted">Usulan tidak dapat ditampilkan. Periksa detail sebelum mengambil keputusan.</p>'}
}
function reviewRecord(kind,id){
  const rows=kind==='transaction'?state.queue?.transactions:kind==='correction'?state.queue?.corrections:kind==='reinstatement'?state.queue?.reinstatements:null;
  return rows?.find(x=>x.id===id);
}
function assignedReview(r){return !!r.assigned_reviewer_id&&r.assigned_reviewer_id===state.me?.id}
async function reviewsPage(){
  setHead('Review Queue','Periksa bukti dan alasan sebelum mengambil keputusan');
  const q=await json('/admin/review-queue');
  if(state.page!=='reviews')return;
  state.queue=q;
  const row=(title,sub,type,r,extra='')=>{
    const assigned=type!=='reinstatement'||assignedReview(r);
    return `<div class="review-card"><div><strong>${h(title)}</strong><small>${h(sub)}</small>${extra}
    ${!assigned?'<small class="muted">Keputusan hanya oleh admin yang ditugaskan.</small>':''}</div>
    <div class="inline-actions">
      <button class="btn outline" data-review-context="${h(type+':'+r.id)}">Periksa</button>
      <button class="btn primary" data-review="${h(type+':'+r.id+':APPROVE')}" ${assigned?'':'disabled'}>Approve</button>
      <button class="btn danger" data-review="${h(type+':'+r.id+':REJECT')}" ${assigned?'':'disabled'}>Reject</button>
      ${type==='reinstatement'?`<button class="btn outline" data-escalate="${h(r.id)}">Eskalasi</button>${r.sla_status==='PROVISIONAL'&&!r.snoozed_at?`<button class="btn soft" data-snooze="${h(r.id)}">Snooze</button>`:''}`:''}
    </div></div>`;
  };
  $('#page-content').innerHTML=`<div class="kpis">
  <div class="kpi"><small>Pending Transaction</small><strong>${q.transactions.length}</strong></div>
  <div class="kpi"><small>Correction Requests</small><strong>${q.corrections.length}</strong></div>
  <div class="kpi orange"><small>Reinstatement</small><strong>${q.reinstatements.length}</strong></div></div>
  <div class="notice mt">Pengeluaran baru masuk laporan setelah APPROVED. Keputusan tetap dicatat satu per satu; tidak ada approval massal otomatis.</div>
  <section class="panel mt"><div class="panelhead"><div><h3>Transaksi menunggu review</h3><small>Manual approval</small></div></div>
  ${q.transactions.map(t=>row(t.description||'Tanpa keterangan',reviewRisks(t.risk_reasons).join(' • ')||'Perlu review','transaction',t,`<small>Nominal: ${rp(t.amount_cents)} | Uploader: ${h(t.uploader_name)}</small><small>Tanggal: ${h(t.transaction_date||'—')}</small><a target="_blank" rel="noopener" href="/api/receipts/${h(t.document_id)}">Lihat kuitansi ↗</a>`)).join('')||'<div class="empty">Tidak ada transaksi yang perlu review.</div>'}</section>
  <section class="panel mt"><div class="panelhead"><h3>Permintaan Koreksi</h3></div>
  ${q.corrections.map(r=>row(r.description||'Transaksi',r.reason,'correction',r,reviewProposal(r.proposed_json))).join('')||'<div class="empty">Tidak ada koreksi pending.</div>'}</section>
  <section class="panel mt"><div class="panelhead"><h3>Permintaan Reinstatement</h3></div>
  ${q.reinstatements.map(r=>row(r.description||'Transaksi',`Status SLA: ${r.sla_status}; penugasan: ${r.assignment_stage}; due: ${r.due_at||r.provisional_due_at||'—'}`,'reinstatement',r,`<small>Alasan: ${h(r.reason)}</small>`)).join('')||'<div class="empty">Tidak ada reinstatement pending.</div>'}</section>`;
}
async function reviewAction(spec){
  if(reviewSubmitting)return toast('Keputusan sedang diproses.',true);
  const [kind,id,initial]=spec.split(':');
  const r=reviewRecord(kind,id);
  if(!r)return toast('Item tidak tersedia; buka ulang Review Queue.',true);
  const txid=kind==='transaction'?id:r.transaction_id;
  let t=kind==='transaction'?r:null;
  if(!t){
    const rows=await loadTx();
    if(state.page!=='reviews')return;
    t=rows.find(x=>x.id===txid);
  }
  const allowed=kind!=='reinstatement'||assignedReview(r);
  const replacementExpected=kind==='correction'&&!!r.replacement_version_id;
  const replacementAvailable=replacementExpected&&t&&Number.isInteger(r.replacement_version_number)&&r.replacement_version_number>0;
  const replacementLink=replacementAvailable?`<p><a href="/api/receipts/${h(t.document_id)}?version=${r.replacement_version_number}" target="_blank" rel="noopener">Buka kuitansi pengganti (versi ${r.replacement_version_number}) ↗</a></p>`:replacementExpected?'<p class="notice">Versi kuitansi pengganti belum tersedia. Muat ulang Review Queue sebelum mengambil keputusan.</p>':'';
  const context=t?`<table class="small-table"><tr><td>Status saat ini</td><td>${pill(t.status)}</td></tr><tr><td>Keterangan</td><td>${h(t.description||'—')}</td></tr><tr><td>Tanggal</td><td>${h(t.transaction_date||'—')}</td></tr><tr><td>Nominal</td><td><b>${rp(t.amount_cents)}</b></td></tr><tr><td>Vendor</td><td>${h(t.vendor||'—')}</td></tr><tr><td>Kategori</td><td>${h(t.category_name||'—')}</td></tr><tr><td>Nama Kontrak</td><td>${h(t.contract_name||'—')}</td></tr><tr><td>Nomor Kontrak</td><td>${h(t.contract_number||'—')}</td></tr><tr><td>Uploader</td><td>${h(t.uploader_name||'—')}</td></tr></table><p><a href="/api/receipts/${h(t.document_id)}" target="_blank" rel="noopener">Buka kuitansi aktif ↗</a></p>`:'<p class="notice">Ringkasan transaksi tidak tersedia. Buka kembali antrean untuk memeriksa data.</p>';
  const evidence=kind==='transaction'?`<h4>Alasan review</h4><ul>${reviewRisks(r.risk_reasons).map(x=>'<li>'+h(x)+'</li>').join('')||'<li>Perlu pemeriksaan admin.</li>'}</ul>`:kind==='correction'?`<h4>Usulan koreksi</h4><p>${h(r.reason)}</p>${reviewProposal(r.proposed_json)}${replacementLink}<p class="tiny muted">Data resmi berubah hanya setelah keputusan disetujui.</p>`:`<h4>Permintaan pemulihan</h4><p>${h(r.reason)}</p><p class="tiny">SLA: ${h(r.sla_status)} · ${h(r.assignment_stage)}</p>`;
  const canDecide=allowed&&!!t&&(!replacementExpected||replacementAvailable);
  modal('Periksa & Putuskan',`${context}${evidence}${canDecide?`<form id="review-decision-form" class="mt">
    <div class="field"><label>Keputusan*</label><select name="decision" required><option value="">Pilih keputusan...</option><option value="APPROVE" ${initial==='APPROVE'?'selected':''}>Approve</option><option value="REJECT" ${initial==='REJECT'?'selected':''}>Reject</option></select></div>
    <div class="field mt"><label>Alasan keputusan*</label><textarea name="reason" required placeholder="Tuliskan alasan berdasarkan pemeriksaan bukti"></textarea></div>
    <label class="checkrow mt"><input type="checkbox" name="confirmed" required> Saya telah memeriksa data dan bukti yang relevan.</label>
    <p class="tiny muted">Keputusan akan dicatat pada audit trail.</p>
    <button type="submit" class="btn primary mt">Simpan Keputusan</button>
    <p id="review-decision-status" role="status" class="tiny muted mt"></p>
  </form>`:'<p class="notice">Keputusan tidak tersedia dari tampilan ini.</p>'}`,'<button class="btn outline" id="modal-done">Tutup</button>');
  $('#modal-done').onclick=closeModal;
  const form=$('#review-decision-form');if(!form)return;
  form.onsubmit=async e=>{
    e.preventDefault();if(reviewSubmitting)return;
    const f=new FormData(form),decision=String(f.get('decision')),reason=String(f.get('reason')||'').trim();
    if(!reason||!['APPROVE','REJECT'].includes(decision)||!f.get('confirmed'))return toast('Lengkapi keputusan, alasan, dan konfirmasi pemeriksaan.',true);
    const route=kind==='transaction'?'/admin/transactions/'+id+'/decision':kind==='correction'?'/admin/corrections/'+id+'/decision':'/admin/reinstatements/'+id+'/decision';
    const button=form.querySelector('button[type=submit]'),status=form.querySelector('#review-decision-status');
    reviewSubmitting=true;button.disabled=true;status.textContent='Menyimpan keputusan…';
    let saved=false;
    try{
      const payload={decision,reason};
      if(kind==='transaction'&&Number.isInteger(r.revision))payload.revision=r.revision;
      await post(route,payload);saved=true;
      toast('Keputusan tersimpan dengan audit trail.');
      if(form.isConnected)closeModal();
      if(state.page==='reviews')await nav('reviews');
    }catch(err){status.textContent=err.message;toast(err.message,true)}
    finally{reviewSubmitting=false;if(!saved)button.disabled=false}
  };
}
async function reportsPage(){
 if(state.me.role==='admin' && (await json('/health')).mode==='DEMO LOCAL'){
   if(state.page!=='reports')return;
   setHead('Reports & Excel','Rekap keuangan berdasarkan periode pilihan');
   const params='year='+financeYear+(financeMonth?'&month='+financeMonth:'');
   const d=await json('/finance/summary?'+params);
   if(state.page!=='reports')return;
   $('#page-content').innerHTML=`<div class="dash-toolbar"><div><h2>Rekap Keuangan MHS</h2><p>Periode yang sama dengan dashboard</p></div><div class="dash-toolbar-actions"><label class="finance-filter">Tahun <select id="report-year">${yearOptions(d)}</select></label><label class="finance-filter">Bulan <select id="report-month" ${financeYear===0?'disabled':''}><option value="0">Semua</option>${['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'].map((m,i)=>`<option value="${i+1}" ${financeMonth===i+1?'selected':''}>${m}</option>`).join('')}</select></label></div></div>
   <div class="dash-kpi-grid">${[['Pemasukan',d.income_cents],['Pengeluaran',d.total_cents],['Selisih tercatat',d.net_cents]].map(([label,v])=>`<div class="dash-card"><div class="dash-card-title">${label}</div><div class="dash-val">${rp(v)}</div></div>`).join('')}</div>
   <section class="panel panelpad mt owner-report-card"><div class="owner-report-intro"><div class="owner-file-icon" aria-hidden="true">XLSX</div><div><h3>Unduh laporan periode</h3><p class="muted">Ringkasan, Semua Transaksi, Pemasukan, Pengeluaran, dan Report Info.</p><p class="tiny muted">${h(d.receipt_count)} pengeluaran disetujui · ${h(d.income_count)} pemasukan aktif</p></div></div><button class="btn primary" id="finance-export">↓ Unduh Excel (.xlsx)</button><p class="tiny muted">Snapshot tidak berubah setelah koreksi. Tautan kuitansi memerlukan login aktif pada server lokal. Bukan laporan pajak resmi.</p>${d.legacy_income_cents?`<div class="notice">Nilai lama tanpa tanggal ${rp(d.legacy_income_cents)} tidak dihitung.</div>`:''}</section>
   <details class="panel panelpad mt"><summary>Format Excel lama (opsional)</summary><p class="muted">Format kompatibilitas lama, seluruh periode atau aktivitas terpilih; tidak memuat pemasukan.</p><div class="field"><label>Aktivitas</label><select id="report-activity">${opts(state.config.activities,null,'Semua aktivitas')}</select></div><button class="btn outline mt" id="export-xlsx">Download format lama</button></details>`;
   $('#report-year').onchange=e=>financePeriodChange(e,'reports');
   $('#report-month').onchange=e=>{financeMonth=Number(e.target.value);nav('reports')};
   $('#finance-export').onclick=async()=>{const btn=$('#finance-export');btn.disabled=true;try{const res=await api('/finance/export?'+params);const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='MHS_Rekap_Keuangan_'+(financeYear||'Semua_Tahun')+(financeMonth?'-'+String(financeMonth).padStart(2,'0'):'')+'.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);toast('Laporan Excel berhasil dibuat')}catch(e){toast(e.message,true)}finally{btn.disabled=false}};
   $('#export-xlsx').onclick=()=>{const a=$('#report-activity').value;window.location.href='/api/reports/export'+(a?'?activity_id='+encodeURIComponent(a):'')};
   return;
 }
 setHead('Reports & Excel','Ekspor snapshot XLSX dengan data APPROVED saja');const [d,rows]=await Promise.all([json('/dashboard'),loadTx()]);$('#page-content').innerHTML=`<div class="grid2"><section class="panel panelpad"><h3>Ringkasan Pengeluaran</h3><div class="kpi" style="box-shadow:none;margin:15px 0"><small>APPROVED TOTAL</small><strong>${rp(d.total_cents)}</strong><span class="muted tiny">${d.receipt_count} kuitansi disetujui</span></div><div class="field"><label>Filter aktivitas</label><select id="report-activity">${opts(state.config.activities,null,'Semua aktivitas')}</select></div><button class="btn primary mt" id="export-xlsx">⬇ Download Excel (.xlsx)</button><p class="muted tiny">Berisi Transactions, Summary, dan Report Info. Histori ekspor tidak berubah setelah transaksi dikoreksi atau dibatalkan.</p></section><section class="panel panelpad"><h3>Kontrol Pelaporan</h3><div class="notice mt">Transaksi REVERSED, REJECTED, draft, dan PENDING_REVIEW tidak masuk total. Koreksi pending juga tidak mengubah nilai resmi.</div><p class="muted mt">Tautan kuitansi di Excel memerlukan login aktif sesuai hak akses pengguna.</p></section></div><section class="panel mt"><div class="panelhead"><h3>Data yang akan diekspor</h3></div>${txTable(rows.filter(t=>t.status==='APPROVED'),false)}</section>`;
 $('#export-xlsx').onclick=()=>{let a=$('#report-activity').value;window.location.href='/api/reports/export'+(a?'?activity_id='+encodeURIComponent(a):'')};
}
async function calendarPage(){setHead('Calendar & SLA','Hari kerja, verifikasi manual kalender, dan provisional SLA');let c=await json('/admin/calendar');if(state.page!=='calendar')return;let a=c.active;
 $('#page-content').innerHTML=`<button class="btn outline" data-nav="management">← Kembali ke Management</button><div class="grid2 mt"><section class="panel panelpad"><h3>Status Kalender</h3><p>Versi kalender: <b>${a.version}</b></p><p>Zona waktu: <b>${h(a.timezone)}</b></p><p>Verifikasi: ${pill(a.verified?'FINAL':'PROVISIONAL')}</p><div class="notice mt">Default hari kerja Senin–Jumat 09.00–17.00 WIB. Kalender awal tidak terverifikasi; eskalasi otomatis diblokir. Sumber hari libur resmi perlu diverifikasi admin secara manual pada V0.1.</div></section><section class="panel panelpad"><h3>Stage Hari Libur (Manual)</h3><p class="muted tiny">Masukkan satu tanggal YYYY-MM-DD per baris. Verifikasi terhadap SKB pemerintah secara mandiri sebelum publish.</p><form id="holiday-form"><div class="field"><label>Sumber resmi / referensi SKB</label><input name="source" required placeholder="Contoh: SKB Pemerintah Indonesia ..."></div><div class="field mt"><label>Daftar hari libur</label><textarea name="holidays" placeholder="2026-12-25\n2027-01-01"></textarea></div><button class="btn primary mt">Stage Kalender</button></form></section></div><section class="panel mt"><div class="panelhead"><h3>Pending Calendar Imports</h3></div>${c.imports.length?c.imports.map(i=>`<div class="review-card"><div><strong>${h(i.source)}</strong><small>${h(i.status)} · ${h(i.year_start)}–${h(i.year_end)} · ${h(i.entries_json)}</small></div>${i.status==='STAGED'?`<button class="btn primary" data-publish="${i.id}">Verifikasi & Publish</button>`:pill(i.status)}</div>`).join(''):'<div class="empty">Belum ada impor kalender.</div>'}</section>`;
 $('#holiday-form').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.currentTarget);try{await post('/admin/calendar/stage',{source:fd.get('source'),holidays:fd.get('holidays').split(/[\n,]+/).map(x=>x.trim()).filter(Boolean)});toast('Data kalender di-stage. Pastikan semua hari libur resmi benar.');await nav('calendar')}catch(ex){toast(ex.message,true)}};
}
let masterBusy=false;
async function managementPage(){
 setHead('Management','Kelola aktivitas dan kategori pengeluaran');
 const cfg=await json('/config');if(state.page!=='management')return;state.config=cfg;
 const a=cfg.activities,c=cfg.categories;
 $('#page-content').innerHTML=`<div class="grid2"><section class="panel panelpad"><h3>Aktivitas (${a.length})</h3><p class="tiny muted">Periode ditutup tetap menerima kuitansi dengan alasan keterlambatan dan review.</p><div class="field"><input id="activity-query" aria-label="Cari aktivitas" placeholder="Cari aktivitas..."></div><div id="activity-list" class="mt"></div><form id="act-form" class="mt"><div class="field"><label>Aktivitas baru</label><input name="name" minlength="3" maxlength="100" required></div><button class="btn primary mt">Tambah Aktivitas</button></form></section><section class="panel panelpad"><h3>Kategori (${c.length})</h3><div class="field mt"><input id="category-query" aria-label="Cari kategori" placeholder="Cari kategori..."></div><div id="category-list" class="mt"></div><form id="cat-form"><div class="field"><label>Kategori baru</label><input name="name" minlength="2" maxlength="80" required></div><button class="btn primary mt">Tambah Kategori</button></form></section></div><section class="panel panelpad mt"><h3>Pengaturan lanjutan</h3><p class="muted">Kalender hari kerja dan SLA pemulihan transaksi.</p><button class="btn outline" data-nav="calendar">Calendar &amp; SLA</button><div id="backup-panel" class="mt"></div><div id="storage-panel" class="mt"></div><div class="mt"><h3>Pembersihan draft</h3><p>Draft yang dihapus dapat dipulihkan selama 30 hari.</p><h3 class="mt">Draft terhapus</h3><button type="button" class="btn danger" id="empty-trash" hidden style="display:none">Kosongkan Draft Terhapus</button><div id="deleted-drafts" aria-live="polite"></div></div></section>`;
 const deleted=$('#deleted-drafts');
 async function refreshDeleted(){
   try{
     const rows=await json('/admin/drafts/deleted');
     deleted.innerHTML=rows.map(r=>`<div class="draft-item"><div class="details"><strong>${h(r.filename||r.description||r.id)}</strong><p>${h(r.uploader_name)} · Dapat dipulihkan hingga ${h(workflowTime(r.purge_at))} WIB</p></div><div class="inline-actions"><button class="btn outline" data-restore-draft="${h(r.id)}">Pulihkan</button>${r.can_purge?`<button class="btn danger" data-purge-draft="${h(r.id)}" data-name="${h(r.filename||r.id)}" data-deleted="${h(workflowTime(r.deleted_at))}">Hapus permanen</button>`:''}</div></div>`).join('')||'<p class="muted">Tidak ada draft yang dapat dipulihkan.</p>';
   }catch(err){deleted.textContent=err.message}
 }
 deleted.onclick=async event=>{
   const btn=event.target.closest('[data-restore-draft],[data-purge-draft]');
   if(!btn||btn.disabled)return;
   btn.disabled=true;
   try{
     if(btn.dataset.purgeDraft){
       if(!confirm('Hapus permanen '+btn.dataset.name+' (dihapus '+btn.dataset.deleted+' WIB, ID '+btn.dataset.purgeDraft+')? File ini tidak bisa dipulihkan dari aplikasi.')){
         btn.disabled=false;return;
       }
       const result=await json('/admin/drafts/'+encodeURIComponent(btn.dataset.purgeDraft)+'/permanent',{method:'DELETE'});
       toast(result.files_removed?'Draft dihapus permanen.':'Draft dihapus. Pembersihan file akan dicoba lagi saat aplikasi dibuka.');
       await refreshDeleted();
       document.querySelector('#storage-check')?.click();
       return;
     }
     await post('/admin/transactions/'+encodeURIComponent(btn.dataset.restoreDraft)+'/restore',{});
     toast('Draft dipulihkan. Buka All Transactions untuk melihatnya.');
     await refreshDeleted();
   }catch(err){toast(err.message,true);btn.disabled=false}
 };
 refreshDeleted();
 if((await json("/health")).mode==="DEMO LOCAL"&&state.page==="management"){
   const emptyTrash=$('#empty-trash');
   emptyTrash.hidden=false;emptyTrash.style.display='';
   emptyTrash.onclick=async()=>{
     emptyTrash.disabled=true;
     try{
       const preview=await json('/admin/drafts/empty-trash');
       if(!emptyTrash.isConnected)return;
       if(!preview.count)return toast('Draft terhapus sudah kosong.');
       if(!confirm('Hapus permanen seluruh '+preview.count+' draft terhapus beserta file kuitansinya dari penyimpanan lokal? Semua draft ini tidak dapat dipulihkan dari aplikasi.'))return;
       const result=await post('/admin/drafts/empty-trash',{token:preview.token});
       toast(result.count+' draft dihapus permanen.'+(result.pending?' Sebagian file akan dibersihkan saat aplikasi dibuka kembali.':''));
       document.querySelector('#storage-check')?.click();
     }catch(err){toast(err.message,true)}finally{emptyTrash.disabled=false;if(emptyTrash.isConnected)await refreshDeleted()}
   };
   await setupBackupPanel();
   if(state.page==="management")setupStoragePanel();
 }
 if(state.page!=="management")return;
 const search=(items,q)=>items.filter(x=>x.name.toLowerCase().includes(q.trim().toLowerCase()));
 const renderA=()=>{$('#activity-list').innerHTML=search(a,$('#activity-query').value).map(x=>`<div class="hint mb"><b>${h(x.name)}</b><p class="tiny">${h(x.status)} · ${pill(x.closure_status)}</p><button class="btn outline" data-activity="${h(x.id+':'+(x.closure_status==='OPEN'?'CLOSED':'OPEN'))}">${x.closure_status==='OPEN'?'Tutup periode':'Buka periode'}</button></div>`).join('')||'<p class="muted">Tidak ada aktivitas.</p>'};
 const renderC=()=>{$('#category-list').innerHTML=search(c,$('#category-query').value).map(x=>`<div class="hint mb">${h(x.name)}</div>`).join('')||'<p class="muted">Tidak ada kategori.</p>'};
 $('#activity-query').oninput=renderA;$('#category-query').oninput=renderC;renderA();renderC();
 for(const [id,route,min,items] of [['act-form','/admin/activities',3,a],['cat-form','/admin/categories',2,c]])$('#'+id).onsubmit=async e=>{
   e.preventDefault();if(masterBusy)return;
   const form=e.currentTarget,name=String(new FormData(form).get('name')||'').trim();
   if(name.length<min)return toast('Nama terlalu pendek.',true);
   if(items.some(x=>x.name.trim().toLowerCase()===name.toLowerCase()))return toast('Nama sudah tersedia.',true);
   const btn=form.querySelector('button');masterBusy=true;btn.disabled=true;
   try{await post(route,{name});toast('Data dibuat');if(state.page==='management')await nav('management')}catch(err){toast(err.message,true)}finally{masterBusy=false;btn.disabled=false}
 };
}
async function setupBackupPanel(){
 const panel=$('#backup-panel');if(!panel)return;
 panel.innerHTML='<h3>Backup &amp; Pemulihan</h3><p class="tiny muted">Memeriksa cadangan...</p>';
 try{
  const b=await json('/admin/backup/status');if(!panel.isConnected||state.page!=='management')return;
  panel.innerHTML=`<h3>Backup &amp; Pemulihan</h3><p>Backup otomatis: <b>${b.automatic?'Aktif':'Nonaktif'}</b> · ${b.count} cadangan harian</p><p class="tiny muted">${b.state==='failed'?'Backup otomatis terakhir gagal; coba backup manual.':b.latest?'Cadangan terakhir: '+h(b.latest):'Belum ada cadangan harian.'}</p><p class="tiny muted">Simpan ZIP di media terpisah. Cadangan berisi data perusahaan dan informasi akun.</p><div class="inline-actions"><button class="btn primary" id="backup-download">Unduh Backup</button><button class="btn outline" id="backup-recover" ${b.latest?'':'disabled'}>Pulihkan Cadangan Terakhir</button><button class="btn outline" id="backup-refresh">Perbarui Status</button></div><p id="backup-status" class="tiny" role="status"></p>`;
  const download=panel.querySelector('#backup-download'),recover=panel.querySelector('#backup-recover'),status=panel.querySelector('#backup-status'),refresh=panel.querySelector('#backup-refresh');
  let busy=false;
  async function run(action){
   if(busy)return;busy=true;download.disabled=recover.disabled=refresh.disabled=true;
   status.textContent='Memproses. Jangan tutup aplikasi.';
   try{await action()}catch(err){status.textContent=err.message;toast(err.message,true)}
   finally{busy=false;download.disabled=refresh.disabled=false;recover.disabled=!b.latest}
  }
  download.onclick=()=>run(async()=>{
   const res=await api('/admin/backup/download',{method:'POST',body:JSON.stringify({})});
   const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
   a.href=url;a.download='MHS_Backup_'+new Date().toISOString().replace(/[:.]/g,'-')+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);
   status.textContent='Backup berhasil dibuat. Periksa folder unduhan.';
  });
  recover.onclick=()=>{
   if(!confirm('Buat salinan pemulihan dari backup terakhir? Database aktif tidak akan diganti.'))return;
   return run(async()=>{const r=await post('/admin/backup/recover-latest',{});status.textContent='Salinan pemulihan tersedia di storage/'+r.folder+'. Data aktif tetap utuh. Hubungi pengelola untuk mengaktifkan salinan.'});
  };
  refresh.onclick=()=>setupBackupPanel();
 }catch(err){panel.innerHTML='<p class="notice">'+h(err.message)+'</p>'}
}
function storageSize(bytes){
 const n=Number(bytes);
 if(!Number.isFinite(n)||n<0)return '—';
 if(n<1024)return n+' B';
 const unit=n>=1024**3?'GiB':n>=1024**2?'MiB':'KiB';
 const divisor=unit==='GiB'?1024**3:unit==='MiB'?1024**2:1024;
 return new Intl.NumberFormat('id-ID',{maximumFractionDigits:1}).format(n/divisor)+' '+unit;
}
function storageIssues(d){
 const issues=[];
 const fields=[['missing_receipt_versions','versi kuitansi tidak ditemukan'],['receipt_size_mismatches','versi kuitansi berbeda ukuran'],['missing_exports','arsip Excel tidak ditemukan'],['duplicate_hash_groups','kelompok kuitansi identik (periksa kemungkinan pencatatan ganda)'],['unlinked_receipt_files','file kuitansi tanpa referensi'],['unlinked_export_files','file Excel tanpa referensi'],['temporary_upload_files','file upload sementara tertinggal'],['scan_warnings','kendala saat pemeriksaan']];
 for(const [key,label] of fields)if(Number(d[key])>0)issues.push(Number(d[key])+' '+label);
 if(Number(d.disk_free_bytes)<2*1024**3)issues.push('Sisa ruang disk kurang dari 2 GiB; kosongkan ruang di luar folder data MHS.');
 return issues;
}

function storageChartModel(d){
 const bytes=v=>{const n=Number(v);return Number.isFinite(n)&&n>=0?n:0};
 const rows=[['Dokumen kuitansi',bytes(d.receipt_bytes),'#f4831e'],['Database',bytes(d.database_bytes),'#4775b5'],['Arsip Excel',bytes(d.export_bytes),'#0d9488'],['Backup harian',bytes(d.daily_backup_bytes),'#8b70b3']];
 const total=rows.reduce((sum,r)=>sum+r[1],0);
 const free=bytes(d.disk_free_bytes),capacity=bytes(d.disk_total_bytes);
 const used=capacity?Math.min(100,Math.max(0,(1-free/capacity)*100)):null;
 return {rows:rows.map(([name,size,color])=>({name,size,color,pct:total?size/total*100:0})),total,free,capacity,used};
}
function renderStorageOverview(d){
 const m=storageChartModel(d),issues=storageIssues(d);
 const percent=n=>new Intl.NumberFormat('id-ID',{maximumFractionDigits:1}).format(n)+'%';
 const low=m.free<2*1024**3, diskColor=low?'#c07817':'#16845b';
 const segment=m.rows.map(r=>'<span style="width:'+r.pct+'%;background:'+r.color+';" title="'+h(r.name+' — '+storageSize(r.size))+'"></span>').join('');
 const legend=m.rows.map(r=>'<div class="storage-legend-row"><i style="background:'+r.color+'"></i><span>'+h(r.name)+'</span><b>'+h(storageSize(r.size))+'</b><span class="storage-pct">'+h(percent(r.pct))+'</span></div>').join('');
 return `<div class="storage-overview">
 <div class="storage-kpis">
 <div class="storage-kpi" style="--storage-accent:#f4831e"><small>Ukuran data utama</small><strong>${h(storageSize(m.total))}</strong><span>Data dan cadangan harian</span></div>
 <div class="storage-kpi" style="--storage-accent:${diskColor}"><small>Sisa ruang disk</small><strong style="color:${diskColor}">${h(storageSize(m.free))}</strong><span>${low?'Kapasitas mulai terbatas':'Ruang tersedia'}</span></div>
 <div class="storage-kpi" style="--storage-accent:#4775b5"><small>Versi kuitansi</small><strong>${h(d.receipt_versions)}</strong><span>${h(d.daily_backup_count)} cadangan harian</span></div>
 </div>
 <div class="storage-chart"><h4>Komposisi penyimpanan</h4><p>Proporsi ukuran data utama aplikasi</p><div class="storage-stack" aria-hidden="true">${segment}</div><div class="storage-legend">${legend}</div></div>
 <div class="storage-chart"><h4>Kapasitas disk perangkat</h4><p>Total penggunaan disk, termasuk file di luar MHS.</p>
 ${m.used===null?'<p>Kapasitas total tidak tersedia.</p>':`<div class="storage-disk-meta"><b>${h(percent(m.used))} terpakai</b><span>Total ${h(storageSize(m.capacity))}</span></div><div class="storage-meter" aria-hidden="true"><span style="width:${m.used}%;background:${diskColor}"></span></div><div class="storage-disk-meta"><span>Ruang tersedia</span><b>${h(storageSize(m.free))}</b></div>`}
 </div>
 ${issues.length?'<div class="notice"><b>Perlu perhatian</b><ul>'+issues.map(x=>'<li>'+h(x)+'</li>').join('')+'</ul><p>Hubungi pengelola jika ada dokumen hilang atau file tidak sesuai. Tidak ada file yang dihapus.</p></div>':'<div class="notice good-notice">Tidak ada masalah ukuran atau referensi yang terdeteksi.</div>'}
 <p class="tiny muted">Pemeriksaan metadata, bukan verifikasi isi setiap file. Ukuran tidak mencakup seluruh folder project atau salinan pemulihan terpisah.</p></div>`;
}

function setupStoragePanel(){
 const panel=$('#storage-panel');if(!panel)return;
 panel.innerHTML='<h3>Penyimpanan Data</h3><p class="tiny muted">Periksa ukuran database, kuitansi, laporan dan cadangan. Tidak menghapus file.</p><button class="btn outline" id="storage-check">Perbarui ringkasan</button><div id="storage-result" role="status" class="mt"></div>';
 const btn=panel.querySelector('#storage-check'),result=panel.querySelector('#storage-result');
 btn.onclick=async()=>{
   btn.disabled=true;result.textContent='Memeriksa penyimpanan…';
   try{
     const d=await json('/admin/storage/status');if(!panel.isConnected)return;
     result.innerHTML=renderStorageOverview(d);
   }catch(err){if(panel.isConnected)result.textContent=err.message}
   finally{btn.disabled=false}
 };
 btn.click();
}
function workflowTime(v){
  const d=new Date(v||'invalid');return Number.isNaN(d.getTime())?'—':d.toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'medium',timeZone:'Asia/Jakarta'});
}
function readableAudit(raw){try{return JSON.stringify(typeof raw==='string'?JSON.parse(raw):raw,null,2)||'—'}catch{return String(raw??'—')}}
const actionNames={TRANSACTION_SUBMITTED:'Transaksi diajukan',ADMIN_APPROVED:'Disetujui admin',ADMIN_REJECTED:'Ditolak admin',TRANSACTION_REVERSED:'Persetujuan dibatalkan',REINSTATEMENT_REQUESTED:'Pemulihan diajukan',REINSTATEMENT_APPROVE:'Pemulihan disetujui',REINSTATEMENT_REJECT:'Pemulihan ditolak',CORRECTION_APPROVED:'Koreksi disetujui',CORRECTION_REJECTED:'Koreksi ditolak',DOCUMENT_UPLOADED:'Kuitansi diunggah',DOCUMENT_OPENED:'Kuitansi dibuka'};
async function auditPage(){
 setHead('Audit Trail','Riwayat keputusan dan perubahan finansial');
 const logs=await json('/admin/audit');if(state.page!=='audit')return;
 $('#page-content').innerHTML=`<section class="panel panelpad"><div class="field"><label>Cari kejadian</label><input id="audit-query" placeholder="Aksi, pelaku, objek, detail..."></div><p class="tiny muted" id="audit-count"></p></section><section class="panel mt" id="audit-results"></section>`;
 const render=()=>{
   const q=$('#audit-query').value.trim().toLowerCase();
   const rows=logs.filter(x=>[x.action,actionNames[x.action],x.actor_name,x.target_type,x.target_id,readableAudit(x.details)].some(v=>String(v??'').toLowerCase().includes(q)));
   $('#audit-count').textContent=rows.length+' dari '+logs.length+' kejadian terbaru (maks. 200 dari API). Waktu WIB.';
   $('#audit-results').innerHTML=rows.length?`<div class="tablescroll"><table class="data-table"><thead><tr><th>WAKTU WIB</th><th>AKSI</th><th>OLEH</th><th>DETAIL</th></tr></thead><tbody>${rows.map(x=>`<tr><td class="nowrap">${h(workflowTime(x.created_at))}</td><td><b>${h(actionNames[x.action]||x.action)}</b><div class="tiny muted">${h(x.target_type)}</div></td><td>${h(x.actor_name||'SYSTEM')}</td><td><details><summary>Lihat detail</summary><div class="tiny" style="white-space:pre-wrap;overflow-wrap:anywhere">${h(readableAudit(x.details))}</div></details></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">Tidak ada kejadian yang sesuai.</div>';
 };
 $('#audit-query').oninput=render;render();
}
const noticeNames={REVIEW:'Pemeriksaan transaksi',DECISION:'Keputusan transaksi',CORRECTION:'Koreksi transaksi',REVERSAL:'Pembatalan persetujuan',REINSTATEMENT:'Pemulihan transaksi'};
async function notificationsPage(){
 setHead('Notifications','Informasi transaksi dan keputusan');
 const ns=await json('/notifications');if(state.page!=='notifications')return;
 $('#page-content').innerHTML=`<section class="panel"><div class="panelhead"><h3>Notifikasi terbaru</h3><small>${ns.length} pesan (maks. 100)</small></div>${ns.length?ns.map(n=>`<div class="review-card"><div><strong>${h(noticeNames[n.type]||n.type)}</strong><p>${h(n.message)}</p><small>${h(workflowTime(n.created_at))} WIB</small></div>${state.me.role==='admin'&&n.type==='REVIEW'?'<button class="btn outline" data-nav="reviews">Review Queue</button>':''}</div>`).join(''):'<div class="empty">Belum ada notifikasi.</div>'}</section>`;
}

// Centralized delegated click handlers also work after page rerenders.
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-nav],[data-edit],[data-detail],[data-correction],[data-reinstate],[data-reverse],[data-delete],[data-review],[data-review-context],[data-publish],[data-activity],[data-escalate],[data-snooze]');if(!el)return;
 try{
 if(el.dataset.nav)await nav(el.dataset.nav);
 else if(el.dataset.edit){if(uploadPending.has(el.dataset.edit))return toast('Draft sedang diproses OCR.',true);await editDraft(el.dataset.edit)}
 else if(el.dataset.detail)await details(el.dataset.detail);
 else if(el.dataset.correction)await correctionForm(el.dataset.correction);
 else if(el.dataset.reinstate)await actionReinstate(el.dataset.reinstate);
 else if(el.dataset.reverse)await actionReverse(el.dataset.reverse);
 else if(el.dataset.delete){if(uploadPending.has(el.dataset.delete))return toast('Tunggu OCR selesai sebelum menghapus draft.',true);await actionDelete(el.dataset.delete)}
 else if(el.dataset.review)await reviewAction(el.dataset.review);
 else if(el.dataset.reviewContext)await reviewAction(el.dataset.reviewContext);
 else if(el.dataset.publish){if(confirm('Sudah memverifikasi daftar hari libur ini dengan sumber pemerintah resmi?')){await post('/admin/calendar/'+el.dataset.publish+'/publish',{});toast('Kalender dipublikasikan; SLA provisional pending difinalkan');await nav('calendar')}}
 else if(el.dataset.activity){if(masterBusy)return;const [id,closure_status]=el.dataset.activity.split(':');if(!confirm(closure_status==='CLOSED'?'Tutup periode? Pengajuan berikutnya memerlukan alasan keterlambatan.':'Buka kembali periode?'))return;masterBusy=true;el.disabled=true;try{await patch('/admin/activities/'+id,{closure_status});toast('Periode diperbarui.');if(state.page==='management')await nav('management')}finally{masterBusy=false;el.disabled=false}}
 else if(el.dataset.escalate){let reason=prompt('Alasan eskalasi manual (minimal 5 karakter):');if(reason){await post('/admin/reinstatements/'+el.dataset.escalate+'/escalate',{reason});toast('Dikirim ke penugasan backup');await nav('reviews')}}
 else if(el.dataset.snooze){let reason=prompt('Alasan snooze reminder satu kali selama 24 jam kerja:');if(reason){await post('/admin/reinstatements/'+el.dataset.snooze+'/snooze',{reason});toast('Reminder ditunda tanpa mengubah SLA');await nav('reviews')}}
 }catch(err){toast(err.message,true)}
});
$('#dialog-close').onclick=closeModal;$('#dialog-overlay').addEventListener('click',e=>{if(e.target.id==='dialog-overlay')closeModal()});
function setMobileNav(open){
 $('#sidebar').classList.toggle('open',open);
 $('#mobile-mask').classList.toggle('hidden',!open);
 $('#mobile-toggle').setAttribute('aria-expanded',String(open));
}
$('#mobile-toggle').onclick=()=>setMobileNav(!$('#sidebar').classList.contains('open'));
$('#mobile-mask').onclick=()=>setMobileNav(false);
$('#logout').onclick=async()=>{try{await post('/auth/logout',{})}catch(e){}state.me=null;showLogin()};
for(let button of document.querySelectorAll('[data-demo]'))button.onclick=()=>{let accounts={admin:['admin@mhs.local','AdminDemo123!']};let [email,password]=accounts[button.dataset.demo];$('#login-form [name=email]').value=email;$('#login-form [name=password]').value=password};
if($('#login-form')) $('#login-form').onsubmit=async e=>{e.preventDefault();const email=$('#login-form [name=email]').value,password=$('#login-form [name=password]').value;try{let r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password}),credentials:'same-origin'});if(!r.ok)throw new Error('Email atau password salah');state.me=await json('/me');state.config=await json('/config');showApp();await nav('dashboard');toast('Berhasil masuk sebagai '+state.me.role)}catch(err){toast(err.message,true)}};
(async()=>{try{state.me=await json('/me');state.config=await json('/config');showApp();await nav('dashboard')}catch(e){showLogin()}
 if(new URLSearchParams(location.search).get('login')==='denied'){toast('Login ditolak atau sesi Google gagal. Gunakan akun owner yang terdaftar.',true);history.replaceState(null,'',location.pathname)}
})();
