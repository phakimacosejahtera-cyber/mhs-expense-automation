"""PT Mulia Hakimaco Sejahtera - local development MVP.
Never deploy this demo configuration on the public internet.
Rules are enforced server-side; UI alone is NOT an authorization boundary.
"""
from .runtime import require_local_app

APP_MODE = require_local_app()
HOSTED_PREVIEW = APP_MODE == 'hosted_preview'
from .owner_auth import OwnerConfig, OwnerAuthError, new_verifier, authorize_url, exchange_owner
OWNER_CONFIG = OwnerConfig.from_env() if APP_MODE in ('owner_test', 'pg_test', 'hosted_preview') else None

import os, json, hashlib, secrets, mimetypes, re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from io import BytesIO
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request,HTTPException,UploadFile,File,Form
from fastapi.responses import HTMLResponse,FileResponse,Response,StreamingResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from .db import ROOT,DATA,init_schema,connection,tx,one,allrows,now,uid,js,audit,notify
from .security import password_hash,verify_password,create_session,get_auth,admin_only,own_or_admin,token_hash
from .rules import amount_to_cents,risk_reasons,business_due
from .receipt_storage import configured_storage, StorageError, PREFIX, legacy_local_path
from urllib.parse import quote, urlsplit
from .https_security import apply_security_headers, cookie_secure
HTTPS_OWNER = cookie_secure(OWNER_CONFIG)
PUBLIC_ORIGIN = OWNER_CONFIG.callback.rsplit('/api/auth/google/callback',1)[0] if HTTPS_OWNER else None
CLOUD_STORAGE = configured_storage(APP_MODE)

app=FastAPI(title='PT Mulia Hakimaco Sejahtera — Expense Automation',version='0.1.0', docs_url=None if OWNER_CONFIG else '/docs', redoc_url=None if OWNER_CONFIG else '/redoc', openapi_url=None if OWNER_CONFIG else '/openapi.json')
app.mount('/assets',StaticFiles(directory=ROOT/'frontend'/'assets'),name='assets')

@app.middleware('http')
async def security_boundary(request:Request,call_next):
    if HTTPS_OWNER:
        if request.headers.get('host','').lower() != urlsplit(PUBLIC_ORIGIN).netloc:
            return apply_security_headers(Response('Invalid host',status_code=400),request.url.path,True)
        if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') != PUBLIC_ORIGIN:
            return apply_security_headers(Response('Invalid origin',status_code=403),request.url.path,True)
    if HOSTED_PREVIEW and request.method not in ('GET','HEAD','OPTIONS'):
        if request.url.path == '/api/auth/login':
            return apply_security_headers(Response('Google owner login only',status_code=403),request.url.path,True)
        try:
            await run_in_threadpool(get_auth,request,True)
        except HTTPException as e:
            return apply_security_headers(Response(js({'detail':e.detail}),status_code=e.status_code,media_type='application/json'),request.url.path,True)
        # Reject oversized or unbounded multipart before parsing the request body.
        length=request.headers.get('content-length')
        multipart=request.headers.get('content-type','').lower().startswith('multipart/form-data')
        limit=9*1024*1024 if multipart else 1024*1024
        if length is not None and (not length.isdigit() or int(length)>limit):
            return apply_security_headers(Response('Request terlalu besar atau tidak valid',status_code=413),request.url.path,True)
        if multipart and length is None:
            return apply_security_headers(Response('Content-Length required',status_code=411),request.url.path,True)
    response = await call_next(request)
    return apply_security_headers(response,request.url.path,HTTPS_OWNER)


def startup():
    if CLOUD_STORAGE:
        CLOUD_STORAGE.check_private()
    init_schema()
    if HOSTED_PREVIEW:
        # Reuse only the already initialized synthetic test data and its bound owner.
        with connection() as c:
            existing=allrows(c,'SELECT email,role,active FROM users')
            binding=one(c,'SELECT supabase_id,google_sub FROM owner_login_identity WHERE singleton=1')
            if (len(existing)!=1 or existing[0]['email']!=OWNER_CONFIG.email or existing[0]['role']!='admin' or not existing[0]['active'] or not binding or not binding['supabase_id'] or not binding['google_sub']):
                raise RuntimeError('Hosted preview requires an existing active and bound test owner')
            if OWNER_CONFIG.pin and (binding['supabase_id'],binding['google_sub'])!=OWNER_CONFIG.pin:
                raise RuntimeError('Hosted preview owner binding mismatch')
        return
    with tx() as c:
        if OWNER_CONFIG:
            c.execute("""CREATE TABLE IF NOT EXISTS owner_login_identity (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                supabase_id TEXT NOT NULL, google_sub TEXT NOT NULL
            )""")
            existing = allrows(c,'SELECT email,role FROM users')
            if existing and (len(existing)!=1 or existing[0]['email']!=OWNER_CONFIG.email or existing[0]['role']!='admin'):
                raise RuntimeError('Owner test database contains unexpected accounts; use a fresh isolated database.')
        if not one(c,'SELECT id FROM users LIMIT 1'):
            accounts = [('Owner MHS',OWNER_CONFIG.email,'admin',secrets.token_urlsafe(48))] if OWNER_CONFIG else [
                ('Admin MHS','admin@mhs.local','admin','AdminDemo123!')]
            for name,email,role,pw in accounts:
                c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(uid(),name,email,password_hash(pw),role,1,now()))
            for cat in ['Transportasi','Konsumsi','Akomodasi','Logistik','ATK','Operasional Lainnya']:
                c.execute('INSERT INTO categories VALUES (?,?,1)',(uid(),cat))
            c.execute('INSERT INTO activities(id,name,created_at) VALUES (?,?,?)',(uid(),'Kegiatan Operasional 2026',now()))
            hours={str(i):[['09:00','17:00']] for i in range(5)}
            c.execute('INSERT INTO calendar_versions VALUES (?,?,?,?,?,?,?,?,?)',
                      (uid(),1,0,'Asia/Jakarta',js(hours),'[]','DEMO: kalender belum diverifikasi',now(),None))

@asynccontextmanager
async def lifespan(app):
    startup()
    yield

app.router.lifespan_context=lifespan

