"""Legacy multi-role workflow cases. Run only in an isolated test subprocess."""
import os,io,json
from pathlib import Path
import pytest

# Fail closed before importing application modules or touching a database.
root = Path(os.environ.get("MHS_DATA_DIR", ".")).resolve()
marker = root / ".mhs-workflow-fixture"
if (os.environ.get("MHS_WORKFLOW_TEST_CHILD") != "1"
        or os.environ.get("MHS_MODE") != "demo"
        or os.environ.get("MHS_STORAGE_MODE") != "local"
        or not marker.is_file()):
    pytest.skip("Use tests/test_workflows.py to launch isolated workflow cases", allow_module_level=True)

from fastapi.testclient import TestClient
from backend.app.db import DB_FILE, DATA, connection, tx, uid, now
from backend.app.main import app, APP_MODE, CLOUD_STORAGE
from backend.app.security import password_hash
from openpyxl import load_workbook

@pytest.fixture
def client():
    assert APP_MODE == "demo" and CLOUD_STORAGE is None
    assert DATA.resolve() == root and DB_FILE.resolve() == root / "mhs_expenses.sqlite3"
    # This path is a guarded temporary test directory, never the application directory.
    DB_FILE.unlink(missing_ok=True)
    with TestClient(app) as c:
        # Multi-role accounts are fixtures only, not application seed accounts.
        with tx() as con:
            for name,email,role,pw in (
                ("Backup Fixture","backup@mhs.local","admin","BackupDemo123!"),
                ("Uploader Fixture","uploader@mhs.local","uploader","UploaderDemo123!"),
            ):
                con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                            (uid(),name,email,password_hash(pw),role,1,now()))
        yield c

def login(c,who='uploader'):
    credentials={'admin':('admin@mhs.local','AdminDemo123!'),'backup':('backup@mhs.local','BackupDemo123!'),'uploader':('uploader@mhs.local','UploaderDemo123!')}
    email,pw=credentials[who];r=c.post('/api/auth/login',json={'email':email,'password':pw});assert r.status_code==200,r.text
    return {'X-CSRF-Token':r.json()['csrf']}

def category_activity(c):
    a=c.get('/api/config').json();return a['categories'][0]['id'],a['activities'][0]['id']

def upload(c,headers,activity,content=b'\x89PNG\r\n\x1a\nextraimage',filename='kuitansi.png'):
    b=c.post('/api/batches',json={'activity_id':activity},headers=headers);assert b.status_code==200,b.text
    r=c.post('/api/batches/'+b.json()['id']+'/documents',files={'file':(filename,content,'image/png')},headers=headers)
    assert r.status_code==200,r.text
    return r.json()['transaction_id'],r.json()['document_id'],b.json()['id']

def draft(c,headers,tid,cat,amount='25000',verified=True):
    r=c.patch('/api/transactions/'+tid+'/draft',json={'transaction_date':'2026-11-14','amount':amount,'description':'Biaya konsumsi rapat','category_id':cat,'vendor':'Contoh Vendor'},headers=headers);assert r.status_code==200,r.text
    if verified:
        # Synthetic trusted extraction flag for rule-engine tests ONLY.
        # The real demo frontend cannot set this; manual submissions require admin review.
        with connection() as con:
            con.execute("UPDATE extraction_runs SET status='VERIFIED',provider='TEST_ONLY_TRUSTED_ADAPTER' WHERE document_id=(SELECT document_id FROM transactions WHERE id=?)",(tid,));con.commit()

def submit(c,headers,ids,**kw):
    return c.post('/api/transactions/submit-batch',json={'ids':ids,**kw},headers=headers)

def active(c,id):return next(x for x in c.get('/api/transactions').json() if x['id']==id)

