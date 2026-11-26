-- Run in the Supabase SQL Editor of the hosted preview project.
-- The transaction can be repeated. Existing receipts and tables are preserved.
begin;
create schema if not exists mhs_pages;
revoke all on schema mhs_pages from public, anon, authenticated;
set local search_path = mhs_pages, pg_catalog;
create table if not exists owner_pin(singleton boolean primary key check(singleton), uid uuid not null, sub text not null);
insert into owner_pin
select true,u.id,i.identity_data->>'sub' from auth.users u join auth.identities i on i.user_id=u.id
where lower(u.email)='phakimacosejahtera@gmail.com' and i.provider='google' and u.email_confirmed_at is not null
on conflict do nothing;
do $$begin if not exists(select from owner_pin) then raise exception 'Owner Google belum terdaftar'; end if;end$$;

create or replace function mhs_pages.allowed() returns boolean language sql stable security definer
set search_path='' as $$
 select exists(select 1 from mhs_pages.owner_pin p join auth.identities i on i.user_id=p.uid
 where p.uid=auth.uid() and i.provider='google' and i.identity_data->>'sub'=p.sub
 and auth.jwt()->'app_metadata'->>'provider'='google'
 and exists(select from jsonb_array_elements(auth.jwt()->'amr') a where a->>'method'='oauth')
 and not exists(select from auth.identities j where j.user_id=p.uid and j.provider<>'google'))
$$;
revoke all on function allowed() from public;
grant usage on schema mhs_pages to authenticated;
grant execute on function allowed() to authenticated;

create table if not exists activities(id uuid primary key default gen_random_uuid(), name text unique not null, status text default 'ACTIVE',closure_status text default 'OPEN');
create table if not exists categories(id uuid primary key default gen_random_uuid(),name text unique not null);
create table if not exists batches(id uuid primary key default gen_random_uuid(),activity_id uuid not null references activities);
create table if not exists receipts(id uuid primary key, batch_id uuid not null references batches, path text unique not null,filename text not null,
 media_type text not null,file_size int not null check(file_size between 1 and 8388608),sha256 text not null check(length(sha256)=64));
create table if not exists transactions(id uuid primary key default gen_random_uuid(),document_id uuid unique not null references receipts,
 activity_id uuid not null references activities, category_id uuid references categories,transaction_date date, amount_cents bigint check(amount_cents between 1 and 99999999999900),
 description text,vendor text,payment_method text,invoice_number text,notes text,contract_name text,contract_number text,
 status text not null default 'DRAFT' check(status in ('DRAFT','PENDING_REVIEW','APPROVED','REJECTED','REVERSED')),
 created_at timestamptz default now(),updated_at timestamptz default now(),deleted_at timestamptz,purge_at timestamptz,revision integer not null default 1,
 risk_reasons text default '[]',late_reason text,ocr jsonb);
create table if not exists income(id uuid primary key, transaction_date date not null,amount_cents bigint not null check(amount_cents between 1 and 99999999999900),
 description text not null,sender text,contract_name text,contract_number text,reversed_at timestamptz,reversal_reason text);
create table if not exists requests(id uuid primary key default gen_random_uuid(),transaction_id uuid not null references transactions,
 kind text not null,reason text not null,requester_id uuid not null,status text not null default 'PENDING',proposed_json text,created_at timestamptz default now(),
 sla_status text default 'PROVISIONAL',assignment_stage text default 'PRIMARY',assigned_reviewer_id uuid);
