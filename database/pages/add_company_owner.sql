-- Apply after the company account has signed in with Google and its identity has been verified.
begin;
create table if not exists mhs_pages.company_owner (
 singleton boolean primary key check (singleton),
 uid uuid unique not null, google_sub text unique not null
);
revoke all on mhs_pages.company_owner from public, anon, authenticated;

insert into mhs_pages.company_owner
select true, u.id, i.provider_id from auth.users u join auth.identities i on i.user_id=u.id
where lower(u.email)='admi@muliahakimaco.co.id' and u.email_confirmed_at is not null
and not coalesce(u.is_anonymous,false) and i.provider='google'
and i.identity_data->>'sub'=i.provider_id and lower(i.identity_data->>'email')=lower(u.email)
and i.identity_data->>'email_verified'='true'
and lower(coalesce(i.identity_data->>'hd',i.identity_data->'custom_claims'->>'hd'))='muliahakimaco.co.id'
and not exists(select from auth.identities j where j.user_id=u.id and j.id<>i.id)
on conflict do nothing;
do $$begin
 if not exists(select from mhs_pages.company_owner) then
   raise exception 'Verifikasi identitas Google Workspace admi terlebih dahulu';
 end if;
end$$;

create or replace function mhs_pages.allowed() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select from auth.users u join auth.identities i on i.user_id=u.id
 where u.id=auth.uid() and u.email_confirmed_at is not null and not coalesce(u.is_anonymous,false)
 and i.provider='google' and lower(i.identity_data->>'email')=lower(u.email)
 and i.identity_data->>'sub'=i.provider_id and i.identity_data->>'email_verified'='true'
 and auth.jwt()->'app_metadata'->>'provider'='google'
 and exists(select from jsonb_array_elements(auth.jwt()->'amr') a where a->>'method'='oauth')
 and not exists(select from auth.identities j where j.user_id=u.id and j.id<>i.id)
 and ((lower(u.email)='phakimacosejahtera@gmail.com' and exists(select from mhs_pages.owner_pin p where p.uid=u.id and p.sub=i.provider_id))
 or (lower(u.email)='admi@muliahakimaco.co.id' and exists(select from mhs_pages.company_owner p where p.uid=u.id and p.google_sub=i.provider_id))))
$$;

create or replace function mhs_pages.shared_receipt(object_path text) returns boolean
language sql stable security definer set search_path='' as $$
 select mhs_pages.allowed() and exists(select from
 (select uid from mhs_pages.owner_pin union all select uid from mhs_pages.company_owner) owners
 where owners.uid::text=split_part(object_path,'/',1))
 and (exists(select from mhs_pages.receipts r where r.path=object_path) or mhs_pages.disposable(object_path))
$$;
revoke all on function mhs_pages.shared_receipt(text) from public;
grant execute on function mhs_pages.shared_receipt(text) to authenticated, anon;
alter policy mhs_pages_guard on storage.objects using(bucket_id<>'mhs-pages-receipts' or
 (mhs_pages.allowed() and (split_part(name,'/',1)=auth.uid()::text or mhs_pages.shared_receipt(name))))
 with check(bucket_id<>'mhs-pages-receipts' or (mhs_pages.allowed() and split_part(name,'/',1)=auth.uid()::text));
create policy mhs_pages_shared_read on storage.objects for select to authenticated
 using(bucket_id='mhs-pages-receipts' and mhs_pages.shared_receipt(name));

create function mhs_pages.stamp_owner_event() returns trigger language plpgsql security definer set search_path='' as $$
begin
 if new.actor_name='Owner' and mhs_pages.allowed() then
  select u.email into strict new.actor_name from auth.users u where u.id=auth.uid();
  new.details:=coalesce(new.details,'{}')||jsonb_build_object('actor_id',auth.uid());
 end if;
 return new;
end$$;
revoke all on function mhs_pages.stamp_owner_event() from public, anon, authenticated;
create trigger stamp_owner_event before insert on mhs_pages.events for each row execute function mhs_pages.stamp_owner_event();
commit;
