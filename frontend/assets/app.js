// PT Mulia Hakimaco Sejahtera. Local V0.1: no fabricated OCR or fake financial results.
const $ = s => document.querySelector(s);
const h = (v='') => String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const rp = cents => new Intl.NumberFormat('id-ID',{style:'currency',currency:'IDR',maximumFractionDigits:0}).format((Number(cents)||0)/100);
const short = s => s ? new Date(s).toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short'}) : '—';
const state={me:null,config:null,page:'dashboard',transactions:[],queue:null,selected:new Set(),
  ocrResults:new Map(),ocrStatus:new Map()};
const navUploader=[['dashboard','◫','Ringkasan'],['upload','↥','Upload Receipt'],['transactions','▤','My Transactions'],['reports','▥','My Reports'],['notifications','♧','Notifications']];
const navAdmin=[['dashboard','◫','Dashboard'],['upload','⬆','Upload Receipt'],['reviews','☑','Review Queue'],['transactions','▤','All Transactions'],['reports','▥','Reports & Excel'],['calendar','◷','Calendar & SLA'],['management','⚙','Management'],['audit','☷','Audit Trail'],['notifications','♧','Notifications']];

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
function showLogin(){$('#login-screen').classList.remove('hidden');$('#app').classList.add('hidden')}
function showApp(){$('#login-screen').classList.add('hidden');$('#app').classList.remove('hidden');$('#role-chip').innerText=state.me.role.toUpperCase();$('#avatar').innerText=state.me.name[0].toUpperCase();$('#today').innerText=new Date().toLocaleDateString('id-ID',{weekday:'long',day:'numeric',month:'long',year:'numeric'});renderNav()}
function renderNav(){let items=state.me.role==='admin'?navAdmin:navUploader;$('#navigation').innerHTML=items.map(([id,icon,name])=>`<button class="navbutton ${id===state.page?'active':''}" data-nav="${id}"><span class="navicon">${icon}</span>${h(name)}</button>`).join('')}
function setHead(name,desc){$('#page-title').innerText=name;$('#page-desc').innerText=desc;$('#crumb-title').innerText=name}
const pill=s=>`<span class="pill ${h(s)}">${h(s?.replaceAll('_',' ')||'—')}</span>`;
function modal(title,body,foot=''){ $('#dialog-title').innerText=title;$('#dialog-body').innerHTML=body;$('#dialog-foot').innerHTML=foot;$('#dialog-overlay').classList.remove('hidden') }
function closeModal(){$('#dialog-overlay').classList.add('hidden')}
function field(label,name,value='',type='text',required=false,extra=''){return `<div class="field"><label for="d-${name}">${h(label)}</label><input id="d-${name}" name="${h(name)}" type="${type}" value="${h(value)}" ${required?'required':''} ${extra}></div>`}
function opts(values,selected=null,placeholder='Pilih...'){return `<option value="">${h(placeholder)}</option>`+values.map(v=>`<option value="${h(v.id)}" ${v.id===selected?'selected':''}>${h(v.name)}</option>`).join('')}
function selectF(label,name,values,selected,required=false){return `<div class="field"><label>${h(label)}</label><select name="${h(name)}" ${required?'required':''}>${opts(values,selected)}</select></div>`}
function txTable(rows,showActions=true){
 if(!rows.length)return '<div class="empty">Belum ada transaksi yang sesuai.</div>';
 return `<div class="tablescroll"><table class="data-table"><thead><tr><th>TANGGAL</th><th>KETERANGAN</th><th>AKTIVITAS</th><th>KATEGORI</th><th>NOMINAL</th><th>STATUS</th>${showActions?'<th>AKSI</th>':''}</tr></thead><tbody>${rows.map(t=>`<tr><td class="nowrap">${h(t.transaction_date||'—')}</td><td><strong class="clamp" title="${h(t.description||'Belum diisi')}">${h(t.description||'Belum diisi')}</strong><div class="tiny muted">${h(t.uploader_name||'')} ${t.correction_pending?'· Koreksi pending':''}</div></td><td>${h(t.activity_name||'')}</td><td>${h(t.category_name||'—')}</td><td class="nowrap"><strong>${rp(t.amount_cents)}</strong></td><td>${pill(t.status)}</td>${showActions?`<td><div class="inline-actions"><button class="btn outline" data-detail="${t.id}">Detail</button>${t.status==='DRAFT'?`<button class="btn soft" data-edit="${t.id}">Edit</button>`:''}${t.status==='APPROVED'?`<button class="btn outline" data-correction="${t.id}">Koreksi</button>`:''}${t.status==='REVERSED'?`<button class="btn soft" data-reinstate="${t.id}">Reinstatement</button>`:''}${state.me.role==='admin'&&t.status==='APPROVED'?`<button class="btn danger" data-reverse="${t.id}">Reverse</button>`:''}</div></td>`:''}</tr>`).join('')}</tbody></table></div>`;
}
async function nav(page){
 state.page=page;renderNav();$('#sidebar').classList.remove('open');$('#mobile-mask').classList.add('hidden');
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
 ${d.incomes.length?`<div class="tablescroll"><table class="data-table"><thead><tr><th>Tanggal</th><th>Keterangan</th><th>Pengirim</th><th>Nominal</th><th>Status</th><th>Aksi</th></tr></thead><tbody>${d.incomes.map(i=>`<tr><td>${h(i.transaction_date)}</td><td>${h(i.description)}</td><td>${h(i.sender||'—')}</td><td>${fmtRp(i.amount_cents)}</td><td>${pill(i.reversed_at?'REVERSED':'APPROVED')}</td><td>${i.reversed_at?h(i.reversal_reason):`<button class="btn danger" data-income-reverse="${h(i.id)}">Batalkan</button>`}</td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">Belum ada pemasukan pada periode ini.</div>'}</section>`:''}
 <section class="dash-card mt">
   <div class="chart-header" style="margin-bottom:10px">
     <div>
       <h3>Pengeluaran Terbaru</h3>
       <small>Aktivitas keuangan yang terakhir dicatat</small>
     </div>
     <button class="btn outline" style="border:none;color:#10b981;font-weight:700" data-nav="transactions">Lihat semua →</button>
   </div>
   ${rows.length?`<div class="tablescroll"><table class="data-table">
     <thead><tr><th>TANGGAL</th><th>KETERANGAN</th><th>VENDOR</th><th>JENIS</th><th>NOMINAL</th><th>STATUS</th></tr></thead>
     <tbody>${rows.slice(0,5).map(t=>`<tr>
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
   </table></div>`:'<div class="empty">Belum ada transaksi tercatat.</div>'}
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
     modal('Catat Pemasukan',`<form id="income-form" class="grid2">${field('Tanggal','transaction_date',today,'date',true)}${field('Nominal (rupiah, tanpa pemisah)','amount','','number',true,'min="1" max="999999999999" step="1"')}${field('Keterangan','description','','text',true,'maxlength="500"')}${field('Transfer dari / pengirim','sender','','text',false,'maxlength="200"')}<div><button class="btn primary" type="submit">Simpan Pemasukan</button></div></form><p class="tiny muted">Catat dana yang benar-benar diterima. Gunakan data simulasi saja.</p>`);
     $('#income-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget;const data=Object.fromEntries(new FormData(form));const amt=Number(data.amount);if(!Number.isSafeInteger(amt)||amt<=0||amt>999999999999)return toast('Nominal tidak valid',true);const btn=form.querySelector('button');btn.disabled=true;try{await post('/finance/income',{request_id:requestId,transaction_date:data.transaction_date,amount_cents:amt*100,description:data.description,sender:data.sender});closeModal();toast('Pemasukan tercatat');financeYear=0;financeMonth=0;await nav('dashboard')}catch(err){toast(err.message,true);btn.disabled=false}};
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
  if(window.MHSReceiptOCR)return Promise.resolve(window.MHSReceiptOCR);
  if(!ocrBundlePromise){
    ocrBundlePromise=new Promise((resolve,reject)=>{
      const script=document.createElement('script');
      script.src='/assets/ocr-engine.bundle.js';
      script.onload=()=>window.MHSReceiptOCR ? resolve(window.MHSReceiptOCR) : reject(new Error('Bundle OCR tidak menyiapkan mesin Tesseract.'));
      script.onerror=()=>reject(new Error('Bundle OCR belum dibangun. Jalankan npm.cmd exec -- esbuild .\\ocr-engine-entry.js --bundle --platform=browser --format=iife --outfile=.\\assets\\ocr-engine.bundle.js dari folder frontend.'));
      document.head.appendChild(script);
    }).catch(err=>{ocrBundlePromise=null;throw err});
  }
  return ocrBundlePromise;
}

function isImageOCRFile(file){return ['image/png','image/jpeg','image/webp'].includes(String(file?.type||'').toLowerCase())}

async function uploadPage(){
  setHead('Upload Receipt','Upload batch, baca kuitansi dengan Tesseract.js, periksa data, lalu submit sebagian');
  await loadTx();
  const acts=state.config.activities;
  const drafts=state.transactions.filter(t=>t.status==='DRAFT');
  $('#page-content').innerHTML=`
    <div class="two-panel">
      <section class="panel panelpad">
        <h3>01. Pilih Aktivitas &amp; Upload</h3>
        <p class="muted">Satu kuitansi menghasilkan satu transaksi. PDF, PNG, JPEG, atau WEBP — maksimal 8 MB.</p>
        <form id="batch-form">
          <div class="field mt"><label>Aktivitas*</label><select name="activity_id" required>${opts(acts,null,'Pilih aktivitas...')}</select></div>
          <div class="uploadbox"><strong>↥ Upload kuitansi</strong>
            <p class="muted tiny">Boleh pilih beberapa file sekaligus. Setiap kuitansi disimpan sebagai draft.</p>
            <input id="upload-files" name="files" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" multiple required>
          </div>
          <div class="mt row wrap"><button class="btn primary" id="batch-upload-button" type="submit">Upload &amp; Buat Draft →</button>
            <span class="tiny muted">Tesseract.js untuk gambar; PDF dan OCR gagal tetap bisa diisi manual.</span></div>
          <p id="ocr-upload-progress" role="status" aria-live="polite" class="tiny muted mt"></p>
        </form>
      </section>
      <section class="panel panelpad"><h3>02. Periksa Hasil</h3>
        <p class="muted">Kuitansi yang siap dapat disubmit tanpa menunggu kuitansi lain.</p>
        <div class="notice mt">Hasil OCR adalah saran, bukan data resmi. Periksa kuitansi asli dan pilih nominal/tanggal yang benar. Semua hasil OCR browser masih wajib melewati review admin pada mode demo.</div>
        <div class="mt"><strong>${drafts.length}</strong> draft aktif tersedia</div>
      </section>
    </div>
    <section class="panel mt"><div class="panelhead"><div><h3>03. Draft Batch Review</h3><small>Pilih draft lengkap untuk submit; dapat dilakukan sebagian.</small></div><button class="btn primary" id="submit-selected">Submit Terpilih →</button></div>
      <div class="panelpad draftgrid">
      ${drafts.length?drafts.map(t=>{
        const risks=(()=>{try{return JSON.parse(t.risk_reasons||'[]')}catch{return []}})();
        const ocr=state.ocrStatus.get(t.id);
        return `<div class="draft-item"><div class="details"><label class="checkrow"><input type="checkbox" class="select-draft" value="${h(t.id)}"><strong>${h(t.description||'Draft kuitansi')}</strong></label>
          <p>${h(t.activity_name)} • ${rp(t.amount_cents)} • ${h(t.transaction_date||'Tanggal belum diisi')}</p>
          <div>${pill(t.status)} ${risks.map(x=>`<span class="pill PENDING">${h(x)}</span>`).join('')}</div>
          ${ocr?`<p class="tiny muted">OCR: ${h(ocr)}</p>`:''}</div>
          <div class="inline-actions"><button class="btn soft" data-edit="${h(t.id)}">Periksa &amp; Edit</button><button class="btn danger" data-delete="${h(t.id)}">Hapus Draft</button></div></div>`;
      }).join(''):'<div class="empty">Belum ada draft. Unggah kuitansi terlebih dahulu.</div>'}
      </div>
    </section>`;

  const form=$('#batch-form');
  form.addEventListener('submit',async ev=>{
    ev.preventDefault();
    const activity_id=new FormData(form).get('activity_id');
    const files=[...$('#upload-files').files];
    if(!files.length)return toast('Pilih kuitansi terlebih dahulu',true);
    if(files.some(f=>f.size>8*1024*1024 || !f.size))return toast('Setiap file harus terisi dan berukuran maksimum 8 MB.',true);
    const btn=$('#batch-upload-button');
    const progress=message=>{const e=$('#ocr-upload-progress');if(e)e.textContent=message};
    btn.disabled=true;
    const successes=[],failures=[];
    try{
      progress(`Menyiapkan batch ${files.length} kuitansi...`);
      const batch=await post('/batches',{activity_id});
      for(const file of files){
        progress(`Mengunggah ${successes.length+failures.length+1}/${files.length}: ${file.name}`);
        try{
          const fd=new FormData();fd.append('file',file);
          const uploaded=await json('/batches/'+batch.id+'/documents',{method:'POST',body:fd});
          successes.push({file,id:uploaded.transaction_id});
        }catch(err){failures.push(`${file.name}: ${err.message}`)}
      }

      // A failed OCR never removes the original file or its saved draft.
      const images=successes.filter(({file})=>isImageOCRFile(file));
      let ocr=null;
      if(images.length){
        try{ocr=await loadBrowserOCR()}
        catch(err){for(const item of images)state.ocrStatus.set(item.id,`Belum diproses: ${err.message}`)}
      }
      if(ocr){
        try{
          let count=0;
          for(const {file,id} of images){
            count++;
            try{
              const result=await ocr.recognize(file,(status,pct)=>progress(`OCR ${count}/${images.length} — ${file.name}: ${status}${pct===null?'':' '+pct+'%'}`));
              state.ocrResults.set(id,result);
              state.ocrStatus.set(id,'Teks terbaca; belum diverifikasi — buka Periksa & Edit');
              try{
                await post('/transactions/'+id+'/ocr-result',{
                  text:result.text.slice(0,16000),confidence:result.confidence,
                  suggestions:result.suggestions
                });
              }catch(err){
                state.ocrStatus.set(id,'Teks terbaca; penyimpanan histori OCR belum berhasil — tetap bisa periksa manual');
                console.warn('Penyimpanan OCR gagal:',err.message);
              }
            }catch(err){state.ocrStatus.set(id,`OCR gagal: ${err.message}. Isi manual.`)}
          }
        }finally{
          try{await ocr.close()}catch(err){console.warn('Menutup OCR worker:',err)}
        }
      }
      for(const {file,id} of successes.filter(x=>!isImageOCRFile(x.file)))
        state.ocrStatus.set(id,`${file.name}: PDF belum didukung OCR browser; isi manual.`);
      await nav('upload');
      toast(`${successes.length} draft berhasil dibuat${failures.length?`; ${failures.length} gagal diunggah`:''}. Periksa & Edit sebelum submit.`,!!failures.length);
      if(failures.length)console.warn('Upload gagal:',failures);
    }catch(err){
      toast(`Upload gagal: ${err.message}`,true);
      await nav('upload');
    }finally{btn.disabled=false}
  });

  $('#submit-selected').addEventListener('click',async()=>{
    const ids=[...document.querySelectorAll('.select-draft:checked')].map(x=>x.value);
    if(!ids.length)return toast('Pilih minimal satu draft',true);
    try{
      const closed=ids.some(id=>{const t=state.transactions.find(t=>t.id===id);return state.config.activities.find(a=>a.id===t.activity_id)?.closure_status==='CLOSED'});
      const late_reason=closed?prompt('Aktivitas telah ditutup. Isi alasan keterlambatan (wajib):'):null;
      if(closed&&!late_reason)return;
      const result=await post('/transactions/submit-batch',{ids,late_reason});
      toast(`${result.items.length} transaksi berhasil disubmit`);
      await nav('upload');
    }catch(err){toast(err.message,true)}
  });
}

async function editDraft(id){
  const t=state.transactions.find(x=>x.id===id)||(await loadTx()).find(x=>x.id===id);
  if(!t)return toast('Draft tidak ditemukan',true);
  let result=state.ocrResults.get(id);
  if(!result){
    try{result=await json('/transactions/'+id+'/ocr-result');state.ocrResults.set(id,result)}
    catch(err){if(!err.message.includes('404'))console.info('Histori OCR belum tersedia:',err.message)}
  }
  const suggestions=result?.suggestions||{amounts:[],dates:[]};
  const candidates=(suggestions.amounts||[]).filter(x=>Number.isFinite(Number(x.value)));
  const dates=(suggestions.dates||[]).filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x));
  const moneyButtons=candidates.length?candidates.map(x=>
    `<button type="button" class="btn soft" data-ocr-amount="${h(x.value)}" title="${h(x.label||'')}" style="white-space:normal">Pakai ${rp(Math.round(Number(x.value)*100))}</button>`).join(' '):'<span class="muted tiny">Nominal tidak terdeteksi secara meyakinkan. Isi manual.</span>';
  const dateButtons=dates.length?dates.map(x=>`<button type="button" class="btn soft" data-ocr-date="${h(x)}">Pakai ${h(x)}</button>`).join(' '):'<span class="muted tiny">Tanggal tidak terdeteksi. Isi manual.</span>';
  const ocrPanel=result?`<div class="notice" style="grid-column:1/-1"><b>Hasil Tesseract.js — BELUM DIVERIFIKASI (tulisan tangan bisa tidak terbaca)</b><p class="tiny">Pilih angka/tanggal dari teks yang benar sesuai dokumen asli; OCR bisa salah membaca nominal, pajak, potongan, atau tanggal surat.</p>
      <p class="tiny"><b>Saran nominal</b></p><div class="row wrap" style="gap:6px">${moneyButtons}</div>
      <p class="tiny mt"><b>Saran tanggal</b></p><div class="row wrap" style="gap:6px">${dateButtons}</div>
      <details class="mt"><summary>Lihat teks mentah OCR (${result.confidence===null?'tanpa skor':Math.round(result.confidence)+'%'} skor mesin OCR (bukan akurasi terukur))</summary><pre style="white-space:pre-wrap;word-break:break-word;max-height:220px;overflow:auto">${h((result.text||'').slice(0,16000))}</pre></details>
    </div>`:`<div class="notice" style="grid-column:1/-1">Belum ada hasil OCR untuk draft ini. Periksa kuitansi asli dan isi secara manual (termasuk jika file PDF).</div>`;
  let existingRisks=[];try{existingRisks=JSON.parse(t.risk_reasons||'[]')}catch{}
  const mixed=existingRisks.some(x=>/beberapa kategori/i.test(x));
  const body=`<div class="notice">Semua hasil OCR merupakan saran. Data resmi belum berubah sampai kamu menyimpan draft dan mengikuti approval.</div>
    <div class="grid2 mt"><div><p><b>Kuitansi asli</b></p><iframe title="Kuitansi" src="/api/receipts/${h(t.document_id)}" style="width:100%;height:350px;border:1px solid #eee;border-radius:10px"></iframe><a class="document-link" href="/api/receipts/${h(t.document_id)}" target="_blank" rel="noopener">Lihat dokumen ukuran penuh ↗</a></div>
    <form id="draft-form" class="grid2" style="align-content:start">${ocrPanel}
      ${field('Tanggal transaksi*','transaction_date',t.transaction_date||'','date',true)}
      ${field('Nominal IDR*','amount',t.amount_cents===null?'':t.amount_cents/100,'number',true,'min="0" step="0.01"')}
      ${selectF('Kategori*','category_id',state.config.categories,t.category_id,true)}
      ${field('Vendor','vendor',t.vendor||'')}
      ${field('Keterangan*','description',t.description||'','text',true)}
      ${field('Metode Pembayaran','payment_method',t.payment_method||'')}
      ${field('Nomor Invoice','invoice_number',t.invoice_number||'')}
      <div class="field"><label>Catatan</label><textarea name="notes">${h(t.notes||'')}</textarea></div>
      <label class="checkrow" style="grid-column:1/-1"><input type="checkbox" name="mixed_receipt" ${mixed?'checked':''}>Kuitansi ini mencakup beberapa kategori</label>
      <button type="submit" class="btn primary" style="grid-column:1/-1">Simpan Draft</button>
    </form></div>`;
  modal('Periksa & Lengkapi Kuitansi',body,'<button class="btn outline" id="modal-done">Tutup</button>');
  $('#modal-done').onclick=closeModal;
  const draftForm=$('#draft-form');
  draftForm.addEventListener('click',ev=>{
    const amount=ev.target.closest('[data-ocr-amount]');
    if(amount){draftForm.elements.amount.value=amount.dataset.ocrAmount;return}
    const date=ev.target.closest('[data-ocr-date]');
    if(date){draftForm.elements.transaction_date.value=date.dataset.ocrDate}
  });
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

    if(!o.category_id)o.category_id=null;
    try{
      await patch('/transactions/'+id+'/draft',o);
      toast('Draft berhasil disimpan. OCR tidak otomatis menjadi approval.');
      closeModal();await nav(state.page==='upload'?'upload':'transactions');
    }catch(err){toast(err.message,true)}
  };
}

async function transactionsPage(){setHead(state.me.role==='admin'?'All Transactions':'My Transactions','Lihat status, dokumen, koreksi, dan riwayat');let rows=await loadTx();$('#page-content').innerHTML=`<div class="filters"><input id="tx-search" placeholder="Cari keterangan, aktivitas, atau uploader..."><select id="tx-status"><option value="ALL">Semua status</option>${['DRAFT','PENDING_REVIEW','APPROVED','REJECTED','REVERSED'].map(s=>`<option>${s}</option>`).join('')}</select><button class="btn outline" data-nav="${state.me.role==='admin'?'reviews':'upload'}">${state.me.role==='admin'?'Review Queue':'Upload Baru'}</button></div><section class="panel tx-compact" id="tx-results">${txTable(rows)}</section>`;
 function filter(){let q=$('#tx-search').value.toLowerCase(),s=$('#tx-status').value;$('#tx-results').innerHTML=txTable(rows.filter(t=>(s==='ALL'||t.status===s)&&[t.description,t.activity_name,t.uploader_name].some(x=>(x||'').toLowerCase().includes(q))))}
 $('#tx-search').oninput=filter;$('#tx-status').onchange=filter;
}
async function details(id){let t=state.transactions.find(t=>t.id===id)|| (await loadTx()).find(t=>t.id===id);if(!t)return;
 let data=await json('/transactions/'+id+'/history');modal('Detail Transaksi',`<div class="grid2"><div><h3>${h(t.description||'Transaksi')}</h3><table class="small-table"><tr><td>Status</td><td>${pill(t.status)}</td></tr><tr><td>Nominal</td><td><b>${rp(t.amount_cents)}</b></td></tr><tr><td>Tanggal</td><td>${h(t.transaction_date)}</td></tr><tr><td>Aktivitas</td><td>${h(t.activity_name)}</td></tr><tr><td>Uploader</td><td>${h(t.uploader_name)}</td></tr><tr><td>Kategori</td><td>${h(t.category_name)}</td></tr></table><a target="_blank" href="/api/receipts/${t.document_id}">Buka kuitansi aktif ↗</a><h4>Versi dokumen</h4>${data.versions.map(v=>`<div class="tiny"><a target="_blank" href="/api/receipts/${t.document_id}?version=${v.version_number}">Versi ${v.version_number}: ${h(v.filename)}</a></div>`).join('')}</div><div><h3>Audit Trail</h3>${data.audit.length?data.audit.map(a=>`<div class="hint mb"><b>${h(a.action)}</b><div class="tiny muted">${short(a.created_at)}</div></div>`).join(''):'<p class="muted">Belum ada histori.</p>'}</div></div>`,'<button class="btn outline" id="modal-done">Tutup</button>');$('#modal-done').onclick=closeModal;
}
async function correctionForm(id){let t=state.transactions.find(x=>x.id===id);if(!t)return;
 modal('Ajukan Koreksi',`<div class="notice">Data resmi tidak berubah selama koreksi menunggu persetujuan admin.</div><form id="correction-form" class="mt"><div class="field"><label>Alasan koreksi*</label><textarea name="reason" required minlength="5" placeholder="Jelaskan alasan perubahan"></textarea></div><div class="grid2 mt">${field('Nominal baru (kosong = tidak diubah)','amount','','number',false,'min="0" step="0.01"')}${field('Keterangan baru','description','')}${field('Tanggal baru','transaction_date','','date')}${selectF('Kategori baru','category_id',state.config.categories,null)}</div><div class="field mt"><label>File kuitansi pengganti (opsional)</label><input type="file" name="replacement" accept=".pdf,.png,.jpg,.jpeg,.webp"></div><button type="submit" class="btn primary mt">Kirim Permintaan Koreksi</button></form>`);
 $('#correction-form').onsubmit=async e=>{e.preventDefault();let form=e.currentTarget;let f=new FormData(form),p={};for(let key of ['amount','description','transaction_date','category_id'])if(f.get(key)!=='')p[key]=f.get(key);let file=form.elements.replacement.files[0];if(file && !Object.keys(p).length)p.notes=t.notes||'';
 if(!Object.keys(p).length)return toast('Isi data yang dikoreksi atau pilih kuitansi pengganti',true);
 try{let r=await post('/transactions/'+id+'/corrections',{reason:f.get('reason'),proposed:p});if(file){let fd=new FormData();fd.append('file',file);await json('/corrections/'+r.id+'/replacement',{method:'POST',body:fd})}toast('Permintaan koreksi dikirim dan menunggu admin');closeModal();await nav('transactions')}catch(ex){toast(ex.message,true)}};
}
async function actionReverse(id){let reason=prompt('Alasan pembatalan approval (wajib, minimal 5 karakter):');if(!reason)return;if(!confirm('Yakin reverse transaksi ini? Transaksi tidak lagi masuk laporan terbaru.'))return;try{await post('/admin/transactions/'+id+'/reverse',{reason});toast('Transaksi dibatalkan dengan audit trail');await nav('transactions')}catch(e){toast(e.message,true)}}
async function actionReinstate(id){let reason=prompt('Alasan reinstatement (minimal 5 karakter):');if(!reason)return;try{let r=await post('/transactions/'+id+'/reinstatement',{reason});toast(`Reinstatement pending. SLA: ${r.sla_status}`);await nav('transactions')}catch(e){toast(e.message,true)}}
async function actionDelete(id){if(!confirm('Soft-delete draft? Admin dapat memulihkannya dalam 30 hari.'))return;try{await json('/transactions/'+id+'/draft',{method:'DELETE'});toast('Draft soft-deleted');await nav('upload')}catch(e){toast(e.message,true)}}
async function reviewsPage(){setHead('Review Queue','Keputusan admin satu per satu, dengan alasan dan histori');state.queue=await json('/admin/review-queue');let q=state.queue;
 const row=(title,sub,type,id,extra='',provisional=false)=>`<div class="review-card"><div><strong>${h(title)}</strong><small>${h(sub)}</small>${extra}</div><div class="inline-actions"><button class="btn primary" data-review="${type}:${id}:APPROVE">Approve</button><button class="btn danger" data-review="${type}:${id}:REJECT">Reject</button>${type==='reinstatement'?`<button class="btn outline" data-escalate="${id}">Eskalasi</button>${provisional?`<button class="btn soft" data-snooze="${id}">Snooze</button>`:''}`:''}</div></div>`;
 $('#page-content').innerHTML=`<div class="kpis"><div class="kpi"><small>Pending Transaction</small><strong>${q.transactions.length}</strong></div><div class="kpi"><small>Correction Requests</small><strong>${q.corrections.length}</strong></div><div class="kpi orange"><small>Reinstatement</small><strong>${q.reinstatements.length}</strong></div></div>
 <section class="panel mt"><div class="panelhead"><div><h3>Transaksi berisiko</h3><small>Manual approval only</small></div></div>${q.transactions.map(t=>row(t.description||'Tanpa keterangan',(JSON.parse(t.risk_reasons||'[]')).join(' • ')||'Perlu review','transaction',t.id,`<small>Nominal: ${rp(t.amount_cents)} | Uploader: ${h(t.uploader_name)}</small><a target="_blank" href="/api/receipts/${t.document_id}">Lihat kuitansi ↗</a>`)).join('')||'<div class="empty">Tidak ada transaksi yang perlu review.</div>'}</section>
 <section class="panel mt"><div class="panelhead"><h3>Permintaan Koreksi</h3></div>${q.corrections.map(r=>row(r.description||'Transaksi',r.reason+' · Usulan: '+r.proposed_json,'correction',r.id)).join('')||'<div class="empty">Tidak ada koreksi pending.</div>'}</section>
 <section class="panel mt"><div class="panelhead"><h3>Permintaan Reinstatement</h3></div>${q.reinstatements.map(r=>row(r.description||'Transaksi',`Status SLA: ${r.sla_status}; penugasan: ${r.assignment_stage}; due: ${r.due_at||r.provisional_due_at||'—'}`,'reinstatement',r.id,`<small>Pemohon: ${h(r.requester_id)} | ${h(r.reason)}</small>`,r.sla_status==='PROVISIONAL'&&!r.snoozed_at)).join('')||'<div class="empty">Tidak ada reinstatement pending.</div>'}</section>`;
}
async function reviewAction(spec){let [kind,id,decision]=spec.split(':');let reason=prompt(`Alasan ${decision==='APPROVE'?'persetujuan':'penolakan'} (wajib untuk tindakan berisiko):`);if(!reason)return;let route=kind==='transaction'?'/admin/transactions/'+id+'/decision':kind==='correction'?'/admin/corrections/'+id+'/decision':'/admin/reinstatements/'+id+'/decision';if(!confirm('Konfirmasi keputusan '+decision+'?'))return;try{await post(route,{decision,reason});toast('Keputusan disimpan dengan audit');await nav('reviews')}catch(e){toast(e.message,true)}}
async function reportsPage(){
 if(state.me.role==='admin' && (await json('/health')).mode==='DEMO LOCAL'){
   if(state.page!=='reports')return;
   setHead('Reports & Excel','Rekap keuangan berdasarkan periode pilihan');
   const params='year='+financeYear+(financeMonth?'&month='+financeMonth:'');
   const d=await json('/finance/summary?'+params);
   if(state.page!=='reports')return;
   $('#page-content').innerHTML=`<div class="dash-toolbar"><div><h2>Rekap Keuangan MHS</h2><p>Periode yang sama dengan dashboard</p></div><div class="dash-toolbar-actions"><label class="finance-filter">Tahun <select id="report-year">${yearOptions(d)}</select></label><label class="finance-filter">Bulan <select id="report-month" ${financeYear===0?'disabled':''}><option value="0">Semua</option>${['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'].map((m,i)=>`<option value="${i+1}" ${financeMonth===i+1?'selected':''}>${m}</option>`).join('')}</select></label></div></div>
   <div class="dash-kpi-grid">${[['Pemasukan',d.income_cents],['Pengeluaran',d.total_cents],['Selisih tercatat',d.net_cents]].map(([label,v])=>`<div class="dash-card"><div class="dash-card-title">${label}</div><div class="dash-val">${rp(v)}</div></div>`).join('')}</div>
   <section class="panel panelpad mt"><h3>Unduh laporan periode</h3><p class="muted">Ringkasan, Semua Transaksi, Pemasukan, Pengeluaran, Report Info. Pengeluaran APPROVED dan pemasukan aktif saja.</p><button class="btn primary" id="finance-export">Download Excel (.xlsx)</button><p class="tiny muted">Snapshot tidak berubah setelah koreksi. Tautan kuitansi memerlukan login aktif pada server lokal. Bukan laporan pajak resmi.</p>${d.legacy_income_cents?`<div class="notice">Nilai lama tanpa tanggal ${rp(d.legacy_income_cents)} tidak dihitung.</div>`:''}</section>
   <section class="panel panelpad mt"><h3>Ekspor pengeluaran lama</h3><p class="muted">Format kompatibilitas lama, seluruh periode atau aktivitas terpilih; tidak memuat pemasukan.</p><div class="field"><label>Aktivitas</label><select id="report-activity">${opts(state.config.activities,null,'Semua aktivitas')}</select></div><button class="btn outline mt" id="export-xlsx">Download format lama</button></section>`;
   $('#report-year').onchange=e=>financePeriodChange(e,'reports');
   $('#report-month').onchange=e=>{financeMonth=Number(e.target.value);nav('reports')};
   $('#finance-export').onclick=async()=>{const btn=$('#finance-export');btn.disabled=true;try{const res=await api('/finance/export?'+params);const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='MHS_Rekap_Keuangan_'+(financeYear||'Semua_Tahun')+(financeMonth?'-'+String(financeMonth).padStart(2,'0'):'')+'.xlsx';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);toast('Laporan Excel berhasil dibuat')}catch(e){toast(e.message,true)}finally{btn.disabled=false}};
   $('#export-xlsx').onclick=()=>{const a=$('#report-activity').value;window.location.href='/api/reports/export'+(a?'?activity_id='+encodeURIComponent(a):'')};
   return;
 }
 setHead('Reports & Excel','Ekspor snapshot XLSX dengan data APPROVED saja');const [d,rows]=await Promise.all([json('/dashboard'),loadTx()]);$('#page-content').innerHTML=`<div class="grid2"><section class="panel panelpad"><h3>Ringkasan Pengeluaran</h3><div class="kpi" style="box-shadow:none;margin:15px 0"><small>APPROVED TOTAL</small><strong>${rp(d.total_cents)}</strong><span class="muted tiny">${d.receipt_count} kuitansi disetujui</span></div><div class="field"><label>Filter aktivitas</label><select id="report-activity">${opts(state.config.activities,null,'Semua aktivitas')}</select></div><button class="btn primary mt" id="export-xlsx">⬇ Download Excel (.xlsx)</button><p class="muted tiny">Berisi Transactions, Summary, dan Report Info. Histori ekspor tidak berubah setelah transaksi dikoreksi atau dibatalkan.</p></section><section class="panel panelpad"><h3>Kontrol Pelaporan</h3><div class="notice mt">Transaksi REVERSED, REJECTED, draft, dan PENDING_REVIEW tidak masuk total. Koreksi pending juga tidak mengubah nilai resmi.</div><p class="muted mt">Tautan kuitansi di Excel memerlukan login aktif sesuai hak akses pengguna.</p></section></div><section class="panel mt"><div class="panelhead"><h3>Data yang akan diekspor</h3></div>${txTable(rows.filter(t=>t.status==='APPROVED'),false)}</section>`;
 $('#export-xlsx').onclick=()=>{let a=$('#report-activity').value;window.location.href='/api/reports/export'+(a?'?activity_id='+encodeURIComponent(a):'')};
}
async function calendarPage(){setHead('Calendar & SLA','Hari kerja, verifikasi manual kalender, dan provisional SLA');let c=await json('/admin/calendar');let a=c.active;
 $('#page-content').innerHTML=`<div class="grid2"><section class="panel panelpad"><h3>Status Kalender</h3><p>Versi kalender: <b>${a.version}</b></p><p>Zona waktu: <b>${h(a.timezone)}</b></p><p>Verifikasi: ${pill(a.verified?'FINAL':'PROVISIONAL')}</p><div class="notice mt">Default hari kerja Senin–Jumat 09.00–17.00 WIB. Kalender awal tidak terverifikasi; eskalasi otomatis diblokir. Sumber hari libur resmi perlu diverifikasi admin secara manual pada V0.1.</div></section><section class="panel panelpad"><h3>Stage Hari Libur (Manual)</h3><p class="muted tiny">Masukkan satu tanggal YYYY-MM-DD per baris. Verifikasi terhadap SKB pemerintah secara mandiri sebelum publish.</p><form id="holiday-form"><div class="field"><label>Sumber resmi / referensi SKB</label><input name="source" required placeholder="Contoh: SKB Pemerintah Indonesia ..."></div><div class="field mt"><label>Daftar hari libur</label><textarea name="holidays" placeholder="2026-12-25\n2027-01-01"></textarea></div><button class="btn primary mt">Stage Kalender</button></form></section></div><section class="panel mt"><div class="panelhead"><h3>Pending Calendar Imports</h3></div>${c.imports.length?c.imports.map(i=>`<div class="review-card"><div><strong>${h(i.source)}</strong><small>${h(i.status)} · ${h(i.year_start)}–${h(i.year_end)} · ${h(i.entries_json)}</small></div>${i.status==='STAGED'?`<button class="btn primary" data-publish="${i.id}">Verifikasi & Publish</button>`:pill(i.status)}</div>`).join(''):'<div class="empty">Belum ada impor kalender.</div>'}</section>`;
 $('#holiday-form').onsubmit=async e=>{e.preventDefault();let fd=new FormData(e.currentTarget);try{await post('/admin/calendar/stage',{source:fd.get('source'),holidays:fd.get('holidays').split(/[\n,]+/).map(x=>x.trim()).filter(Boolean)});toast('Data kalender di-stage. Pastikan semua hari libur resmi benar.');await nav('calendar')}catch(ex){toast(ex.message,true)}};
}
async function managementPage(){setHead('Management','Kelola kegiatan dan kategori pengeluaran');
 $('#page-content').innerHTML=`<div class="grid2"><section class="panel panelpad"><h3>Aktivitas</h3><div class="mt">${state.config.activities.map(a=>`<div class="hint mb"><b>${h(a.name)}</b><div>${pill(a.closure_status)} <button class="btn outline" data-activity="${a.id}:${a.closure_status==='OPEN'?'CLOSED':'OPEN'}">${a.closure_status==='OPEN'?'Close':'Reopen'}</button></div></div>`).join('')}</div><form id="act-form" class="mt"><div class="field"><label>Aktivitas baru</label><input name="name" minlength="3" required></div><button class="btn primary mt">Tambah Aktivitas</button></form></section><section class="panel panelpad"><h3>Kategori Pengeluaran</h3><div class="mt">${state.config.categories.map(c=>`<div class="hint mb">${h(c.name)}</div>`).join('')}</div><form id="cat-form"><div class="field"><label>Kategori baru</label><input name="name" minlength="2" required></div><button class="btn primary mt">Tambah Kategori</button></form></section></div>`;
 for(let [f,route] of [['act-form','/admin/activities'],['cat-form','/admin/categories']])$('#'+f).onsubmit=async e=>{e.preventDefault();let data=Object.fromEntries(new FormData(e.currentTarget));try{await post(route,data);toast('Data dibuat');state.config=await json('/config');await nav('management')}catch(ex){toast(ex.message,true)}};
}
async function auditPage(){setHead('Audit Trail','Riwayat keputusan dan perubahan finansial');let logs=await json('/admin/audit');$('#page-content').innerHTML=`<section class="panel"><div class="panelhead"><h3>Recent Audit Events</h3><small>Terbaru lebih dahulu</small></div><div class="tablescroll"><table class="data-table"><thead><tr><th>WAKTU UTC</th><th>AKSI</th><th>OLEH</th><th>OBJEK</th><th>DETAIL</th></tr></thead><tbody>${logs.map(a=>`<tr><td class="nowrap">${short(a.created_at)}</td><td><b>${h(a.action)}</b></td><td>${h(a.actor_name||'SYSTEM')}</td><td>${h(a.target_type)}</td><td class="clamp" title="${h(a.details)}">${h(a.details)}</td></tr>`).join('')}</tbody></table></div></section>`}
async function notificationsPage(){setHead('Notifications','Informasi transaksi dan keputusan');let ns=await json('/notifications');$('#page-content').innerHTML=`<section class="panel">${ns.length?ns.map(n=>`<div class="review-card"><div><strong>${h(n.type)}</strong><small>${h(n.message)} · ${short(n.created_at)}</small></div></div>`).join(''):'<div class="empty">Belum ada notifikasi.</div>'}</section>`}

// Centralized delegated click handlers also work after page rerenders.
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-nav],[data-edit],[data-detail],[data-correction],[data-reinstate],[data-reverse],[data-delete],[data-review],[data-publish],[data-activity],[data-escalate],[data-snooze]');if(!el)return;
 try{
 if(el.dataset.nav)await nav(el.dataset.nav);
 else if(el.dataset.edit)await editDraft(el.dataset.edit);
 else if(el.dataset.detail)await details(el.dataset.detail);
 else if(el.dataset.correction)await correctionForm(el.dataset.correction);
 else if(el.dataset.reinstate)await actionReinstate(el.dataset.reinstate);
 else if(el.dataset.reverse)await actionReverse(el.dataset.reverse);
 else if(el.dataset.delete)await actionDelete(el.dataset.delete);
 else if(el.dataset.review)await reviewAction(el.dataset.review);
 else if(el.dataset.publish){if(confirm('Sudah memverifikasi daftar hari libur ini dengan sumber pemerintah resmi?')){await post('/admin/calendar/'+el.dataset.publish+'/publish',{});toast('Kalender dipublikasikan; SLA provisional pending difinalkan');await nav('calendar')}}
 else if(el.dataset.activity){let [id,closure_status]=el.dataset.activity.split(':');await patch('/admin/activities/'+id,{closure_status});state.config=await json('/config');await nav('management')}
 else if(el.dataset.escalate){let reason=prompt('Alasan eskalasi manual (minimal 5 karakter):');if(reason){await post('/admin/reinstatements/'+el.dataset.escalate+'/escalate',{reason});toast('Dikirim ke penugasan backup');await nav('reviews')}}
 else if(el.dataset.snooze){let reason=prompt('Alasan snooze reminder satu kali selama 24 jam kerja:');if(reason){await post('/admin/reinstatements/'+el.dataset.snooze+'/snooze',{reason});toast('Reminder ditunda tanpa mengubah SLA');await nav('reviews')}}
 }catch(err){toast(err.message,true)}
});
$('#dialog-close').onclick=closeModal;$('#dialog-overlay').addEventListener('click',e=>{if(e.target.id==='dialog-overlay')closeModal()});
$('#mobile-toggle').onclick=()=>{$('#sidebar').classList.add('open');$('#mobile-mask').classList.remove('hidden')};
$('#mobile-mask').onclick=()=>{$('#sidebar').classList.remove('open');$('#mobile-mask').classList.add('hidden')};
$('#logout').onclick=async()=>{try{await post('/auth/logout',{})}catch(e){}state.me=null;showLogin()};
for(let button of document.querySelectorAll('[data-demo]'))button.onclick=()=>{let accounts={admin:['admin@mhs.local','AdminDemo123!']};let [email,password]=accounts[button.dataset.demo];$('#login-form [name=email]').value=email;$('#login-form [name=password]').value=password};
if($('#login-form')) $('#login-form').onsubmit=async e=>{e.preventDefault();const email=$('#login-form [name=email]').value,password=$('#login-form [name=password]').value;try{let r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password}),credentials:'same-origin'});if(!r.ok)throw new Error('Email atau password salah');state.me=await json('/me');state.config=await json('/config');showApp();await nav('dashboard');toast('Berhasil masuk sebagai '+state.me.role)}catch(err){toast(err.message,true)}};
(async()=>{try{state.me=await json('/me');state.config=await json('/config');showApp();await nav('dashboard')}catch(e){showLogin()}
 if(new URLSearchParams(location.search).get('login')==='denied'){toast('Login ditolak atau sesi Google gagal. Gunakan akun owner yang terdaftar.',true);history.replaceState(null,'',location.pathname)}
})();