create unique index if not exists mhs_one_pending on requests(transaction_id,kind) where status='PENDING';
create table if not exists events(id bigint generated always as identity primary key,created_at timestamptz default now(),actor_name text not null,action text not null,target_id uuid,target_type text,details jsonb);
create table if not exists calendars(id uuid primary key default gen_random_uuid(),source text not null,entries_json jsonb not null,year_start int not null,year_end int not null,status text default 'STAGED',version int,created_at timestamptz default now());
create table if not exists versions(id uuid primary key references receipts,document_id uuid references receipts not null,version_number int not null,created_at timestamptz default now(),unique(document_id,version_number));
alter table requests add column if not exists attachment_id uuid references receipts;
alter table transactions add column if not exists current_file uuid references receipts;
create table if not exists exports(id uuid primary key default gen_random_uuid(),created_at timestamptz default now(),params jsonb not null,snapshot jsonb not null);
create table if not exists file_jobs(path text primary key, created_at timestamptz not null default now(), ready_at timestamptz not null);
create or replace function mhs_pages.disposable(object_path text) returns boolean language sql stable security definer set search_path='' as $$
 select mhs_pages.allowed() and exists(select from mhs_pages.file_jobs where path=object_path and ready_at<=now())
 and not exists(select from mhs_pages.receipts r where r.path=object_path)
$$;
revoke all on function disposable(text) from public;
grant execute on function disposable(text) to authenticated,anon;
revoke all on all tables in schema mhs_pages from public,anon,authenticated;
create or replace view ledger as select t.id,t.document_id,t.activity_id,t.category_id,t.transaction_date,t.amount_cents,t.description,t.vendor,t.payment_method,t.invoice_number,t.notes,t.contract_name,t.contract_number,
 t.status,t.created_at,t.updated_at,t.deleted_at,t.purge_at,t.revision,t.risk_reasons,t.late_reason,a.name activity_name,c.name category_name,'Owner'::text uploader_name,r.filename,
 (select count(*) from requests q where q.transaction_id=t.id and q.kind='correction' and q.status='PENDING') correction_pending,
 (select count(*) from requests q where q.transaction_id=t.id and q.kind='reinstatement' and q.status='PENDING') reinstatement_pending
 from transactions t join activities a on a.id=t.activity_id join receipts r on r.id=t.document_id left join categories c on c.id=t.category_id;
revoke all on ledger from public,anon,authenticated;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('mhs-pages-receipts','mhs-pages-receipts',false,8388608,array['image/jpeg','image/png','image/webp','application/pdf'])
on conflict(id) do nothing;
do $$begin if not exists(select from storage.buckets where id='mhs-pages-receipts' and not public and file_size_limit=8388608)
 then raise exception 'Bucket incompatible'; end if;end$$;
create or replace function mhs_pages.reserved(object_path text) returns boolean language sql stable security definer set search_path='' as $$
 select mhs_pages.allowed() and exists(select from mhs_pages.file_jobs where path=object_path and ready_at>now())
$$;
revoke all on function reserved(text) from public;
grant execute on function reserved(text) to authenticated,anon;
drop policy if exists mhs_pages_reservation on storage.objects;
create policy mhs_pages_reservation on storage.objects as restrictive for insert to public with check(bucket_id<>'mhs-pages-receipts' or mhs_pages.reserved(name));
drop policy if exists mhs_pages_insert on storage.objects;
create policy mhs_pages_insert on storage.objects for insert to authenticated
with check(bucket_id='mhs-pages-receipts' and mhs_pages.allowed() and split_part(name,'/',1)=auth.uid()::text);
drop policy if exists mhs_pages_read on storage.objects;
create policy mhs_pages_read on storage.objects for select to authenticated using(bucket_id='mhs-pages-receipts' and mhs_pages.allowed() and split_part(name,'/',1)=auth.uid()::text);
-- Restrict any broader existing policies on this new bucket.
drop policy if exists mhs_pages_guard on storage.objects;
create policy mhs_pages_guard on storage.objects as restrictive for all to public
using(bucket_id<>'mhs-pages-receipts' or (mhs_pages.allowed() and split_part(name,'/',1)=auth.uid()::text))
with check(bucket_id<>'mhs-pages-receipts' or (mhs_pages.allowed() and split_part(name,'/',1)=auth.uid()::text));
drop policy if exists mhs_pages_immutable on storage.objects;
create policy mhs_pages_immutable on storage.objects as restrictive for update to public using(bucket_id<>'mhs-pages-receipts') with check(bucket_id<>'mhs-pages-receipts');
drop policy if exists mhs_pages_keep on storage.objects;
create policy mhs_pages_keep on storage.objects as restrictive for delete to public using(bucket_id<>'mhs-pages-receipts' or mhs_pages.disposable(name));
drop policy if exists mhs_pages_cleanup on storage.objects;
create policy mhs_pages_cleanup on storage.objects for delete to authenticated using(bucket_id='mhs-pages-receipts' and mhs_pages.disposable(name));
grant usage on schema mhs_pages to anon;
grant execute on function allowed() to anon;

