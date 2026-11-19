"""Idempotent local background worker. Run in a separate process: python -m backend.app.worker.
Jobs are intentionally simple in V0.1. Provisional SLA never enables automatic escalation.
"""
import json, time, sys
from datetime import datetime,timezone
from pathlib import Path
from .db import tx,now,uid,audit,notify,allrows,one
from .rules import business_due


def escalate_reinstatement(c,r,actor=None,reason='SLA FINAL melebihi 24 jam kerja'):
    """Shared escalation path for manual actions and automatic worker.
    Only assignments change, never request/financial status.
    """
    if r['status']!='PENDING' or r['assignment_stage']=='BACKUP':return 'SKIP'
    requester=one(c,'SELECT role FROM users WHERE id=?',(r['requester_id'],))
    excluded=r['requester_id'] if requester['role']=='admin' else ''
    backups=allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1 AND id<>? AND id<>? ORDER BY name",(excluded,r['assigned_reviewer_id'] or ''))
    if not backups:
        if not one(c,"SELECT id FROM notifications WHERE dedup_key=?",('no-backup-'+r['id'],)):
            for adm in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1"):
                notify(c,adm['id'],'BLOCKED',f'Tidak ada reviewer backup eligible untuk reinstatement {r["id"]}',f'blocked-backup-{r["id"]}-{adm["id"]}')
        return 'BLOCKED'
    c.execute("UPDATE reinstatement_requests SET assignment_stage='BACKUP',assigned_reviewer_id=? WHERE id=?",(backups[0]['id'],r['id']))
    audit(c,actor,'REINSTATEMENT_ESCALATED','reinstatement',r['id'],{'reason':reason,'assigned_to':backups[0]['id']})
    notify(c,backups[0]['id'],'ESCALATION',f'Reinstatement {r["id"]} dialihkan untuk direview',f'escalated-{r["id"]}')
    return 'ESCALATED'


def run_once():
    stats={'escalated':0,'blocked':0,'provisional_reminders':0,'purged_drafts':0}
    paths=[]
    with tx() as c:
        current=now()
        cal=one(c,'SELECT * FROM calendar_versions ORDER BY version DESC LIMIT 1')
        for r in allrows(c,"SELECT * FROM reinstatement_requests WHERE status='PENDING' AND sla_status='FINAL' AND assignment_stage='PRIMARY' AND due_at <= ?",(current,)):
            result=escalate_reinstatement(c,r)
            if result=='ESCALATED':stats['escalated']+=1
            elif result=='BLOCKED':stats['blocked']+=1
        # Alerts are aggregated per calendar quality issue and worker cycle.
        due=allrows(c,"SELECT * FROM reinstatement_requests WHERE status='PENDING' AND sla_status='PROVISIONAL' AND next_reminder_at IS NOT NULL AND next_reminder_at<=?",(current,))
        if due:
            for a in allrows(c,"SELECT id FROM users WHERE role='admin' AND active=1"):
                notify(c,a['id'],'CALENDAR_UNVERIFIED',f'{len(due)} reinstatement perlu perhatian; kalender belum terverifikasi. Tidak ada eskalasi otomatis.',f'provisional-{cal["version"]}-{datetime.now(timezone.utc).date().isoformat()}-{a["id"]}')
            for r in due:
                nxt=business_due(current,holidays=json.loads(cal['holidays_json']),hours=json.loads(cal['hours_json']))
                c.execute('UPDATE reinstatement_requests SET next_reminder_at=?,reminder_seq=reminder_seq+1 WHERE id=?',(nxt,r['id']))
                audit(c,None,'PROVISIONAL_REMINDER_SCHEDULED','reinstatement',r['id'],{'next_reminder_at':nxt,'seq':r['reminder_seq']+1})
                stats['provisional_reminders']+=1
        # Only unsubmitted soft-deleted drafts may be permanently purged.
        for t in allrows(c,"SELECT * FROM transactions WHERE status='DRAFT' AND deleted_at IS NOT NULL AND purge_at <= ?",(current,)):
            vers=allrows(c,'SELECT storage_path FROM document_versions WHERE document_id=?',(t['document_id'],))
            paths.extend(x['storage_path'] for x in vers)
            c.execute('DELETE FROM extraction_runs WHERE document_id=?',(t['document_id'],))
            c.execute('DELETE FROM document_versions WHERE document_id=?',(t['document_id'],))
            c.execute('DELETE FROM transactions WHERE id=?',(t['id'],))
            c.execute('DELETE FROM documents WHERE id=?',(t['document_id'],))
            audit(c,None,'DRAFT_PURGED','transaction',t['id'],{'deleted_at':t['deleted_at']})
            stats['purged_drafts']+=1
    for p in paths:
        try:Path(p).unlink(missing_ok=True)
        except OSError:pass
    return stats

if __name__=='__main__':
    print('MHS local background worker started; Ctrl+C to stop.')
    try:
        while True:
            try:print('Worker tick:',run_once(),flush=True)
            except Exception as e:print('Worker error:',str(e),file=sys.stderr,flush=True)
            time.sleep(60)
    except KeyboardInterrupt:print('Worker stopped')
