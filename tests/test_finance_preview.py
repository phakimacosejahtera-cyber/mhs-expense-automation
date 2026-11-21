"""Local synthetic finance tests. No Supabase connection or real receipts."""
import io
import os
import subprocess
import sys
from pathlib import Path

def test_finance_isolated(tmp_path):
    # Fresh process avoids interfering with other modules' environment/import fixtures.
    script = r'''
from uuid import uuid4
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from io import BytesIO
from backend.app.main import app
with TestClient(app) as c:
    assert c.get('/api/finance/summary').status_code == 401
    r=c.post('/api/auth/login',json={'email':'admin@mhs.local','password':'AdminDemo123!'})
    assert r.status_code==200, r.text
    headers={'X-CSRF-Token':c.get('/api/me').json()['csrf']}
    def post(path,data):
        return c.post(path,json=data,headers=headers)
    def income(day,amount,desc):
        p={'request_id':str(uuid4()),'transaction_date':day,'amount_cents':amount,'description':desc,'sender':'Fixture'}
        r=post('/api/finance/income',p); assert r.status_code==200,r.text
        assert post('/api/finance/income',p).json()['replayed']
        return p['request_id']
    income('2024-01-10',10000000,'Prior year')
    income('2025-01-10',35000000,'=Unsafe formula')
    cancelled=income('2025-02-01',20000000,'Cancelled')
    assert post('/api/finance/income/'+cancelled+'/reverse',{'reason':'Fixture cancellation'}).status_code==200
    assert post('/api/finance/income/'+cancelled+'/reverse',{'reason':'Fixture cancellation'}).status_code==409
    assert post('/api/dashboard/income',{'income_cents':12300}).status_code==200
    cfg=c.get('/api/config').json()
    activity=cfg['activities'][0]['id']; cat=cfg['categories'][0]['id']
    batch=post('/api/batches',{'activity_id':activity}).json()['id']
    def expense(day,amount,status,tag):
        r=c.post('/api/batches/'+batch+'/documents',files={'file':('fixture.pdf',b'%PDF-1.4\n'+tag.encode(),'application/pdf')},headers=headers)
        assert r.status_code==200,r.text
        tid=r.json()['transaction_id']
        r=c.patch('/api/transactions/'+tid+'/draft',json={'transaction_date':day,'amount':amount,'description':tag,'category_id':cat},headers=headers)
        assert r.status_code==200,r.text
        if status=='DRAFT': return
        assert post('/api/transactions/submit-batch',{'ids':[tid]}).status_code==200
        if status=='PENDING_REVIEW': return
        r=post('/api/admin/transactions/'+tid+'/decision',{'decision':'APPROVE','reason':'Fixture validation'})
        assert r.status_code==200,r.text
        if status=='REVERSED':
            r=post('/api/admin/transactions/'+tid+'/reverse',{'reason':'Fixture cancellation'})
            assert r.status_code==200,r.text
    expense('2024-01-12',123,'APPROVED','other year')
    expense('2025-01-15',50000,'APPROVED','included')
    expense('2025-01-18',5000,'DRAFT','draft')
    expense('2025-01-19',10000,'PENDING_REVIEW','pending')
    expense('2025-02-05',9000,'REVERSED','reversed')
    d=c.get('/api/finance/summary?year=2025').json()
    assert d['income_cents']==35000000 and d['total_cents']==5000000 and d['net_cents']==30000000,d
    assert d['monthly_income'][0]==35000000 and d['monthly_expense'][0]==5000000
    assert d['legacy_income_cents']==12300
    feb=c.get('/api/finance/summary?year=2025&month=2').json()
    assert feb['income_cents']==feb['total_cents']==0
    assert c.get('/api/finance/summary?year=2025&month=13').status_code==422
    r=c.get('/api/finance/export?year=2025')
    assert r.status_code==200,r.text
    wb=load_workbook(BytesIO(r.content))
    assert wb.sheetnames==['Ringkasan','Semua Transaksi','Pemasukan','Pengeluaran','Report Info']
    assert wb['Ringkasan']['B3'].value==350000
    assert wb['Ringkasan']['B4'].value==50000
    assert wb['Ringkasan']['B5'].value==300000
    assert wb['Pemasukan']['B2'].data_type!='f'
    assert wb['Pengeluaran']['I2'].hyperlink
    assert 'MHS_Pemasukan' in wb['Pemasukan'].tables
    assert 'MHS_Pengeluaran' in wb['Pengeluaran'].tables
    assert 'MHS_Transaksi' in wb['Semua Transaksi'].tables
    assert 'SUMIFS(' in wb['Ringkasan']['B13'].value
    assert 'SUMIFS(' in wb['Ringkasan']['C13'].value
    assert 'SUBTOTAL(109,' in wb['Pemasukan']['C5'].value
    assert wb['Ringkasan']['B27'].value=='=ROUND(B25-B3,2)'
    empty=c.get('/api/finance/export?year=2025&month=2')
    assert empty.status_code==200,empty.text
    empty_wb=load_workbook(BytesIO(empty.content))
    assert empty_wb['Ringkasan']['B3'].value==0
    assert empty_wb['Pemasukan'].tables['MHS_Pemasukan'].ref=='A1:E2'
    assert empty_wb['Ringkasan']['A13'].value=='Februari'
    overall=c.get('/api/finance/summary?year=0').json()
    assert overall['income_cents']==45000000 and overall['total_cents']==5012300,overall
    assert overall['net_cents']==39987700
    assert {2024,2025}.issubset(set(overall['available_years']))
    assert [x['year'] for x in overall['annual']]==[2024,2025]
    assert c.get('/api/finance/summary?year=0&month=1').status_code==422
    all_report=c.get('/api/finance/export?year=0')
    assert all_report.status_code==200,all_report.text
    all_wb=load_workbook(BytesIO(all_report.content))
    assert all_wb['Ringkasan']['B2'].value=='Semua Tahun'
    assert all_wb['Ringkasan']['B3'].value==450000
    assert all_wb['Ringkasan']['B4'].value==50123
    assert all_wb['Ringkasan']['A13'].value==2024
    assert all_wb['Ringkasan']['A14'].value==2025
    assert 'DATE(2024,1,1)' in all_wb['Ringkasan']['B13'].value


    assert post('/api/admin/users',{'name':'Fixture Uploader','email':'fixture@example.invalid','password':'FixturePassword123','role':'uploader'}).status_code==200
    with TestClient(app) as other:
        assert other.post('/api/auth/login',json={'email':'fixture@example.invalid','password':'FixturePassword123'}).status_code==200
        h={'X-CSRF-Token':other.get('/api/me').json()['csrf']}
        assert other.get('/api/finance/summary').status_code==403
        assert other.get('/api/finance/export').status_code==403
        assert other.post('/api/dashboard/income',json={'income_cents':1},headers=h).status_code==403
'''
    env={k:v for k,v in os.environ.items() if not k.startswith('MHS_') and k not in ('RENDER','RENDER_SERVICE_ID')}
    env.update(MHS_MODE='demo',MHS_STORAGE_MODE='local',MHS_DATA_DIR=str(tmp_path))
    result=subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