create or replace function public.mhs_pages_api(op text, body jsonb default '{}', item uuid default null)
returns jsonb language plpgsql security definer set search_path=pg_catalog,mhs_pages,pg_temp as $$
declare
 result jsonb; obj jsonb; k uuid; cat uuid; rec transactions%rowtype; req requests%rowtype; inc income%rowtype;
 title text:=trim(body->>'name'); why text:=trim(body->>'reason'); today date:=(now() at time zone 'Asia/Jakarta')::date;
 newstatus text; log_action text; meta jsonb:='{}'; rows jsonb:='[]'; target uuid:=item;
begin
 if not mhs_pages.allowed() then raise insufficient_privilege; end if;
 if length(body::text)>100000 then raise exception 'Data terlalu besar'; end if;
 case op
 when 'config' then return jsonb_build_object('activities',coalesce((select jsonb_agg(a order by name) from activities a where status<>'ARCHIVED'),'[]'),
 'categories',coalesce((select jsonb_agg(c order by name) from categories c),'[]'),'company','PT Mulia Hakimaco Sejahtera');
 when 'transactions','deleted' then return coalesce((select jsonb_agg(to_jsonb(l)||jsonb_build_object('can_purge',l.deleted_at is not null) order by created_at desc,id) from ledger l where (deleted_at is not null)=(op='deleted')),'[]');
 when 'queue' then return jsonb_build_object('transactions',coalesce((select jsonb_agg(l order by created_at) from ledger l where status='PENDING_REVIEW'),'[]'),
 'reinstatements',coalesce((select jsonb_agg(to_jsonb(q)||jsonb_build_object('description',t.description)) from requests q join transactions t on t.id=q.transaction_id where q.kind='reinstatement' and q.status='PENDING'),'[]'),
 'corrections',coalesce((select jsonb_agg(to_jsonb(q)||jsonb_build_object('description',t.description,'replacement_version_number',(select version_number from versions where id=q.attachment_id))) from requests q join transactions t on t.id=q.transaction_id where q.kind='correction' and q.status='PENDING'),'[]'));
 when 'notifications' then return coalesce((select jsonb_agg(to_jsonb(e)||jsonb_build_object('type',action,'message',action) order by id desc) from (select * from events order by id desc limit 100)e),'[]');
 when 'audit' then return coalesce((select jsonb_agg(e order by id desc) from (select * from events order by id desc limit 200)e),'[]');
 when 'history' then return jsonb_build_object('audit',coalesce((select jsonb_agg(e order by id desc) from events e where target_id=item),'[]'),
 'versions',coalesce((select jsonb_agg(jsonb_build_object('filename',r.filename,'version_number',1,'created_at',t.created_at)) from transactions t join receipts r on r.id=t.document_id where t.id=item),'[]') ||
 coalesce((select jsonb_agg(jsonb_build_object('filename',r.filename,'version_number',v.version_number,'created_at',v.created_at) order by v.version_number) from versions v join receipts r on r.id=v.id join transactions t on t.document_id=v.document_id where t.id=item),'[]'));
 when 'receipt' then
 if body?'version' then
 if body->>'version'='1' then k:=item;
 else select v.id into strict k from versions v where v.document_id=item and v.version_number=(body->>'version')::int;end if;
 else select coalesce(current_file,document_id) into strict k from transactions where document_id=item;end if;
 select to_jsonb(r) into strict result from receipts r where id=k; log_action:='DOCUMENT_OPENED';
 when 'activities','categories' then
 if title is null or length(title) not between 2 and 100 then raise exception 'Nama tidak valid'; end if;
 if op='activities' then insert into activities(name) values(title) returning id into k;
 else insert into categories(name) values(title) returning id into k;end if;
 target:=k; result:=jsonb_build_object('id',k);log_action:='MASTER_CREATED';
 when 'activity_edit' then
 if (body->>'closure_status') not in ('CLOSED','OPEN') or body->>'closure_status' is null then raise exception 'Status tidak valid';end if;
 update activities set closure_status=body->>'closure_status' where id=item;
 if not found then raise no_data_found;end if;log_action:='ACTIVITY_UPDATED';
 when 'batch' then insert into batches(activity_id) select id from activities where id=(body->>'activity_id')::uuid and status<>'ARCHIVED' returning id into strict k;
 return jsonb_build_object('id',k,'status','PROCESSING');
 when 'calendar' then return jsonb_build_object('active',coalesce((select jsonb_build_object('version',version,'timezone','Asia/Jakarta','verified',true) from calendars where status='PUBLISHED' order by version desc limit 1),jsonb_build_object('version',1,'timezone','Asia/Jakarta','verified',false)),
 'imports',coalesce((select jsonb_agg(c order by created_at desc) from calendars c),'[]'));
 when 'stage' then
 if coalesce(length(trim(body->>'source')),0)<5 or jsonb_typeof(body->'holidays') is distinct from 'array' or jsonb_array_length(body->'holidays')=0 then raise exception 'Periksa sumber dan daftar hari libur';end if;
 insert into calendars(source,entries_json,year_start,year_end) select trim(body->>'source'),body->'holidays',min(extract(year from d::date)),max(extract(year from d::date)) from jsonb_array_elements_text(body->'holidays')d returning id into target;log_action:='CALENDAR_STAGED';
 when 'publish' then
 lock table calendars in share row exclusive mode;
 update calendars set status='PUBLISHED',version=(select coalesce(max(version),1)+1 from calendars) where id=item and status='STAGED';if not found then raise no_data_found;end if;log_action:='CALENDAR_PUBLISHED';
 when 'reserve' then
 if not exists(select from batches where id=item) and not exists(select from requests where id=item and kind='correction' and status='PENDING') then raise no_data_found; end if;
 k:=gen_random_uuid();insert into file_jobs(path,ready_at) values(auth.uid()::text||'/'||k::text,now()+interval '1 hour');return to_jsonb(k);
 when 'cleanup' then return coalesce((select jsonb_agg(path) from(select path from file_jobs where ready_at<=now() order by ready_at limit 100)j),'[]');
 when 'cleanup_done' then delete from file_jobs j where j.ready_at<=now() and j.path in(select jsonb_array_elements_text(body->'paths'))
 and not exists(select from storage.objects s where s.bucket_id='mhs-pages-receipts' and s.name=j.path);return '{}';
 when 'storage' then return (select jsonb_build_object('files',count(*),'bytes',coalesce(sum(file_size),0)) from receipts);
 when 'trash_preview','empty_trash','purge' then
 if op<>'purge' then lock table transactions in share row exclusive mode;end if;
 select coalesce(jsonb_agg(id order by id),'[]') into rows from transactions where status='DRAFT' and deleted_at is not null and (op<>'purge' or id=item);
 if op='trash_preview' then return jsonb_build_object('token',md5(rows::text),'count',jsonb_array_length(rows));end if;
 if op='empty_trash' and md5(rows::text) is distinct from body->>'token' then raise exception 'Daftar draft berubah';end if;
 for k in select value::uuid from jsonb_array_elements_text(rows) loop
 delete from transactions where id=k and status='DRAFT' and deleted_at is not null returning document_id into strict cat;
 insert into file_jobs(path,ready_at) select path,now() from receipts where id=cat;
 delete from receipts where id=cat;insert into events(actor_name,action,target_id,target_type,details) values('Owner','DRAFT_PURGED',k,'transaction','{}');
 end loop;return jsonb_build_object('count',jsonb_array_length(rows),'pending',jsonb_array_length(rows));
 when 'upload','replacement' then
 k:=(body->>'document_id')::uuid;
 delete from file_jobs where path=auth.uid()::text||'/'||k::text and ready_at>now();
 if not found then raise exception 'Reservasi unggahan kedaluwarsa';end if;
 if not exists(select from storage.objects s where s.bucket_id='mhs-pages-receipts' and s.name=auth.uid()::text||'/'||k::text
 and (s.metadata->>'size')::bigint=(body->>'file_size')::bigint and s.metadata->>'mimetype'=body->>'media_type') then raise exception 'Bukti tidak ditemukan';end if;
 if op='replacement' then
 select * into strict req from requests where id=item and kind='correction' and status='PENDING' and attachment_id is null for update;
 select * into strict rec from transactions where id=req.transaction_id and status='APPROVED' for update;
 end if;
 insert into receipts values(k,case when op='upload' then item else (select batch_id from receipts where id=rec.document_id) end,auth.uid()::text||'/'||k::text,left(body->>'filename',240),body->>'media_type',(body->>'file_size')::int,body->>'sha256');
 if op='replacement' then
 insert into versions select k,rec.document_id,coalesce(max(version_number),1)+1,now() from versions where document_id=rec.document_id;
 update requests set attachment_id=k where id=item; target:=rec.id;log_action:='REPLACEMENT_PROPOSED';
 else
 insert into transactions(document_id,activity_id) select k,activity_id from batches where id=item returning id into strict target;
 log_action:='DOCUMENT_UPLOADED';result:=jsonb_build_object('transaction_id',target,'document_id',k); end if;
 when 'ocr_get' then select ocr into strict result from transactions where id=item;return coalesce(result,'{}');
 when 'submit' then
 if jsonb_array_length(body->'ids') not between 1 and 100 then raise exception 'Pilih 1 sampai 100 draft';end if;
 for k in select value::uuid from jsonb_array_elements_text(body->'ids') order by 1 loop
 select * into strict rec from transactions where id=k and status='DRAFT' and deleted_at is null for update;
 if rec.amount_cents is null or rec.transaction_date is null or rec.category_id is null or nullif(trim(rec.description),'') is null then raise exception 'Draft belum lengkap';end if;
 if exists(select from activities where id=rec.activity_id and closure_status='CLOSED') and coalesce(length(trim(body->>'late_reason')),0)<5 then raise exception 'Alasan keterlambatan wajib';end if;
 update transactions set status='PENDING_REVIEW',revision=revision+1,updated_at=now(),late_reason=body->>'late_reason',risk_reasons='["Bukti dan nominal memerlukan pemeriksaan manual"]' where id=k;
 insert into events(actor_name,action,target_id,target_type,details) values('Owner','TRANSACTION_SUBMITTED',k,'transaction','{}');
 rows:=rows||jsonb_build_object('id',k,'status','PENDING_REVIEW');
 end loop;return jsonb_build_object('items',rows);
 when 'income_create' then
 k:=(body->>'request_id')::uuid;
 if coalesce(length(trim(body->>'description')),0)=0 or (body->>'transaction_date')::date>today then raise exception 'Tanggal atau keterangan tidak valid';end if;
 insert into income(id,transaction_date,amount_cents,description,sender,contract_name,contract_number)
 values(k,(body->>'transaction_date')::date,(body->>'amount_cents')::bigint,trim(body->>'description'),body->>'sender',body->>'contract_name',body->>'contract_number') on conflict do nothing;
 if not found then
 select * into strict inc from income where id=k;
 if (inc.transaction_date,inc.amount_cents,inc.description,inc.sender,inc.contract_name,inc.contract_number) is distinct from
 ((body->>'transaction_date')::date,(body->>'amount_cents')::bigint,trim(body->>'description'),body->>'sender',body->>'contract_name',body->>'contract_number') then raise exception 'ID sudah digunakan';end if;
 return jsonb_build_object('id',k,'replayed',true);end if;
 target:=k;result:=jsonb_build_object('id',k);log_action:='INCOME_RECORDED';
 when 'income_reverse' then
 if coalesce(length(why),0)<5 then raise exception 'Alasan wajib';end if;
 update income set reversed_at=now(),reversal_reason=why where id=item and reversed_at is null;
 if not found then raise no_data_found;end if;log_action:='INCOME_REVERSED';
 when 'finance','export' then
 select jsonb_build_object('expenses',coalesce((select jsonb_agg(l order by transaction_date,id) from ledger l where status='APPROVED' and deleted_at is null),'[]'),
 'incomes',coalesce((select jsonb_agg(i order by transaction_date desc,id) from income i),'[]'),
 'drafts',(select count(*) from transactions where status='DRAFT' and deleted_at is null),'pending_review',(select count(*) from transactions where status='PENDING_REVIEW')) into result;
 if op='finance' then return result;end if;
 insert into exports(params,snapshot) values(body,result) returning id into target;log_action:='FINANCE_EXPORTED';meta:=body;
 when 'correction_decision' then
 select * into strict req from requests where id=item and status='PENDING' and kind='correction' for update;
 select * into strict rec from transactions where id=req.transaction_id and status='APPROVED' for update;
 if coalesce(length(why),0)<1 or coalesce(body->>'decision','') not in ('APPROVE','REJECT') then raise exception 'Keputusan tidak valid';end if;
 newstatus:=case when body->>'decision'='APPROVE' then 'APPROVED' else 'REJECTED' end;
 if newstatus='APPROVED' then
 obj:=req.proposed_json::jsonb;
 update transactions set current_file=coalesce(req.attachment_id,current_file),description=coalesce(obj->>'description',description),vendor=coalesce(obj->>'vendor',vendor),notes=coalesce(obj->>'notes',notes),
 transaction_date=coalesce((obj->>'transaction_date')::date,transaction_date),category_id=coalesce((obj->>'category_id')::uuid,category_id),
 amount_cents=coalesce((obj->>'amount_cents')::bigint,amount_cents),invoice_number=coalesce(obj->>'invoice_number',invoice_number),
 payment_method=coalesce(obj->>'payment_method',payment_method),revision=revision+1,updated_at=now() where id=req.transaction_id;end if;
 update requests set status=newstatus where id=item;target:=req.transaction_id;meta:=jsonb_build_object('reason',why,'request_id',item);log_action:='CORRECTION_'||newstatus;
 else
 select * into strict rec from transactions where id=item for update;
 if (rec.deleted_at is not null and op<>'restore') or (rec.status<>'DRAFT' and op in ('draft','ocr','trash','restore')) then raise exception 'Status transaksi berubah';end if;
 case op
 when 'draft' then
 title:=trim(body->>'category_name');
 if coalesce(length(title),0) not between 1 and 80 or coalesce(length(trim(body->>'description')),0)=0 or
 coalesce(body->>'amount','') !~ '^[0-9]{1,12}([.][0-9]{1,2})?$' or (body->>'transaction_date')::date>today then raise exception 'Periksa nominal, tanggal, kategori dan keterangan';end if;
 insert into categories(name) values(title) on conflict(name) do update set name=excluded.name returning id into cat;
 update transactions set category_id=cat,amount_cents=((body->>'amount')::numeric*100)::bigint,transaction_date=(body->>'transaction_date')::date,description=trim(body->>'description'),
 vendor=body->>'vendor',payment_method=body->>'payment_method',invoice_number=body->>'invoice_number',notes=body->>'notes',contract_name=body->>'contract_name',contract_number=body->>'contract_number',
 revision=revision+1,updated_at=now() where id=item;result:=jsonb_build_object('category',jsonb_build_object('id',cat,'name',title));log_action:='DRAFT_UPDATED';
 when 'ocr' then update transactions set ocr=body where id=item;return jsonb_build_object('run_id',item);
 when 'trash' then update transactions set deleted_at=now(),purge_at=now()+interval '30 days' where id=item;log_action:='DRAFT_DELETED';
 when 'restore' then if rec.deleted_at is null or rec.purge_at<now() then raise exception 'Pemulihan tidak tersedia';end if;update transactions set deleted_at=null,purge_at=null where id=item;log_action:='DRAFT_RESTORED';
 when 'decision' then
 if rec.status<>'PENDING_REVIEW' or rec.revision is distinct from (body->>'revision')::int or coalesce(length(why),0)<1 or coalesce(body->>'decision','') not in ('APPROVE','REJECT') then raise exception 'Keputusan atau revisi tidak valid';end if;
 newstatus:=case when body->>'decision'='APPROVE' then 'APPROVED' else 'REJECTED' end;
 update transactions set status=newstatus,revision=revision+1,updated_at=now() where id=item;log_action:='ADMIN_'||newstatus;
 when 'reverse' then
 if rec.status<>'APPROVED' or coalesce(length(why),0)<5 then raise exception 'Pembatalan tidak valid';end if;
 update transactions set status='REVERSED',revision=revision+1,updated_at=now() where id=item;
 update requests set status='REJECTED' where transaction_id=item and status='PENDING' and kind='correction';log_action:='TRANSACTION_REVERSED';
 when 'reinstatement','correction' then
 if coalesce(length(why),0)<5 or rec.status<>(case when op='reinstatement' then 'REVERSED' else 'APPROVED' end) then raise exception 'Permintaan tidak valid';end if;
 obj:=body->'proposed';
 if op='correction' then
 if jsonb_typeof(obj) is distinct from 'object' or obj='{}' or (obj-array['amount','transaction_date','description','category_id','vendor','invoice_number','payment_method','notes'])<>'{}' then raise exception 'Usulan tidak valid';end if;
 if obj?'amount' then if (obj->>'amount') !~ '^[0-9]{1,12}([.][0-9]{1,2})?$' or (obj->>'amount')::numeric<=0 then raise exception 'Nominal tidak valid';end if;
 obj:=(obj-'amount')||jsonb_build_object('amount_cents',((obj->>'amount')::numeric*100)::bigint);end if;
 if obj?'description' and coalesce(length(trim(obj->>'description')),0)=0 or (obj->>'transaction_date')::date>today then raise exception 'Usulan tidak valid';end if;
 end if;
 insert into requests(transaction_id,kind,reason,requester_id,proposed_json) values(item,op,why,auth.uid(),obj::text) returning id into k;
 result:=jsonb_build_object('id',k,'status','PENDING','sla_status','PROVISIONAL');log_action:=upper(op)||'_REQUESTED';
 else raise exception 'Operasi tidak tersedia';end case;
 end case;
 insert into events(actor_name,action,target_id,target_type,details) values('Owner',log_action,target,case when op like 'income%' then 'income' else 'transaction' end,
 meta||jsonb_strip_nulls(jsonb_build_object('reason',why)));
 if op='export' then result:=result||jsonb_build_object('snapshot_id',target);end if;
 return coalesce(result,jsonb_build_object('ok',true,'transaction_status',newstatus));
end$$;
revoke all on function public.mhs_pages_api(text,jsonb,uuid) from public,anon;
grant execute on function public.mhs_pages_api(text,jsonb,uuid) to authenticated;
notify pgrst,'reload schema';
commit;
