begin;
create or replace function mhs_pages.company_email_otp_uid() returns uuid language sql stable security definer set search_path='' as $$
select u.id from auth.users u join auth.identities i on i.user_id=u.id
 where u.id=auth.uid() and not coalesce(u.is_anonymous,false) and u.email_confirmed_at is not null
 and lower(u.email)='admin@muliahakimaco.co.id' and lower(auth.jwt()->>'email')=lower(u.email)
 and i.provider='email' and lower(i.identity_data->>'email')=lower(u.email)
 and exists(select from jsonb_array_elements(auth.jwt()->'amr') a where a->>'method'='otp')
$$;
revoke all on function mhs_pages.company_email_otp_uid() from public, anon, authenticated;
create or replace function mhs_pages.allowed() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select from auth.users u join auth.identities i on i.user_id=u.id
 where u.id=auth.uid() and u.email_confirmed_at is not null and not coalesce(u.is_anonymous,false)
 and i.provider='google' and lower(i.identity_data->>'email')=lower(u.email)
 and i.identity_data->>'sub'=i.provider_id and i.identity_data->>'email_verified'='true'
 and auth.jwt()->'app_metadata'->>'provider'='google'
 and exists(select from jsonb_array_elements(auth.jwt()->'amr') a where a->>'method'='oauth')
 and not exists(select from auth.identities j where j.user_id=u.id and j.id<>i.id)
 and ((lower(u.email)='phakimacosejahtera@gmail.com' and exists(select from mhs_pages.owner_pin p where p.uid=u.id and p.sub=i.provider_id))
 or (lower(u.email)='admin@muliahakimaco.co.id' and exists(select from mhs_pages.company_owner p where p.uid=u.id and p.google_sub=i.provider_id))))
 or exists(select from mhs_pages.company_owner p where p.uid=mhs_pages.company_email_otp_uid())
$$;

create or replace function mhs_pages.activate_company_owner() returns boolean language plpgsql security definer set search_path='' as $$
begin
 if mhs_pages.allowed() then return true; end if;
 insert into mhs_pages.company_owner
select true, u.id, i.provider_id from auth.users u join auth.identities i on i.user_id=u.id
where u.id=auth.uid() and auth.jwt()->'app_metadata'->>'provider'='google'
and exists(select from jsonb_array_elements(auth.jwt()->'amr') a where a->>'method'='oauth')
and lower(u.email)='admin@muliahakimaco.co.id' and u.email_confirmed_at is not null
and not coalesce(u.is_anonymous,false) and i.provider='google'
and i.identity_data->>'sub'=i.provider_id and lower(i.identity_data->>'email')=lower(u.email)
and i.identity_data->>'email_verified'='true'
and lower(coalesce(i.identity_data->>'hd',i.identity_data->'custom_claims'->>'hd'))='muliahakimaco.co.id'
and not exists(select from auth.identities j where j.user_id=u.id and j.id<>i.id)
union all select true, uid, 'email:'||uid::text from (select mhs_pages.company_email_otp_uid() as uid) verified where uid is not null
on conflict do nothing;
 if found then
   insert into mhs_pages.events(actor_name,action,target_id,target_type,details)
   values('admin@muliahakimaco.co.id','OWNER_ACTIVATED',auth.uid(),'owner','{}');
 end if;
 return mhs_pages.allowed();
end$$;

commit;