def test_auth_and_server_side_role_boundary(client):
    hu=login(client)
    assert client.get('/api/me').json()['role']=='uploader'
    assert client.get('/api/admin/review-queue').status_code==403
    assert client.get('/api/admin/audit').status_code==403
    assert client.post('/api/admin/activities',headers=hu,json={'name':'Unauthorized'}).status_code==403
    assert client.post('/api/batches',json={'activity_id':'wrong'}).status_code==403 # csrf
    assert client.get('/api/config').status_code==200


def test_upload_manual_fallback_and_autoapproval(client):
    hu=login(client);cat,act=category_activity(client)
    tid,doc,bid=upload(client,hu,act)
    assert active(client,tid)['status']=='DRAFT'
    assert client.get('/api/receipts/'+doc).status_code==200
    draft(client,hu,tid,cat)
    resp=submit(client,hu,[tid]);assert resp.status_code==200,resp.text
    assert resp.json()['items'][0]['status']=='APPROVED'
    assert active(client,tid)['amount_cents']==2500000
    dash=client.get('/api/dashboard').json()
    assert dash['receipt_count']==1 and dash['total_cents']==2500000
    xls=client.get('/api/reports/export');assert xls.status_code==200
    wb=load_workbook(io.BytesIO(xls.content));assert wb.sheetnames==['Transactions','Summary','Report Info']
    assert wb['Transactions']['B2'].value==25000
    with connection() as con:
        assert con.execute('SELECT status FROM upload_batches WHERE id=?',(bid,)).fetchone()[0]=='FULLY_SUBMITTED'


def test_duplicate_manual_review_and_non_admin_cannot_approve(client):
    hu=login(client);cat,act=category_activity(client)
    t1,_,_=upload(client,hu,act);draft(client,hu,t1,cat)
    assert submit(client,hu,[t1]).json()['items'][0]['status']=='APPROVED'
    t2,_,_=upload(client,hu,act);draft(client,hu,t2,cat)
    assert submit(client,hu,[t2]).json()['items'][0]['status']=='PENDING_REVIEW'
    assert client.post('/api/admin/transactions/'+t2+'/decision',headers=hu,json={'decision':'APPROVE','reason':'Verified duplicate'}) .status_code==403
    ha=login(client,'admin')
    assert client.post('/api/admin/transactions/'+t2+'/decision',headers=ha,json={'decision':'APPROVE'}).status_code==422
    r=client.post('/api/admin/transactions/'+t2+'/decision',headers=ha,json={'decision':'APPROVE','reason':'Bukti berbeda setelah ditinjau'})
    assert r.status_code==200,r.text
    assert client.post('/api/admin/transactions/'+t2+'/decision',headers=ha,json={'decision':'REJECT','reason':'again'}).status_code==409


def test_correction_approved_only_then_reversal_excludes_from_report(client):
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat);assert submit(client,hu,[tid]).status_code==200
    original=client.get('/api/reports/export').content
    r=client.post('/api/transactions/'+tid+'/corrections',headers=hu,json={'reason':'Nominal kurang tepat','proposed':{'amount':30000}})
    assert r.status_code==200,r.text
    assert client.get('/api/dashboard').json()['total_cents']==2500000
    ha=login(client,'admin');d=client.post('/api/admin/corrections/'+r.json()['id']+'/decision',headers=ha,json={'decision':'APPROVE','reason':'Nota diverifikasi manual'})
    assert d.status_code==200,d.text
    assert client.get('/api/dashboard').json()['total_cents']==3000000
    # Previously exported bytes retain the earlier amount.
    assert load_workbook(io.BytesIO(original))['Transactions']['B2'].value==25000
    assert client.post('/api/admin/transactions/'+tid+'/reverse',headers=ha,json={'reason':'Pengeluaran tidak sah'}).status_code==200
    assert client.get('/api/dashboard').json()['total_cents']==0
    assert load_workbook(io.BytesIO(client.get('/api/reports/export').content))['Summary']['B2'].value==0


