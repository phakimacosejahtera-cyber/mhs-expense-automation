import hashlib,hmac,secrets,base64,os
from datetime import datetime,timedelta,timezone
from fastapi import HTTPException,Request
from .db import one,connection,tx,now

def password_hash(password):
    salt=secrets.token_bytes(16)
    derived=hashlib.pbkdf2_hmac('sha256', password.encode(),salt,250_000)
    return 'pbkdf2_sha256$250000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(derived).decode()

def verify_password(password,stored):
    try:
        kind,rounds,salt,derived=stored.split('$')
        if kind!='pbkdf2_sha256':return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt),int(rounds))
        return hmac.compare_digest(actual,base64.b64decode(derived))
    except (ValueError,TypeError): return False

def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()

def create_session(c,user_id):
    token=secrets.token_urlsafe(36); csrf=secrets.token_urlsafe(24)
    expiry=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
    c.execute('INSERT INTO sessions(id_hash,user_id,csrf,expires_at) VALUES (?,?,?,?)',(token_hash(token),user_id,csrf,expiry))
    return token,csrf

def get_auth(req:Request,unsafe=False):
    token=req.cookies.get('mhs_session')
    if not token:raise HTTPException(401,'Silakan login terlebih dahulu')
    with connection() as c:
        s=one(c,'SELECT s.*,u.name,u.email,u.role,u.active FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id_hash=?',(token_hash(token),))
    if not s or not s['active'] or s['expires_at']<=now():raise HTTPException(401,'Sesi berakhir, silakan login')
    if os.getenv('MHS_MODE') == 'owner_test':
        expected = os.getenv('MHS_OWNER_EMAIL', '').strip().lower()
        if not expected or s['email'].lower() != expected or s['role'] != 'admin':
            raise HTTPException(403, 'Akses khusus owner')
    if unsafe and not hmac.compare_digest(req.headers.get('x-csrf-token',''),s['csrf']):
        raise HTTPException(403,'Token keamanan tidak cocok')
    return {'id':s['user_id'],'name':s['name'],'email':s['email'],'role':s['role'],'csrf':s['csrf']}

def admin_only(user):
    if user['role']!='admin':raise HTTPException(403,'Fitur khusus admin')

def own_or_admin(user,owner):
    if user['role']!='admin' and user['id']!=owner:raise HTTPException(403,'Tidak boleh mengakses data pengguna lain')
