from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
TZ=ZoneInfo('Asia/Jakarta')
WORKING_MINUTES=24*60

def amount_to_cents(value):
    try:
        v=Decimal(str(value))
        if not v.is_finite() or v<0 or v>Decimal('999999999999'):raise ValueError()
        return int((v*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,TypeError):raise ValueError('Nominal tidak valid')

def business_due(start_iso,minutes=WORKING_MINUTES,holidays=None,hours=None):
    """MVP calendar: Mon-Fri, configurable intervals; excluded holiday dates.
    Returns ISO UTC. Cross-midnight intervals unsupported as fixed by baseline.
    """
    holidays=set(holidays or [])
    hours=hours or {'0':[['09:00','17:00']],'1':[['09:00','17:00']],'2':[['09:00','17:00']],
                    '3':[['09:00','17:00']],'4':[['09:00','17:00']]}
    cursor=datetime.fromisoformat(start_iso).astimezone(TZ)
    remaining=minutes
    for _ in range(1000):
        day=cursor.date().isoformat()
        intervals=[] if day in holidays else hours.get(str(cursor.weekday()),[])
        for a,b in intervals:
            h1,m1=map(int,a.split(':'));h2,m2=map(int,b.split(':'))
            s=datetime.combine(cursor.date(),time(h1,m1),tzinfo=TZ)
            e=datetime.combine(cursor.date(),time(h2,m2),tzinfo=TZ)
            if s>=e:raise ValueError('Interval kerja harus berakhir di hari yang sama')
            if cursor>=e:continue
            beginning=max(s,cursor)
            available=int((e-beginning).total_seconds()//60)
            if remaining<=available:
                return (beginning+timedelta(minutes=remaining)).astimezone(ZoneInfo('UTC')).isoformat(timespec='seconds')
            remaining-=available
        cursor=datetime.combine(cursor.date()+timedelta(days=1),time(0,0),tzinfo=TZ)
    raise ValueError('Kalender tidak menyediakan jam kerja yang cukup')

def risk_reasons(tx,duplicate=False,closed=False):
    risks=[]
    for key,label in [('transaction_date','tanggal'),('amount_cents','nominal'),('description','keterangan'),('category_id','kategori')]:
        if tx.get(key) in (None,''):risks.append(f'Data {label} belum lengkap')
    if duplicate:risks.append('Kemungkinan kuitansi duplikat')
    if closed:risks.append('Pengumpulan setelah periode ditutup')
    date_str=tx.get('transaction_date')
    if date_str:
        try:
            day=datetime.strptime(date_str,'%Y-%m-%d').date()
            if day>datetime.now(TZ).date():risks.append('Tanggal kuitansi di masa depan')
        except ValueError:risks.append('Tanggal kuitansi tidak valid')
    if tx.get('amount_cents') == 0:risks.append('Nominal nol perlu verifikasi')
    if tx.get('mixed_receipt'):risks.append('Kuitansi berisi beberapa kategori')
    return risks