@pytest.mark.parametrize("single_owner", [True, False])
def test_reinstatement_assigned_admin_boundary(client, single_owner):
    # Current application policy (also on main): the assigned admin may review
    # their own request. This is not independent segregation of duties.
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat);submit(client,hu,[tid])
    ha=login(client,'admin')
    if single_owner:
        with tx() as con:
            con.execute("UPDATE users SET active=0 WHERE email='backup@mhs.local'")
    assert client.post('/api/admin/transactions/'+tid+'/reverse',json={'reason':'Verifikasi ulang biaya'},headers=ha).status_code==200
    r=client.post('/api/transactions/'+tid+'/reinstatement',json={'reason':'Sudah ditemukan bukti sah'},headers=ha)
    assert r.status_code==200,r.text
    assert r.json()['sla_status']=='PROVISIONAL'
    rid=r.json()['id']; url='/api/admin/reinstatements/'+rid+'/decision'
    payload={'decision':'APPROVE','reason':'Sudah divalidasi oleh reviewer'}
    actor=client.get('/api/me').json()['id']
    with connection() as con:
        request=con.execute('SELECT requester_id,assigned_reviewer_id FROM reinstatement_requests WHERE id=?',(rid,)).fetchone()
        assert request['requester_id']==actor==request['assigned_reviewer_id']
    hu=login(client,'uploader')
    assert client.post(url,headers=hu,json=payload).status_code==403
    if not single_owner:
        hb=login(client,'backup')
        assert client.post(url,headers=hb,json=payload).status_code==403
        assert client.post(url,headers=hb,json={'decision':'REJECT','reason':'Tidak ditugaskan'}).status_code==403
    ha=login(client,'admin')
    assert active(client,tid)['status']=='REVERSED'
    assert client.post(url,headers=ha,json={'decision':'APPROVE','reason':''}).status_code==422
    ok=client.post(url,headers=ha,json=payload)
    assert ok.status_code==200,ok.text
    assert active(client,tid)['status']=='APPROVED'
    assert client.post(url,headers=ha,json=payload).status_code==409
    with connection() as con:
        row=con.execute('SELECT status,reviewer_id,decision_reason FROM reinstatement_requests WHERE id=?',(rid,)).fetchone()
        assert row['status']=='APPROVED' and row['reviewer_id']==actor and row['decision_reason']==payload['reason']
        log=con.execute("SELECT actor_id FROM audit_logs WHERE action='REINSTATEMENT_APPROVE' AND target_id=?",(tid,)).fetchone()
        assert log and log['actor_id']==actor


def test_provisional_snooze_once_and_calendar_finalization(client):
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat);submit(client,hu,[tid])
    ha=login(client,'admin');client.post('/api/admin/transactions/'+tid+'/reverse',json={'reason':'Dibatalkan sementara'},headers=ha)
    r=client.post('/api/transactions/'+tid+'/reinstatement',json={'reason':'Minta tinjauan kembali'},headers=ha)
    rid=r.json()['id'];assert r.json()['sla_status']=='PROVISIONAL'
    snooze=client.post('/api/admin/reinstatements/'+rid+'/snooze',headers=ha,json={'reason':'Hari libur masih belum diverifikasi'})
    assert snooze.status_code==200,snooze.text
    assert client.post('/api/admin/reinstatements/'+rid+'/snooze',headers=ha,json={'reason':'Coba ulang lagi'}).status_code==409
    import_data=client.post('/api/admin/calendar/stage',headers=ha,json={'holidays':['2026-12-25'],'source':'Pemeriksaan manual SKB pemerintah 2026 dan 2027'})
    assert import_data.status_code==200,import_data.text
    publish=client.post('/api/admin/calendar/'+import_data.json()['id']+'/publish',headers=ha,json={})
    assert publish.status_code==200,publish.text
    queue=client.get('/api/admin/review-queue').json();req=next(x for x in queue['reinstatements'] if x['id']==rid)
    assert req['sla_status']=='FINAL' and req['due_at'] and req['provisional_due_at'] is None
    assert req['status']=='PENDING'


