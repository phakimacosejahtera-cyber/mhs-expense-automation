import assert from 'node:assert/strict';
import test from 'node:test';
import {handle,matchesOwner} from '../../frontend/owner-pages.mjs';

const env={MHS_PUBLIC_ORIGIN:'https://mhs-test.pages.dev',MHS_SUPABASE_URL:'https://fixture.supabase.co',
  MHS_OWNER_EMAIL:'owner@example.test',MHS_SUPABASE_PUBLISHABLE_KEY:'sb_publishable_test',
  MHS_OWNER_SUPABASE_ID:'owner-uuid',MHS_OWNER_GOOGLE_SUB:'google-sub'};
const user={id:'owner-uuid',email:env.MHS_OWNER_EMAIL,role:'authenticated',email_confirmed_at:'2026-01-01',
  identities:[{provider:'google',identity_data:{email:env.MHS_OWNER_EMAIL,email_verified:true,sub:'google-sub'}}]};
const call=(path,init={})=>handle({request:new Request(env.MHS_PUBLIC_ORIGIN+path,init),env});
test('pins both provider identifiers, single Google identity and verified email',()=>{
  assert.ok(matchesOwner(user,env));
  for(const override of [{id:'other'},{email:'other@example.test'},{is_anonymous:true},{identities:[]},
    {identities:[...user.identities,...user.identities]},{role:'anon'},{email_confirmed_at:null}])
    assert.ok(!matchesOwner({...user,...override},env));
  assert.ok(!matchesOwner(user,{...env,MHS_OWNER_GOOGLE_SUB:'other'}));
});
test('login uses the pinned HTTPS callback and a host-scoped verifier',async()=>{
  const r=await call('/api/auth/google/start');
  const target=new URL(r.headers.get('location'));
  assert.equal(target.searchParams.get('redirect_to'),env.MHS_PUBLIC_ORIGIN+'/api/auth/google/callback');
  assert.equal(target.searchParams.get('code_challenge_method'),'s256');
  assert.match(r.headers.get('set-cookie'),/__Host-mhs-verifier=[\w-]{43}; Path=\/; Secure; HttpOnly/);
});
test('direct callback, missing session, foreign origin and cross-site logout fail closed',async()=>{
  assert.equal((await call('/api/auth/google/callback?code=x')).headers.get('location'),'/?login=denied');
  assert.equal((await call('/api/me')).status,401);
  assert.equal((await call('/api/auth/logout',{method:'POST'})).status,403);
  assert.equal((await handle({request:new Request('https://other.example/api/me'),env})).status,503);
});
test('PKCE exchange accepts the independently verified owner and hides tokens from HTML',async t=>{
  const start=await call('/api/auth/google/start');
  const verifier=start.headers.get('set-cookie').split(';')[0];
  t.mock.method(globalThis,'fetch',async(url,opts)=>{
    if(url.includes('/token?')){
      assert.equal(JSON.parse(opts.body).code_verifier,verifier.split('=')[1]);
      return Response.json({access_token:'owner-token',expires_in:120});
    }
    assert.equal(opts.headers.Authorization,'Bearer owner-token');
    return Response.json(user);
  });
  const result=await call('/api/auth/google/callback?code=fixture',{headers:{Cookie:verifier}});
  assert.equal(result.headers.get('location'),'/');
  assert.match(result.headers.get('set-cookie'),/__Host-mhs-session=owner-token; Path=\/; Secure; HttpOnly/);
  assert.equal(await result.text(),'');
});
