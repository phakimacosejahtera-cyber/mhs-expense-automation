"""Focused tests for new Tesseract-client ingestion. Run in isolated temp DB."""
import os,tempfile
os.environ['MHS_DATA_DIR']=tempfile.mkdtemp(prefix='mhs-client-ocr-')
os.environ['MHS_MODE']='demo'
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import DB_FILE,connection

def _login(c,email='admin@mhs.local',password='AdminDemo123!'):
    resp=c.post('/api/auth/login',json={'email':email,'password':password})
    assert resp.status_code==200,resp.text
    return {'X-CSRF-Token':resp.json()['csrf']}

def _upload(c,headers):
    activity=c.get('/api/config').json()['activities'][0]['id']
    batch=c.post('/api/batches',json={'activity_id':activity},headers=headers)
    assert batch.status_code==200,batch.text
    doc=c.post(f"/api/batches/{batch.json()['id']}/documents",
        files={'file':('dummy.png',b'\x89PNG\r\n\x1a\nTEST_IMAGE_ONLY','image/png')},headers=headers)
    assert doc.status_code==200,doc.text
    return doc.json()['transaction_id'],doc.json()['document_id']

def test_client_ocr_is_unverified_and_never_autoapproved():
    DB_FILE.unlink(missing_ok=True)
    with TestClient(app) as c:
        admin=_login(c)
        tid,doc=_upload(c,admin)
        body={'text':'Rp 12.000\nTanggal 18/11/2026','confidence':90,
              'suggestions':{'amounts':[{'value':12000,'label':'Rp 12.000','priority':1,'line':1}],
                             'dates':['2026-11-18']}}
        resp=c.post(f'/api/transactions/{tid}/ocr-result',json=body,headers=admin)
        assert resp.status_code==200,resp.text
        assert resp.json()['verified'] is False
        get=c.get(f'/api/transactions/{tid}/ocr-result')
        assert get.status_code==200 and get.json()['text']==body['text']
        with connection() as db:
            row=db.execute('SELECT status,provider FROM extraction_runs WHERE document_id=? ORDER BY rowid DESC LIMIT 1',(doc,)).fetchone()
            assert tuple(row)==('EXTRACTED','TESSERACT_JS_CLIENT')
        assert c.get('/api/transactions').json()[0]['amount_cents'] is None
        cat=c.get('/api/config').json()['categories'][0]['id']
        edit=c.patch(f'/api/transactions/{tid}/draft',headers=admin,json={
            'transaction_date':'2026-11-18','amount':12000,'category_id':cat,'description':'Biaya konsumsi rapat'})
        assert edit.status_code==200,edit.text
        submission=c.post('/api/transactions/submit-batch',headers=admin,json={'ids':[tid]})
        assert submission.status_code==200,submission.text
        assert submission.json()['items'][0]['status']=='PENDING_REVIEW'
        denied=c.post(f'/api/transactions/{tid}/ocr-result',json=body,headers=admin)
        assert denied.status_code==409

def test_client_ocr_permission_and_input_validation():
    DB_FILE.unlink(missing_ok=True)
    with TestClient(app) as c:
        admin=_login(c)
        tid,_=_upload(c,admin)
        assert c.post(f'/api/transactions/{tid}/ocr-result',json={'text':'abc'}).status_code==403
        too_long=c.post(f'/api/transactions/{tid}/ocr-result',headers=admin,json={'text':'x'*16001})
        assert too_long.status_code==422
        bad_conf=c.post(f'/api/transactions/{tid}/ocr-result',headers=admin,json={'text':'a','confidence':101})
        assert bad_conf.status_code==422