def test_soft_delete_and_admin_restore(client):
    hu=login(client);_,act=category_activity(client);tid,_,_=upload(client,hu,act)
    assert client.delete('/api/transactions/'+tid+'/draft',headers=hu).status_code==200
    assert not any(x['id']==tid for x in client.get('/api/transactions').json())
    ha=login(client,'admin');assert client.post('/api/admin/transactions/'+tid+'/restore',headers=ha,json={}).status_code==200
    assert any(x['id']==tid for x in client.get('/api/transactions').json())


def test_closed_activity_requires_reason_and_manual_review(client):
    ha=login(client,'admin');_,act=category_activity(client)
    assert client.patch('/api/admin/activities/'+act,json={'closure_status':'CLOSED'},headers=ha).status_code==200
    hu=login(client);cat,_=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat)
    assert submit(client,hu,[tid]).status_code==422
    r=submit(client,hu,[tid],late_reason='Bukti baru diterima dari vendor')
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['status']=='PENDING_REVIEW'


def test_unsafe_upload_rejected(client):
    hu=login(client);_,act=category_activity(client)
    b=client.post('/api/batches',json={'activity_id':act},headers=hu).json()['id']
    r=client.post('/api/batches/'+b+'/documents',files={'file':('bad.exe',b'not an image','application/octet-stream')},headers=hu)
    assert r.status_code==422

def test_two_receipts_one_batch_partial_submit_and_duplicate_guard(client):
    hu=login(client);cat,act=category_activity(client)
    b=client.post('/api/batches',headers=hu,json={'activity_id':act}).json()['id']
    r1=client.post('/api/batches/'+b+'/documents',headers=hu,files={'file':('a.png',b'\x89PNG\r\n\x1a\nunique-file-A','image/png')}).json()
    r2=client.post('/api/batches/'+b+'/documents',headers=hu,files={'file':('b.png',b'\x89PNG\r\n\x1a\nunique-file-B','image/png')}).json()
    assert r1['transaction_id']!=r2['transaction_id']
    draft(client,hu,r1['transaction_id'],cat)
    r=submit(client,hu,[r1['transaction_id']]);assert r.status_code==200
    with connection() as c:assert c.execute('SELECT status FROM upload_batches WHERE id=?',(b,)).fetchone()[0]=='PARTIALLY_SUBMITTED'
    assert submit(client,hu,[r1['transaction_id']]).status_code==409
    assert active(client,r2['transaction_id'])['status']=='DRAFT'


def test_uploader_cannot_read_another_uploaders_document(client):
    hu=login(client);cat,act=category_activity(client);tid,doc,_=upload(client,hu,act)
    ha=login(client,'admin');r=client.post('/api/admin/users',headers=ha,json={'name':'Uploader Dua','email':'second@example.com','password':'Abcdefgh1234','role':'uploader'})
    assert r.status_code==200,r.text
    client.post('/api/auth/login',json={'email':'second@example.com','password':'Abcdefgh1234'})
    assert client.get('/api/receipts/'+doc).status_code==403
    assert tid not in [x['id'] for x in client.get('/api/transactions').json()]


def test_replacement_version_active_only_after_approval(client):
    hu=login(client);cat,act=category_activity(client);tid,doc,_=upload(client,hu,act)
    draft(client,hu,tid,cat);submit(client,hu,[tid])
    before=client.get('/api/receipts/'+doc).content
    corr=client.post('/api/transactions/'+tid+'/corrections',headers=hu,json={'reason':'Perbaikan bukti kuitansi','proposed':{'notes':'Versi revisi'}}).json()['id']
    replacement=b'\x89PNG\r\n\x1a\nreplacement-different'
    r=client.post('/api/corrections/'+corr+'/replacement',headers=hu,files={'file':('revised.png',replacement,'image/png')})
    assert r.status_code==200,r.text
    assert client.get('/api/receipts/'+doc).content==before
    ha=login(client,'admin');d=client.post('/api/admin/corrections/'+corr+'/decision',headers=ha,json={'decision':'APPROVE','reason':'Bukti pengganti diverifikasi'})
    assert d.status_code==200,d.text
    assert client.get('/api/receipts/'+doc).content==replacement
    assert client.get('/api/receipts/'+doc+'?version=1').content==before