@app.get('/',response_class=HTMLResponse)
def home():
    html = (ROOT/'frontend'/'index.html').read_text(encoding='utf-8')
    if OWNER_CONFIG:
        start = html.index('<form id="login-form">')
        end = html.index('</div>', html.index('<div class="security-hint">', start)) + len('</div>')
        html = html[:start] + (
            '<a class="btn primary full" href="/api/auth/google/start">Masuk dengan Google</a>'
            '<div class="security-hint">Khusus owner. Mode uji lokal — gunakan kuitansi contoh saja.</div>'
        ) + html[end:]
        html = html.replace('LOCAL DEVELOPMENT • V0.1','OWNER LOGIN TEST')
        html = html.replace('Local Development <small>v0.1 • Data tersimpan di SQLite lokal','Owner Login Test <small>Data uji SQLite terpisah')
        html = html.replace('DEVELOPMENT MODE','OWNER TEST')
        if APP_MODE == 'pg_test':
            html = html.replace('Data uji SQLite terpisah', 'Database PostgreSQL uji • Private Storage uji' if CLOUD_STORAGE else 'Database PostgreSQL uji • kuitansi masih lokal')
        if HOSTED_PREVIEW:
            html = html.replace('OWNER LOGIN TEST','HOSTED PREVIEW').replace('OWNER TEST','PREVIEW — DATA SIMULASI')
            html = html.replace('Owner Login Test','Hosted Preview').replace('Data uji SQLite terpisah','Supabase uji • Jangan gunakan data asli')
            html = html.replace('Mode uji lokal — gunakan kuitansi contoh saja.','Uji online — gunakan data simulasi saja.')
    return HTMLResponse(html,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

@app.get('/api/health')
def health():return {'ok':True,'name':'PT Mulia Hakimaco Sejahtera','mode':'HOSTED PREVIEW — SYNTHETIC ONLY' if HOSTED_PREVIEW else 'POSTGRES TEST LOCAL' if APP_MODE=='pg_test' else ('OWNER TEST LOCAL' if OWNER_CONFIG else 'DEMO LOCAL'),'version':'0.1.0'}

class Login(BaseModel):email:str;password:str
@app.post('/api/auth/login')
def login(data:Login):
    if OWNER_CONFIG:raise HTTPException(403,'Gunakan login Google owner')
    with tx() as c:
        u=one(c,'SELECT * FROM users WHERE lower(email)=lower(?) AND active=1',(data.email.strip(),))
        if not u or not verify_password(data.password,u['password_hash']):raise HTTPException(401,'Email atau password salah')
        token,csrf=create_session(c,u['id'])
    resp=Response(content=js({'ok':True,'csrf':csrf}),media_type='application/json')
    resp.set_cookie('mhs_session',token,httponly=True,samesite='strict',secure=False,path='/',max_age=43200)
    return resp

@app.get('/api/auth/google/start')
def google_start(request:Request):
    if not OWNER_CONFIG:raise HTTPException(404,'Google login tidak aktif')
    verifier = new_verifier()
    resp = RedirectResponse(authorize_url(OWNER_CONFIG,verifier),status_code=303,
                            headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    resp.set_cookie('mhs_oauth_verifier',verifier,httponly=True,samesite='lax',secure=HTTPS_OWNER,
                    max_age=600,path='/api/auth/google/callback')
    return resp

@app.get('/api/auth/google/callback')
def google_callback(request:Request,code:str|None=None):
    if not OWNER_CONFIG:raise HTTPException(404,'Google login tidak aktif')
    denied = RedirectResponse('/?login=denied',status_code=303,
                              headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    denied.delete_cookie('mhs_oauth_verifier',path='/api/auth/google/callback',secure=HTTPS_OWNER,httponly=True,samesite='lax')
    try:
        supabase_id, google_sub = exchange_owner(OWNER_CONFIG,code,request.cookies.get('mhs_oauth_verifier'))
        if OWNER_CONFIG.pin is not None and (supabase_id,google_sub) != OWNER_CONFIG.pin:
            raise OwnerAuthError()
        with tx() as c:
            u=one(c,'SELECT * FROM users WHERE email=? AND role=? AND active=1',(OWNER_CONFIG.email,'admin'))
            if not u:raise OwnerAuthError()
            binding=one(c,'SELECT * FROM owner_login_identity WHERE singleton=1')
            if binding:
                if binding['supabase_id']!=supabase_id or binding['google_sub']!=google_sub:
                    raise OwnerAuthError()
            else:
                if HOSTED_PREVIEW:raise OwnerAuthError()
                c.execute('INSERT INTO owner_login_identity VALUES (1,?,?)',(supabase_id,google_sub))
            old=request.cookies.get('mhs_session')
            if old:c.execute('DELETE FROM sessions WHERE id_hash=?',(token_hash(old),))
            token,csrf=create_session(c,u['id'])
            audit(c,u['id'],'OWNER_GOOGLE_LOGIN','user',u['id'])
    except OwnerAuthError:
        return denied
    resp=RedirectResponse('/',status_code=303,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    resp.delete_cookie('mhs_oauth_verifier',path='/api/auth/google/callback',secure=HTTPS_OWNER,httponly=True,samesite='lax')
    resp.set_cookie('mhs_session',token,httponly=True,samesite='strict',secure=HTTPS_OWNER,path='/',max_age=43200)
    return resp

@app.get('/api/me')
def me(request:Request):return get_auth(request)

@app.post('/api/auth/logout')
def logout(request:Request):
    u=get_auth(request,True)
    with tx() as c:c.execute('DELETE FROM sessions WHERE id_hash=?',(token_hash(request.cookies['mhs_session']),))
    resp=Response(content=js({'ok':True}),media_type='application/json');resp.delete_cookie('mhs_session',path='/',secure=HTTPS_OWNER,httponly=True,samesite='strict');return resp

def auth(request:Request,write=False):return get_auth(request,unsafe=write)

@app.get('/api/config')
def config(request:Request):
    u=auth(request)
    with connection() as c:
        cats=allrows(c,'SELECT id,name FROM categories WHERE active=1 ORDER BY name')
        acts=allrows(c,'SELECT id,name,status,closure_status FROM activities WHERE status != ? ORDER BY name',('ARCHIVED',))
    return {'categories':cats,'activities':acts,'company':'PT Mulia Hakimaco Sejahtera','user':u}

class ActivityIn(BaseModel):name:str=Field(min_length=3,max_length=100)
@app.post('/api/admin/activities')
def create_activity(request:Request,data:ActivityIn):
    u=auth(request,True);admin_only(u)
    key=uid()
    with tx() as c:
        c.execute('INSERT INTO activities(id,name,created_at) VALUES (?,?,?)',(key,data.name.strip(),now()))
        audit(c,u['id'],'ACTIVITY_CREATED','activity',key,{'name':data.name})
    return {'id':key}

class ActivityUpdate(BaseModel):status:str|None=None;closure_status:str|None=None
@app.patch('/api/admin/activities/{activity_id}')
def update_activity(request:Request,activity_id:str,data:ActivityUpdate):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        a=one(c,'SELECT * FROM activities WHERE id=?',(activity_id,))
        if not a:raise HTTPException(404,'Aktivitas tidak ditemukan')
        status=data.status or a['status']; closure=data.closure_status or a['closure_status']
        if status not in ('ACTIVE','COMPLETED','ARCHIVED') or closure not in ('OPEN','CLOSED'):
            raise HTTPException(422,'Status aktivitas tidak dikenal')
        c.execute('UPDATE activities SET status=?,closure_status=?,closed_at=? WHERE id=?',
                  (status,closure,now() if closure=='CLOSED' and a['closure_status']!='CLOSED' else a['closed_at'],activity_id))
        audit(c,u['id'],'ACTIVITY_UPDATED','activity',activity_id,{'status':status,'closure_status':closure})
    return {'ok':True}

class CategoryIn(BaseModel):name:str=Field(min_length=2,max_length=80)
@app.post('/api/admin/categories')
def create_category(request:Request,data:CategoryIn):
    u=auth(request,True);admin_only(u);key=uid()
    with tx() as c:
        try:c.execute('INSERT INTO categories VALUES (?,?,1)',(key,data.name.strip()))
        except Exception:raise HTTPException(409,'Kategori sudah tersedia')
        audit(c,u['id'],'CATEGORY_CREATED','category',key,{'name':data.name})
    return {'id':key}

class UserIn(BaseModel):name:str=Field(min_length=2);email:str;password:str=Field(min_length=10);role:str='uploader'
@app.post('/api/admin/users')
def create_user(request:Request,data:UserIn):
    u=auth(request,True);admin_only(u)
    if OWNER_CONFIG:raise HTTPException(403,'Tidak ada akun tambahan pada mode owner')
    if data.role!='uploader':raise HTTPException(403,'MVP demo hanya menyediakan provisioning uploader; admin cadangan sudah disediakan')
    if '@' not in data.email:raise HTTPException(422,'Email tidak valid')
    key=uid()
    with tx() as c:
        try:c.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',(key,data.name,data.email.lower().strip(),password_hash(data.password),data.role,1,now()))
        except Exception:raise HTTPException(409,'Email sudah digunakan')
        audit(c,u['id'],'INVITED_USER_CREATED','user',key,{'email':data.email})
    return {'id':key,'notice':'Akun dibuat admin. Email invitation otomatis belum terintegrasi.'}

@app.get('/api/admin/users')
def users(request:Request):
    u=auth(request);admin_only(u)
    with connection() as c:return allrows(c,'SELECT id,name,email,role,active,created_at FROM users ORDER BY name')

class BatchIn(BaseModel):activity_id:str
@app.post('/api/batches')
def create_batch(request:Request,data:BatchIn):
    u=auth(request,True);key=uid()
    with tx() as c:
        a=one(c,'SELECT * FROM activities WHERE id=?',(data.activity_id,))
        if not a or a['status']=='ARCHIVED':raise HTTPException(422,'Aktivitas tidak tersedia')
        c.execute('INSERT INTO upload_batches VALUES (?,?,?,?,?)',(key,u['id'],data.activity_id,'PROCESSING',now()))
        audit(c,u['id'],'BATCH_CREATED','batch',key,{'activity_id':data.activity_id})
    return {'id':key,'status':'PROCESSING'}

MAX_FILE=8*1024*1024
ALLOWED={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}

def validate_bytes(filename,data):
    if not data:raise HTTPException(422,'File kosong')
    if len(data)>MAX_FILE:raise HTTPException(413,'Maksimum 8 MB per file')
    if data.startswith(b'%PDF-'):return 'application/pdf','.pdf'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png','.png'
    if data[:3]==b'\xff\xd8\xff':return 'image/jpeg','.jpg'
    if data.startswith(b'RIFF') and data[8:12]==b'WEBP':return 'image/webp','.webp'
    raise HTTPException(422,'Hanya PDF, PNG, JPEG, atau WEBP yang valid')

def store_file(data,ext):
    if CLOUD_STORAGE:
        try:
            return CLOUD_STORAGE.put(data,ext)
        except StorageError:
            raise HTTPException(503,'Penyimpanan cloud uji tidak tersedia') from None
    folder=DATA/'private_docs';folder.mkdir(parents=True,exist_ok=True)
    key=uid()+ext;path=folder/key;path.write_bytes(data)
    return str(path)

@app.post('/api/batches/{batch_id}/documents')
async def upload(request:Request,batch_id:str,file:UploadFile=File(...)):
    u=auth(request,True)
    raw=await file.read(MAX_FILE+1)
    mime,ext=validate_bytes(file.filename or '',raw)
    h=hashlib.sha256(raw).hexdigest();doc=uid();ver=uid();txid=uid();path=None
    try:
        with tx() as c:
            b=one(c,'SELECT * FROM upload_batches WHERE id=?',(batch_id,))
            if not b:raise HTTPException(404,'Batch tidak ditemukan')
            own_or_admin(u,b['uploader_id'])
            path=store_file(raw,ext)
            c.execute('INSERT INTO documents VALUES (?,?,?,?,?)',(doc,b['uploader_id'],batch_id,ver,now()))
            c.execute('INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?)',(ver,doc,1,(file.filename or 'receipt')[:240],mime,h,path,len(raw),now()))
            cats = allrows(c, 'SELECT id, name FROM categories WHERE active=1')
            from .ocr import extract_receipt
            ocr_res = extract_receipt(raw, mime, cats)
            d_ocr = ocr_res.get('data') or {}
            try:
                ocr_cents = amount_to_cents(d_ocr.get('amount')) if d_ocr.get('amount') not in (None, '') else None
            except Exception:
                ocr_cents = None

            c.execute('''INSERT INTO transactions(
                id,document_id,batch_id,uploader_id,activity_id,
                category_id,transaction_date,amount_cents,description,
                vendor,payment_method,invoice_number,notes,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                txid,doc,batch_id,b['uploader_id'],b['activity_id'],
                d_ocr.get('category_id'),
                d_ocr.get('transaction_date'),
                ocr_cents,
                (d_ocr.get('description') or '')[:500] or None,
                (d_ocr.get('vendor') or '')[:200] or None,
                (d_ocr.get('payment_method') or '')[:100] or None,
                (d_ocr.get('invoice_number') or '')[:100] or None,
                (d_ocr.get('notes') or '')[:1000] or None,
                now(),now()
            ))
            c.execute('INSERT INTO extraction_runs(id,document_id,status,provider,raw_json,created_at) VALUES (?,?,?,?,?,?)',
                      (uid(),doc,ocr_res['status'],ocr_res['provider'],js(ocr_res['raw']),now()))
            dup=one(c,'SELECT document_id FROM document_versions WHERE sha256=? AND document_id<>? LIMIT 1',(h,doc))
            risks=['Kemungkinan kuitansi duplikat'] if dup else []
            if risks:c.execute('UPDATE transactions SET risk_reasons=? WHERE id=?',(js(risks),txid))
            audit(c,u['id'],'DOCUMENT_UPLOADED','document',doc,{'sha256':h,'filename':file.filename,'duplicate_candidate':bool(dup)})
    except Exception:
        # Keep cloud objects on ambiguous DB failure; reconcile orphans before production.
        if path and not path.startswith(PREFIX):
            try:Path(path).unlink(missing_ok=True)
            except OSError:pass
        raise
    return {'document_id':doc,'transaction_id':txid,'ocr_status':'MANUAL_REQUIRED','risk_reasons':risks}

class BrowserOCRObservation(BaseModel):
    text: str = Field(max_length=16000)
    confidence: float | None = Field(default=None, ge=0, le=100)
    suggestions: dict = Field(default_factory=dict)

@app.post('/api/transactions/{txid}/ocr-result')
def save_browser_ocr(request:Request,txid:str,data:BrowserOCRObservation):
    u=auth(request,True)
    # OCR is only an untrusted observation, never VERIFIED or auto-approved.
    if len(js(data.suggestions))>8000:raise HTTPException(422,'Saran OCR terlalu besar')
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Draft tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        if t['status']!='DRAFT' or t['deleted_at']:raise HTTPException(409,'OCR hanya dapat disimpan untuk draft aktif')
        run_id=uid()
        c.execute('INSERT INTO extraction_runs(id,document_id,status,provider,raw_json,created_at) VALUES (?,?,?,?,?,?)',
                  (run_id,t['document_id'],'EXTRACTED','TESSERACT_JS_CLIENT',
                   js({'text':data.text,'confidence':data.confidence,'suggestions':data.suggestions}),now()))
        audit(c,u['id'],'OCR_CLIENT_RECORDED','document',t['document_id'],
              {'run_id':run_id,'provider':'TESSERACT_JS_CLIENT','verified':False})
    return {'ok':True,'status':'EXTRACTED','verified':False,'run_id':run_id}

@app.get('/api/transactions/{txid}/ocr-result')
def read_browser_ocr(request:Request,txid:str):
    u=auth(request)
    with connection() as c:
        t=one(c,'SELECT uploader_id,document_id FROM transactions WHERE id=? AND deleted_at IS NULL',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        row=one(c,"SELECT raw_json FROM extraction_runs WHERE document_id=? AND provider='TESSERACT_JS_CLIENT' ORDER BY created_at DESC, rowid DESC LIMIT 1",(t['document_id'],))
        if not row:raise HTTPException(404,'Belum ada hasil OCR Tesseract.js')
        return json.loads(row['raw_json'])

class DraftData(BaseModel):
    transaction_date:str|None=None;amount:str|int|float|None=None;description:str|None=None
    category_id:str|None=None;vendor:str|None=None;payment_method:str|None=None
    invoice_number:str|None=None;notes:str|None=None;mixed_receipt:bool=False

@app.patch('/api/transactions/{txid}/draft')
def edit_draft(request:Request,txid:str,data:DraftData):
    u=auth(request,True)
    if data.transaction_date:
        try:datetime.strptime(data.transaction_date,'%Y-%m-%d')
        except ValueError:raise HTTPException(422,'Format tanggal harus YYYY-MM-DD')
    try:cents=amount_to_cents(data.amount) if data.amount not in (None,'') else None
    except ValueError as e:raise HTTPException(422,str(e))
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        if t['status']!='DRAFT' or t['deleted_at']:raise HTTPException(409,'Hanya draft aktif yang dapat diedit langsung')
        if data.category_id and not one(c,'SELECT id FROM categories WHERE id=? AND active=1',(data.category_id,)):
            raise HTTPException(422,'Kategori tidak dikenal')
        fields=(data.transaction_date,cents,(data.description or '')[:500],data.category_id,
                (data.vendor or '')[:200],(data.payment_method or '')[:100],(data.invoice_number or '')[:100],
                (data.notes or '')[:2000],txid)
        c.execute('''UPDATE transactions SET transaction_date=?,amount_cents=?,description=?,category_id=?,vendor=?,payment_method=?,invoice_number=?,notes=?,revision=revision+1,updated_at=? WHERE id=?''',
                  fields[:-1]+(now(),fields[-1]))
        old=json.loads(t['risk_reasons'])
        old=[x for x in old if 'duplikat' in x.lower()]
        if data.mixed_receipt:old.append('Kuitansi berisi beberapa kategori')
        c.execute('UPDATE transactions SET risk_reasons=? WHERE id=?',(js(old),txid))
        audit(c,u['id'],'DRAFT_EDITED','transaction',txid,{'revision':t['revision']+1})
    return {'ok':True}

class SubmitIn(BaseModel):ids:list[str]=Field(min_length=1,max_length=100);late_reason:str|None=None
@app.post('/api/transactions/submit-batch')
def submit_batch(request:Request,data:SubmitIn):
    u=auth(request,True)
    if len(set(data.ids))!=len(data.ids):raise HTTPException(422,'ID transaksi ganda')
    results=[]
    with tx() as c:
        for txid in data.ids:
            t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
            if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
            own_or_admin(u,t['uploader_id'])
            if t['status']!='DRAFT' or t['deleted_at']:raise HTTPException(409,'Hanya draft aktif yang bisa disubmit')
            a=one(c,'SELECT * FROM activities WHERE id=?',(t['activity_id'],))
            late=a['closure_status']=='CLOSED'
            if late and not (data.late_reason or '').strip():raise HTTPException(422,'Alasan keterlambatan wajib diisi')
            dup=json.loads(t['risk_reasons'])
            clean={**t,'mixed_receipt':any('kategori' in x.lower() for x in dup)}
            risk=risk_reasons(clean,any('duplikat' in x.lower() for x in dup),late)
            missing=[x for x in risk if x.startswith('Data ')]
            if missing:raise HTTPException(422,f'Lengkapi data sebelum submit: {", ".join(missing)}')
            risky=[x for x in risk if not x.startswith('Data ')]
            extraction=one(c,'SELECT status,provider FROM extraction_runs WHERE document_id=? ORDER BY created_at DESC LIMIT 1',(t['document_id'],))
            if not extraction or extraction['status']!='VERIFIED':
                risky.append('Belum ada validasi OCR tepercaya; review admin wajib')
            # Auto approval only for validated trusted extraction AND no known risk.

            new_status='PENDING_REVIEW' if risky else 'APPROVED'
            c.execute('''UPDATE transactions SET status=?,risk_reasons=?,is_late=?,late_reason=?,submitted_at=?,approved_at=?,approved_by=?,revision=revision+1,updated_at=? WHERE id=?''',
                      (new_status,js(risky),1 if late else 0,data.late_reason if late else None,now(),now() if not risky else None,None,now(),txid))
            audit(c,u['id'],'TRANSACTION_SUBMITTED','transaction',txid,{'risk':risky,'status':new_status})
            if not risky:audit(c,None,'AUTO_APPROVED','transaction',txid,{'policy':'all_required_fields_present_and_no_known_risk'})
            else:
                for adm in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1"):
                    notify(c,adm['id'],'REVIEW',f'Transaksi menunggu review: {t["description"]}',f'pending-{txid}-{adm["id"]}')
            results.append({'id':txid,'status':new_status,'risk_reasons':risky})
        batch_ids={one(c,'SELECT batch_id FROM transactions WHERE id=?',(i,))['batch_id'] for i in data.ids}
        for bid in batch_ids:
            remaining=one(c,"SELECT count(*) AS n FROM transactions WHERE batch_id=? AND status='DRAFT' AND deleted_at IS NULL",(bid,))['n']
            c.execute('UPDATE upload_batches SET status=? WHERE id=?',('PARTIALLY_SUBMITTED' if remaining else 'FULLY_SUBMITTED',bid))
    return {'items':results}

@app.get('/api/transactions')
def transactions(request:Request,status:str|None=None):
    u=auth(request)
    where=['t.deleted_at IS NULL'];args=[]
    if u['role']!='admin':where.append('t.uploader_id=?');args.append(u['id'])
    if status:where.append('t.status=?');args.append(status)
    sql='''SELECT t.*,a.name as activity_name,c.name as category_name,us.name as uploader_name,
          (SELECT count(*) FROM correction_requests r WHERE r.transaction_id=t.id AND r.status='PENDING') as correction_pending,
          (SELECT count(*) FROM reinstatement_requests r WHERE r.transaction_id=t.id AND r.status='PENDING') as reinstatement_pending
          FROM transactions t JOIN activities a ON a.id=t.activity_id
          LEFT JOIN categories c ON c.id=t.category_id JOIN users us ON us.id=t.uploader_id
          WHERE '''+' AND '.join(where)+' ORDER BY t.created_at DESC LIMIT 500'
    with connection() as c:return allrows(c,sql,args)

@app.get('/api/transactions/{txid}/history')
def history(request:Request,txid:str):
    u=auth(request)
    with connection() as c:
        t=one(c,'SELECT uploader_id,document_id FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        return {'audit':allrows(c,"SELECT action,details,created_at FROM audit_logs WHERE target_type='transaction' AND target_id=? ORDER BY created_at DESC",(txid,)),
                'versions':allrows(c,'SELECT version_number,filename,created_at FROM document_versions WHERE document_id=? ORDER BY version_number',(t['document_id'],))}

@app.get('/api/receipts/{document_id}')
def receipt(request:Request,document_id:str,version:int|None=None):
    u=auth(request)
    with tx() as c:
        d=one(c,'SELECT * FROM documents WHERE id=?',(document_id,))
        if not d:raise HTTPException(404,'Dokumen tidak ditemukan')
        own_or_admin(u,d['owner_id'])
        v=one(c,'SELECT * FROM document_versions WHERE document_id=? AND version_number=?',(document_id,version)) if version else one(c,'SELECT * FROM document_versions WHERE id=?',(d['active_version_id'],))
        if not v:raise HTTPException(404,'Versi dokumen tidak ditemukan')
        audit(c,u['id'],'DOCUMENT_OPENED','document',document_id,{'version':v['version_number']})
    headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    try:
        if v['storage_path'].startswith(PREFIX):
            if not CLOUD_STORAGE:
                raise StorageError('Cloud storage is not configured')
            raw = CLOUD_STORAGE.read(v['storage_path'], v['sha256'], v['file_size'])
            headers['Content-Disposition']="inline; filename*=UTF-8''"+quote(v['filename'],safe='')
            return Response(raw,media_type=v['media_type'],headers=headers)
        if HOSTED_PREVIEW:
            raise StorageError('Legacy local receipt is available only on original laptop')
        path=legacy_local_path(v['storage_path'],DATA)
    except StorageError:
        raise HTTPException(503,'Kuitansi tidak tersedia atau gagal verifikasi') from None
    return FileResponse(path,media_type=v['media_type'],filename=v['filename'],content_disposition_type='inline',headers=headers)

class Decision(BaseModel):decision:str;reason:str|None=None;revision:int|None=None
@app.get('/api/admin/review-queue')
def review_queue(request:Request):
    u=auth(request);admin_only(u)
    with connection() as c:
        return {
         'transactions':allrows(c,"SELECT t.*,us.name uploader_name FROM transactions t JOIN users us ON us.id=t.uploader_id WHERE status='PENDING_REVIEW' ORDER BY submitted_at LIMIT 200"),
         'corrections':allrows(c,"SELECT r.*,t.description FROM correction_requests r JOIN transactions t ON t.id=r.transaction_id WHERE r.status='PENDING' ORDER BY r.created_at LIMIT 200"),
         'reinstatements':allrows(c,"SELECT r.*,t.description FROM reinstatement_requests r JOIN transactions t ON t.id=r.transaction_id WHERE r.status='PENDING' ORDER BY r.created_at LIMIT 200")}

@app.post('/api/admin/transactions/{txid}/decision')
def decide_tx(request:Request,txid:str,data:Decision):
    u=auth(request,True);admin_only(u)
    if data.decision not in ('APPROVE','REJECT'):raise HTTPException(422,'Keputusan tidak dikenal')
    if data.decision=='REJECT' and not (data.reason or '').strip():raise HTTPException(422,'Alasan penolakan wajib')
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        if t['status']!='PENDING_REVIEW':raise HTTPException(409,'Transaksi sudah diputuskan')
        if data.revision is not None and t['revision']!=data.revision:raise HTTPException(409,'Data sudah berubah, muat ulang')
        if data.decision=='APPROVE' and json.loads(t['risk_reasons']) and not (data.reason or '').strip():
            raise HTTPException(422,'Persetujuan berisiko wajib alasan')
        new='APPROVED' if data.decision=='APPROVE' else 'REJECTED'
        c.execute('UPDATE transactions SET status=?,approved_by=?,approved_at=?,rejected_reason=?,revision=revision+1,updated_at=? WHERE id=?',
                  (new,u['id'] if new=='APPROVED' else None,now() if new=='APPROVED' else None,data.reason if new=='REJECTED' else None,now(),txid))
        audit(c,u['id'],'ADMIN_'+new,'transaction',txid,{'reason':data.reason})
        notify(c,t['uploader_id'],'DECISION',f'Transaksi {t["description"]}: {new}')
    return {'status':new}

class CorrectionIn(BaseModel):reason:str=Field(min_length=5);proposed:dict
CORR_KEYS={'transaction_date','amount','description','category_id','activity_id','vendor','payment_method','invoice_number','notes'}
@app.post('/api/transactions/{txid}/corrections')
def correction(request:Request,txid:str,data:CorrectionIn):
    u=auth(request,True)
    if not data.proposed or set(data.proposed)-CORR_KEYS:raise HTTPException(422,'Kolom koreksi tidak valid')
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        if t['status'] not in ('APPROVED','PENDING_REVIEW','REJECTED'):
            raise HTTPException(409,'Koreksi hanya untuk transaksi yang sudah disubmit dan tidak reversed')
        if one(c,"SELECT id FROM correction_requests WHERE transaction_id=? AND status='PENDING'",(txid,)):
            raise HTTPException(409,'Masih ada permintaan koreksi pending')
        proposed=data.proposed.copy()
        if 'amount' in proposed:
            try:proposed['amount_cents']=amount_to_cents(proposed.pop('amount'))
            except ValueError as e:raise HTTPException(422,str(e))
        if 'category_id' in proposed and proposed['category_id'] and not one(c,'SELECT id FROM categories WHERE id=?',(proposed['category_id'],)):
            raise HTTPException(422,'Kategori tidak dikenal')
        if 'activity_id' in proposed and not one(c,'SELECT id FROM activities WHERE id=?',(proposed['activity_id'],)):
            raise HTTPException(422,'Aktivitas tidak dikenal')
        key=uid()
        c.execute('INSERT INTO correction_requests(id,transaction_id,requester_id,reason,proposed_json,created_at) VALUES (?,?,?,?,?,?)',
                  (key,txid,u['id'],data.reason.strip(),js(proposed),now()))
        audit(c,u['id'],'CORRECTION_REQUESTED','transaction',txid,{'request_id':key,'fields':list(proposed)})
        for a in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1"):
            notify(c,a['id'],'CORRECTION',f'Permintaan koreksi: {t["description"]}',f'correction-{key}-{a["id"]}')
    return {'id':key,'status':'PENDING'}

@app.post('/api/corrections/{request_id}/replacement')
async def correction_replacement(request:Request,request_id:str,file:UploadFile=File(...)):
    u=auth(request,True);raw=await file.read(MAX_FILE+1);mime,ext=validate_bytes(file.filename or '',raw)
    with tx() as c:
        r=one(c,'SELECT * FROM correction_requests WHERE id=?',(request_id,))
        if not r:raise HTTPException(404,'Permintaan tidak ditemukan')
        t=one(c,'SELECT * FROM transactions WHERE id=?',(r['transaction_id'],))
        own_or_admin(u,t['uploader_id'])
        if r['status']!='PENDING' or r['replacement_version_id']:raise HTTPException(409,'Tidak bisa mengganti lampiran request ini')
        ver=uid();path=store_file(raw,ext)
        try:
            num=one(c,'SELECT coalesce(max(version_number),0)+1 as n FROM document_versions WHERE document_id=?',(t['document_id'],))['n']
            c.execute('INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?)',
                      (ver,t['document_id'],num,(file.filename or 'replacement')[:240],mime,hashlib.sha256(raw).hexdigest(),path,len(raw),now()))
            c.execute('UPDATE correction_requests SET replacement_version_id=? WHERE id=?',(ver,request_id))
            c.execute('INSERT INTO extraction_runs(id,document_id,status,provider,raw_json,created_at) VALUES (?,?,?,?,?,?)',
                      (uid(),t['document_id'],'MANUAL_REQUIRED','NO_OCR_CONFIGURED',js({'replacement_version_id':ver}),now()))
            audit(c,u['id'],'REPLACEMENT_PROPOSED','transaction',t['id'],{'version':num,'request_id':request_id})
        except Exception:
            if not path.startswith(PREFIX):
                try:Path(path).unlink(missing_ok=True)
                except OSError:pass
            raise
    return {'version':num,'status':'PENDING_ADMIN_APPROVAL'}

@app.post('/api/admin/corrections/{request_id}/decision')
def decide_correction(request:Request,request_id:str,data:Decision):
    u=auth(request,True);admin_only(u)
    if data.decision not in ('APPROVE','REJECT') or not (data.reason or '').strip():
        raise HTTPException(422,'Keputusan dan alasan wajib diisi')
    with tx() as c:
        r=one(c,'SELECT * FROM correction_requests WHERE id=?',(request_id,))
        if not r:raise HTTPException(404,'Permintaan tidak ditemukan')
        if r['status']!='PENDING':raise HTTPException(409,'Permintaan sudah diputuskan')
        t=one(c,'SELECT * FROM transactions WHERE id=?',(r['transaction_id'],))
        if t['status']=='REVERSED':raise HTTPException(409,'Transaksi reversed tidak boleh dikoreksi lewat request ini')
        if data.decision=='APPROVE':
            p=json.loads(r['proposed_json'])
            fields=[k for k in p if k in {'transaction_date','amount_cents','description','category_id','activity_id','vendor','payment_method','invoice_number','notes'}]
            if fields:
                vals=[p[k] for k in fields]
                c.execute('UPDATE transactions SET '+','.join(f'{k}=?' for k in fields)+',revision=revision+1,updated_at=? WHERE id=?',vals+[now(),t['id']])
            if r['replacement_version_id']:
                c.execute('UPDATE documents SET active_version_id=? WHERE id=?',(r['replacement_version_id'],t['document_id']))
            if t['status']=='REJECTED':
                c.execute("UPDATE transactions SET status='PENDING_REVIEW',rejected_reason=NULL,revision=revision+1,updated_at=? WHERE id=?",(now(),t['id']))
                for adm in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1"):
                    notify(c,adm['id'],'REVIEW',f'Transaksi terkoreksi menunggu keputusan: {t["description"]}',f'corrected-review-{t["id"]}-{adm["id"]}')
            audit(c,u['id'],'CORRECTION_APPROVED','transaction',t['id'],{'request_id':request_id,'fields':fields,'document_changed':bool(r['replacement_version_id']),'reopened_review':t['status']=='REJECTED'})
        else:audit(c,u['id'],'CORRECTION_REJECTED','transaction',t['id'],{'request_id':request_id,'reason':data.reason})
        c.execute('UPDATE correction_requests SET status=?,reviewer_id=?,decision_reason=?,decided_at=? WHERE id=?',
                  ('APPROVED' if data.decision=='APPROVE' else 'REJECTED',u['id'],data.reason,now(),request_id))
        notify(c,r['requester_id'],'CORRECTION',f'Permintaan koreksi {data.decision.lower()}')
    return {'status':data.decision}

class Reason(BaseModel):reason:str=Field(min_length=5)
@app.post('/api/admin/transactions/{txid}/reverse')
def reverse(request:Request,txid:str,data:Reason):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        if t['status']!='APPROVED':raise HTTPException(409,'Hanya transaksi APPROVED yang dapat di-reverse')
        c.execute("UPDATE transactions SET status='REVERSED',revision=revision+1,updated_at=? WHERE id=?",(now(),txid))
        # Pending corrections cannot be applied to reversed transactions.
        for r in allrows(c,"SELECT id,requester_id FROM correction_requests WHERE transaction_id=? AND status='PENDING'",(txid,)):
            c.execute("UPDATE correction_requests SET status='REJECTED',decision_reason='Dibatalkan oleh reversal',reviewer_id=?,decided_at=? WHERE id=?",(u['id'],now(),r['id']))
            notify(c,r['requester_id'],'CORRECTION','Permintaan koreksi ditutup karena reversal')
        audit(c,u['id'],'TRANSACTION_REVERSED','transaction',txid,{'reason':data.reason})
        notify(c,t['uploader_id'],'REVERSAL',f'Transaksi dibatalkan: {t["description"]}')
    return {'status':'REVERSED'}

@app.post('/api/transactions/{txid}/reinstatement')
def reinstatement(request:Request,txid:str,data:Reason):
    u=auth(request,True)
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Transaksi tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        if t['status']!='REVERSED':raise HTTPException(409,'Reinstatement hanya untuk REVERSED')
        if one(c,"SELECT id FROM reinstatement_requests WHERE transaction_id=? AND status='PENDING'",(txid,)):
            raise HTTPException(409,'Permintaan reinstatement sudah pending')
        cal=one(c,'SELECT * FROM calendar_versions ORDER BY version DESC LIMIT 1')
        hours=json.loads(cal['hours_json']); holidays=json.loads(cal['holidays_json'])
        due=business_due(now(),holidays=holidays,hours=hours)
        verified=bool(cal['verified']);key=uid()
        eligible=allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1 ORDER BY created_at,name")
        assigned=eligible[0]['id'] if eligible else None
        c.execute('''INSERT INTO reinstatement_requests(id,transaction_id,requester_id,reason,sla_status,calendar_quality,due_at,provisional_due_at,next_reminder_at,calendar_version,assigned_reviewer_id,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (key,txid,u['id'],data.reason,'FINAL' if verified else 'PROVISIONAL',
                   'VERIFIED' if verified else 'CALENDAR_UNVERIFIED',due if verified else None,
                   None if verified else due,due if not verified else None,cal['version'],assigned,now()))
        audit(c,u['id'],'REINSTATEMENT_REQUESTED','transaction',txid,{'request_id':key,'sla_status':'FINAL' if verified else 'PROVISIONAL'})
        for a in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1 AND id<>?",(u['id'],)):
            notify(c,a['id'],'REINSTATEMENT',f'Reinstatement perlu review: {t["description"]}',f'reinstate-{key}-{a["id"]}')
    return {'id':key,'status':'PENDING','sla_status':'FINAL' if verified else 'PROVISIONAL'}

@app.post('/api/admin/reinstatements/{request_id}/decision')
def decide_reinstatement(request:Request,request_id:str,data:Decision):
    u=auth(request,True);admin_only(u)
    if data.decision not in ('APPROVE','REJECT') or not (data.reason or '').strip():
        raise HTTPException(422,'Keputusan dan alasan wajib')
    with tx() as c:
        r=one(c,'SELECT * FROM reinstatement_requests WHERE id=?',(request_id,))
        if not r:raise HTTPException(404,'Permintaan tidak ditemukan')
        if r['status']!='PENDING':raise HTTPException(409,'Permintaan sudah diputuskan')
        # Single integrated admin account mode: self-review allowed
        if r['assigned_reviewer_id'] is None or r['assigned_reviewer_id']!=u['id']:
            raise HTTPException(403,'Hanya reviewer admin yang ditugaskan boleh memutuskan request ini')
        t=one(c,'SELECT * FROM transactions WHERE id=?',(r['transaction_id'],))
        if t['status']!='REVERSED':raise HTTPException(409,'Transaksi sudah berubah')
        if data.decision=='APPROVE':
            c.execute("UPDATE transactions SET status='APPROVED',revision=revision+1,updated_at=? WHERE id=?",(now(),t['id']))
        c.execute('UPDATE reinstatement_requests SET status=?,reviewer_id=?,decision_reason=?,decided_at=? WHERE id=?',
                  ('APPROVED' if data.decision=='APPROVE' else 'REJECTED',u['id'],data.reason,now(),request_id))
        audit(c,u['id'],'REINSTATEMENT_'+data.decision,'transaction',t['id'],{'request_id':request_id,'reason':data.reason})
        notify(c,r['requester_id'],'REINSTATEMENT',f'Permintaan reinstatement {data.decision.lower()}')
    return {'request_status':data.decision,'transaction_status':'APPROVED' if data.decision=='APPROVE' else 'REVERSED'}

class BudgetIn(BaseModel):
    income_cents: int = Field(ge=0)

@app.post('/api/dashboard/income')
def set_dashboard_income(request:Request, data:BudgetIn):
    u=auth(request,True)
    with tx() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS app_settings(
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        )''')
        c.execute('''INSERT INTO app_settings(key,value,updated_at) VALUES ('total_income_cents',?,?)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at''',
                  (str(data.income_cents), now()))
        audit(c,u['id'],'INCOME_UPDATED','settings','total_income_cents',{'income_cents':data.income_cents})
    return {'income_cents': data.income_cents}

@app.get('/api/dashboard')
def dashboard(request:Request):
    u=auth(request)
    sql="FROM transactions WHERE status='APPROVED' AND deleted_at IS NULL"
    params=[]
    if u['role']!='admin':sql+=' AND uploader_id=?';params=[u['id']]
    with connection() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS app_settings(
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        )''')
        inc_row = one(c, "SELECT value FROM app_settings WHERE key='total_income_cents'")
        income_cents = int(inc_row['value']) if inc_row else 0
        r=one(c,'SELECT count(*) as receipt_count,coalesce(sum(amount_cents),0) as total_cents '+sql,params)
        pending=one(c,"SELECT count(*) as n FROM transactions WHERE status='PENDING_REVIEW'"+(" AND uploader_id=?" if u['role']!='admin' else ''),params)['n']
        base="SELECT coalesce(c.name,'Belum dikategorikan') category,sum(t.amount_cents) total_cents FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.status='APPROVED' AND t.deleted_at IS NULL"
        if u['role']!='admin':base+=' AND t.uploader_id=?'
        base+=' GROUP BY c.name ORDER BY total_cents DESC'
        cats=allrows(c,base,params)
        m_sql="SELECT substr(transaction_date,6,2) as mm, coalesce(sum(amount_cents),0) as total_cents FROM transactions WHERE status='APPROVED' AND deleted_at IS NULL AND transaction_date IS NOT NULL AND length(transaction_date)>=7"
        if u['role']!='admin':m_sql+=' AND uploader_id=?'
        m_sql+=' GROUP BY mm'
        m_rows=allrows(c,m_sql,params)
        monthly = {f"{i:02d}": 0 for i in range(1, 13)}
        for mr in m_rows:
            if mr['mm'] in monthly:
                monthly[mr['mm']] = mr['total_cents']
    return {
        **r,
        'income_cents': income_cents,
        'net_cents': income_cents - r['total_cents'],
        'pending_review': pending,
        'categories': cats,
        'monthly_expense': [monthly[f"{i:02d}"] for i in range(1, 13)]
    }

def safe_excel(v):
    if v is None:return ''
    s=str(v)
    if s.lstrip()[:1] in ('=','+','-','@','\t','\r','\n'):return "'"+s
    return s

@app.get('/api/reports/export')
def export_report(request:Request,activity_id:str|None=None):
    u=auth(request)
    sql="""SELECT t.*,a.name activity_name,c.name category_name,us.name uploader_name
           FROM transactions t JOIN activities a ON a.id=t.activity_id
           LEFT JOIN categories c ON c.id=t.category_id JOIN users us ON us.id=t.uploader_id
           WHERE t.status='APPROVED' AND t.deleted_at IS NULL"""
    args=[]
    if u['role']!='admin':sql+=' AND t.uploader_id=?';args.append(u['id'])
    if activity_id:sql+=' AND t.activity_id=?';args.append(activity_id)
    sql+=' ORDER BY t.transaction_date,t.id'
    with connection() as c:rows=allrows(c,sql,args)
    wb=Workbook();ws=wb.active;ws.title='Transactions'
    heads=['Date','Amount (IDR)','Description','Vendor','Category','Payment Method','Invoice Number','Uploader','Receipt Link','Notes','Transaction ID','Activity']
    ws.append(heads)
    base=PUBLIC_ORIGIN or 'http://127.0.0.1:8000'
    for r in rows:
        ws.append([safe_excel(r['transaction_date']),r['amount_cents']/100,safe_excel(r['description']),safe_excel(r['vendor']),
                   safe_excel(r['category_name']),safe_excel(r['payment_method']),safe_excel(r['invoice_number']),
                   safe_excel(r['uploader_name']),base+'/api/receipts/'+r['document_id'],safe_excel(r['notes']),r['id'],safe_excel(r['activity_name'])])
    for cell in ws[1]:cell.fill=PatternFill('solid',fgColor='171717');cell.font=Font(color='FFFFFF',bold=True)
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col,w in {'A':15,'B':18,'C':42,'D':22,'E':24,'F':20,'G':22,'H':24,'I':55,'J':28,'K':42,'L':30}.items():ws.column_dimensions[col].width=w
    for cell in ws['B'][1:]:cell.number_format='#,##0.00'
    sums=wb.create_sheet('Summary');sums.append(['Metric','Value']);sums.append(['Approved receipts',len(rows)]);sums.append(['Approved total (IDR)',sum(x['amount_cents'] for x in rows)/100])
    info=wb.create_sheet('Report Info');info.append(['Company','PT Mulia Hakimaco Sejahtera']);info.append(['Snapshot UTC',now()]);info.append(['Scope','all admin data' if u['role']=='admin' else 'own approved data']);info.append(['Activity filter',activity_id or 'ALL']);info.append(['Rule','Only current APPROVED; historic exports immutable'])
    key=uid()
    if HOSTED_PREVIEW:
        info.append(['Preview','Download-only snapshot; no server archive in preview'])
        stream=BytesIO();wb.save(stream);payload=stream.getvalue()
        location='download-only:sha256:'+hashlib.sha256(payload).hexdigest()
    else:
        path=DATA/'exports';path.mkdir(exist_ok=True);fname=path/(key+'.xlsx');wb.save(fname)
        location=str(fname)
    with tx() as c:
        c.execute('INSERT INTO export_logs VALUES (?,?,?,?,?,?)',(key,u['id'],'all' if u['role']=='admin' else 'own',js({'activity_id':activity_id}),location,now()))
        audit(c,u['id'],'REPORT_EXPORTED','export',key,{'count':len(rows),'approved_total_cents':sum(x['amount_cents'] for x in rows)})
    if HOSTED_PREVIEW:
        return Response(payload,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="MHS_Approved_Expenses.xlsx"','Cache-Control':'private, no-store'})
    return FileResponse(fname,filename='MHS_Approved_Expenses.xlsx',media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Cache-Control':'private, no-store'})

@app.get('/api/notifications')
def notifications(request:Request):
    u=auth(request)
    with connection() as c:return allrows(c,'SELECT id,type,message,created_at,read_at FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(u['id'],))

@app.get('/api/admin/audit')
def audits(request:Request):
    u=auth(request);admin_only(u)
    with connection() as c:return allrows(c,'SELECT a.*,u.name actor_name FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.created_at DESC LIMIT 200')

@app.get('/api/admin/calendar')
def calendar(request:Request):
    u=auth(request);admin_only(u)
    with connection() as c:
        return {'active':one(c,'SELECT * FROM calendar_versions ORDER BY version DESC LIMIT 1'),
                'imports':allrows(c,'SELECT * FROM holiday_import_batches ORDER BY created_at DESC LIMIT 20')}

class CalendarImport(BaseModel):holidays:list[str];source:str=Field(min_length=8)
@app.post('/api/admin/calendar/stage')
def stage_calendar(request:Request,data:CalendarImport):
    u=auth(request,True);admin_only(u)
    from zoneinfo import ZoneInfo
    current_year=datetime.now(ZoneInfo('Asia/Jakarta')).year
    yrs={current_year,current_year+1}
    try:
        if any(datetime.strptime(d,'%Y-%m-%d').year not in yrs for d in data.holidays):raise ValueError()
    except ValueError:raise HTTPException(422,'Tanggal hari libur harus valid dan dalam tahun berjalan / berikutnya')
    key=uid()
    with tx() as c:
        c.execute('INSERT INTO holiday_import_batches VALUES (?,?,?,?,?,?,?,?,?)',
                  (key,'STAGED',min(yrs),max(yrs),js(sorted(set(data.holidays))),data.source,u['id'],now(),None))
        audit(c,u['id'],'HOLIDAY_IMPORT_STAGED','calendar_import',key,{'count':len(data.holidays),'source':data.source})
    return {'id':key,'status':'STAGED','notice':'Periksa tanggal berdasarkan sumber resmi sebelum publish; aplikasi tidak memverifikasi SKB secara otomatis.'}

@app.post('/api/admin/calendar/{import_id}/publish')
def publish_calendar(request:Request,import_id:str):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        b=one(c,'SELECT * FROM holiday_import_batches WHERE id=?',(import_id,))
        if not b:raise HTTPException(404,'Import kalender tidak ditemukan')
        if b['status']!='STAGED':raise HTTPException(409,'Import sudah dipublikasikan')
        old=one(c,'SELECT * FROM calendar_versions ORDER BY version DESC LIMIT 1')
        cid=uid();current=now()
        c.execute('INSERT INTO calendar_versions VALUES (?,?,?,?,?,?,?,?,?)',
                  (cid,old['version']+1,1,old['timezone'],old['hours_json'],b['entries_json'],b['source'],current,current))
        c.execute("UPDATE holiday_import_batches SET status='PUBLISHED',published_at=? WHERE id=?",(now(),import_id))
        # Explicitly finalize pending provisional requests on publication; audit both due values.
        for r in allrows(c,"SELECT * FROM reinstatement_requests WHERE status='PENDING' AND sla_status='PROVISIONAL'"):
            due=business_due(r['created_at'],holidays=json.loads(b['entries_json']),hours=json.loads(old['hours_json']))
            c.execute("UPDATE reinstatement_requests SET sla_status='FINAL',calendar_quality='VERIFIED',due_at=?,provisional_due_at=NULL,next_reminder_at=NULL WHERE id=?",(due,r['id']))
            audit(c,u['id'],'SLA_FINALIZED','reinstatement',r['id'],{'old_provisional_due_at':r['provisional_due_at'],'new_due_at':due})
        audit(c,u['id'],'CALENDAR_PUBLISHED','calendar',cid,{'source':b['source'],'holiday_count':len(json.loads(b['entries_json']))})
    return {'status':'PUBLISHED','calendar_version':old['version']+1}

@app.post('/api/admin/reinstatements/{request_id}/snooze')
def snooze(request:Request,request_id:str,data:Reason):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        r=one(c,'SELECT * FROM reinstatement_requests WHERE id=?',(request_id,))
        if not r:raise HTTPException(404,'Permintaan tidak ditemukan')
        if r['status']!='PENDING' or r['sla_status']!='PROVISIONAL':raise HTTPException(409,'Snooze hanya untuk reminder provisional pending')
        if r['snoozed_at']:raise HTTPException(409,'Snooze satu kali sudah digunakan')
        cal=one(c,'SELECT * FROM calendar_versions ORDER BY version DESC LIMIT 1')
        end=business_due(now(),holidays=json.loads(cal['holidays_json']),hours=json.loads(cal['hours_json']))
        c.execute('UPDATE reinstatement_requests SET snoozed_at=?,snooze_until=?,snooze_reason=?,next_reminder_at=? WHERE id=?',
                  (now(),end,data.reason,end,request_id))
        audit(c,u['id'],'SLA_REMINDER_SNOOZED','reinstatement',request_id,{'reason':data.reason,'until':end})
    return {'snooze_until':end,'sla_unchanged':True}

class Escalation(BaseModel):reason:str=Field(min_length=5)
@app.post('/api/admin/reinstatements/{request_id}/escalate')
def manual_escalate(request:Request,request_id:str,data:Escalation):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        r=one(c,'SELECT * FROM reinstatement_requests WHERE id=?',(request_id,))
        if not r:raise HTTPException(404,'Permintaan tidak ditemukan')
        if r['status']!='PENDING':raise HTTPException(409,'Request sudah diputuskan')
        if r['assignment_stage']=='BACKUP':raise HTTPException(409,'Sudah dieskalasi')
        from .worker import escalate_reinstatement
        result=escalate_reinstatement(c,r,actor=u['id'],reason=data.reason)
        if result=='BLOCKED':raise HTTPException(409,'Tidak ada admin cadangan eligible; permintaan tetap pending')
    return {'assignment_stage':'BACKUP','status':'PENDING'}

@app.delete('/api/transactions/{txid}/draft')
def delete_draft(request:Request,txid:str):
    u=auth(request,True)
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t:raise HTTPException(404,'Draft tidak ditemukan')
        own_or_admin(u,t['uploader_id'])
        if t['status']!='DRAFT' or t['deleted_at']:raise HTTPException(409,'Hanya draft aktif dapat dihapus')
        expiry=(datetime.now(timezone.utc)+timedelta(days=30)).isoformat(timespec='seconds')
        c.execute('UPDATE transactions SET deleted_at=?,purge_at=? WHERE id=?',(now(),expiry,txid))
        audit(c,u['id'],'DRAFT_SOFT_DELETED','transaction',txid,{'purge_at':expiry})
    return {'status':'SOFT_DELETED','purge_at':expiry}

@app.post('/api/admin/transactions/{txid}/restore')
def restore_draft(request:Request,txid:str):
    u=auth(request,True);admin_only(u)
    with tx() as c:
        t=one(c,'SELECT * FROM transactions WHERE id=?',(txid,))
        if not t or t['status']!='DRAFT' or not t['deleted_at']:raise HTTPException(409,'Draft tidak dapat dipulihkan')
        if t['purge_at']<=now():raise HTTPException(409,'Periode pemulihan berakhir')
        c.execute('UPDATE transactions SET deleted_at=NULL,purge_at=NULL WHERE id=?',(txid,))
        audit(c,u['id'],'DRAFT_RESTORED','transaction',txid,{})
    return {'status':'DRAFT'}