def test_excel_formula_injection_is_text(client):
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    client.patch('/api/transactions/'+tid+'/draft',headers=hu,json={'transaction_date':'2026-11-14','amount':'12500','description':'=HYPERLINK("https://evil.example")','category_id':cat})
    with connection() as con:
        con.execute("UPDATE extraction_runs SET status='VERIFIED',provider='TEST_ONLY_TRUSTED_ADAPTER' WHERE document_id=(SELECT document_id FROM transactions WHERE id=?)",(tid,));con.commit()
    submit(client,hu,[tid])
    cell=load_workbook(io.BytesIO(client.get('/api/reports/export').content))['Transactions']['C2']
    assert cell.data_type!='f' and cell.value.startswith("'=")


def test_auto_worker_never_escalates_provisional(client):
    from backend.app.worker import run_once
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat);submit(client,hu,[tid])
    ha=login(client,'admin');client.post('/api/admin/transactions/'+tid+'/reverse',headers=ha,json={'reason':'Temporarily reversed'})
    rein=client.post('/api/transactions/'+tid+'/reinstatement',headers=ha,json={'reason':'Valid after verification'}).json()['id']
    with connection() as c:
        c.execute("UPDATE reinstatement_requests SET provisional_due_at='2020-01-01T00:00:00+00:00',next_reminder_at='2020-01-01T00:00:00+00:00' WHERE id=?",(rein,));c.commit()
    output=run_once()
    assert output['escalated']==0 and output['provisional_reminders']==1
    with connection() as c:
        r=c.execute('SELECT status,assignment_stage FROM reinstatement_requests WHERE id=?',(rein,)).fetchone()
        assert r['status']=='PENDING' and r['assignment_stage']=='PRIMARY'


def test_worker_escalates_final_with_distinct_backup(client):
    from backend.app.worker import run_once
    hu=login(client);cat,act=category_activity(client);tid,_,_=upload(client,hu,act)
    draft(client,hu,tid,cat);submit(client,hu,[tid])
    ha=login(client,'admin');client.post('/api/admin/transactions/'+tid+'/reverse',headers=ha,json={'reason':'Need validation'})
    hu=login(client,'uploader')
    resp=client.post('/api/transactions/'+tid+'/reinstatement',headers=hu,json={'reason':'Review again with evidence'})
    assert resp.status_code==200,resp.text
    rein=resp.json()['id']
    with connection() as c:
        c.execute("UPDATE reinstatement_requests SET sla_status='FINAL',due_at='2020-01-01T00:00:00+00:00' WHERE id=?",(rein,));c.commit()
    out=run_once();assert out['escalated']==1,out
    with connection() as c:
        r=c.execute('SELECT status,assignment_stage,assigned_reviewer_id FROM reinstatement_requests WHERE id=?',(rein,)).fetchone()
        assert r['status']=='PENDING' and r['assignment_stage']=='BACKUP'


def test_manual_entry_without_verified_ocr_requires_admin(client):
    hu=login(client);cat,act=category_activity(client);tid,doc,_=upload(client,hu,act)
    draft(client,hu,tid,cat,verified=False)
    result=submit(client,hu,[tid])
    assert result.status_code==200,result.text
    assert result.json()['items'][0]['status']=='PENDING_REVIEW'
    assert 'OCR' in ' '.join(result.json()['items'][0]['risk_reasons'])
    assert client.get('/api/dashboard').json()['total_cents']==0
