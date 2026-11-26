import {workspace} from './pages-workspace.mjs';
const verifierCookie = '__Host-mhs-verifier';
const sessionCookie = '__Host-mhs-session';
const csrfCookie = '__Host-mhs-csrf';
const callback = '/api/auth/google/callback';
const encode = bytes => btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
function random() { return encode(crypto.getRandomValues(new Uint8Array(32))); }
function cookie(name, value, age) {
  return `${name}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${age}`;
}
function readCookie(request, name) {
  return request.headers.get('Cookie')?.split(';').map(s => s.trim()).find(s => s.startsWith(name + '='))?.slice(name.length + 1) || '';
}
function response(body, status, cookies = [], location) {
  const headers = new Headers({'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','Content-Type':'application/json'});
  for (const c of cookies) headers.append('Set-Cookie', c);
  if (location) headers.set('Location', location);
  return new Response(body === null ? null : JSON.stringify(body), {status, headers});
}
function settings(request, env) {
  const base = env.MHS_SUPABASE_URL;
  if (!/^https:\/\/[a-z0-9]+\.supabase\.co$/.test(base) ||
      !env.MHS_SUPABASE_PUBLISHABLE_KEY?.startsWith('sb_publishable_') ||
      !env.MHS_OWNER_EMAIL || !env.MHS_OWNER_SUPABASE_ID || !env.MHS_OWNER_GOOGLE_SUB ||
      !env.MHS_PUBLIC_ORIGIN?.startsWith('https://') ||
      new URL(request.url).origin !== env.MHS_PUBLIC_ORIGIN) throw Error('configuration');
  return {base, headers:{apikey:env.MHS_SUPABASE_PUBLISHABLE_KEY}};
}
export function matchesOwner(user, env) {
  const identity = user?.identities?.length === 1 && user.identities[0];
  const email = env.MHS_OWNER_EMAIL.toLowerCase();
  return user?.id === env.MHS_OWNER_SUPABASE_ID && user.role === 'authenticated' &&
    !user.is_anonymous && !!user.email_confirmed_at && user.email?.toLowerCase() === email &&
    identity?.provider === 'google' && identity.identity_data?.email_verified === true &&
    identity.identity_data.email?.toLowerCase() === email && identity.identity_data.sub === env.MHS_OWNER_GOOGLE_SUB;
}
async function owner(config, env, token) {
  if (!token) return null;
  const res = await fetch(config.base+'/auth/v1/user', {headers:{...config.headers, Authorization:'Bearer '+token}, redirect:'manual'});
  if (res.status===429 || res.status>=500) throw Error('auth unavailable');
  if (!res.ok) return null;
  const user = await res.json();
  return matchesOwner(user, env) ? user : null;
}
export async function handle({request, env}) {
  let config;
  try { config = settings(request, env); }
  catch { return response({detail:'Konfigurasi workspace belum tersedia'}, 503); }
  const {pathname,searchParams} = new URL(request.url);
  const clear = [cookie(verifierCookie,'',0),cookie(sessionCookie,'',0),cookie(csrfCookie,'',0)];
  try {
    if (request.method === 'GET' && pathname === '/api/auth/google/start') {
      const verifier = random();
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
      const url = new URL(config.base+'/auth/v1/authorize');
      url.search = new URLSearchParams({provider:'google',redirect_to:env.MHS_PUBLIC_ORIGIN+callback,code_challenge_method:'s256',code_challenge:encode(new Uint8Array(digest)),prompt:'select_account'});
      return response(null,302,[cookie(verifierCookie,verifier,300)],url.href);
    }
    if (request.method === 'GET' && pathname === callback) {
      const verifier = readCookie(request,verifierCookie);
      const code = searchParams.get('code');
      if (!/^[\w-]{43}$/.test(verifier) || !code || code.length>2048) return response(null,302,clear,'/?login=denied');
      const res = await fetch(config.base+'/auth/v1/token?grant_type=pkce',{method:'POST',redirect:'manual',
        headers:{...config.headers,'Content-Type':'application/json'},body:JSON.stringify({auth_code:code,code_verifier:verifier})});
      const session = res.ok ? await res.json() : {};
      if (!await owner(config,env,session.access_token)) return response(null,302,clear,'/?login=denied');
      const age = Math.min(Number(session.expires_in) || 0, 3600);
      return response(null,302,[cookie(verifierCookie,'',0),cookie(sessionCookie,session.access_token,age),cookie(csrfCookie,random(),age)],'/');
    }
    const token = readCookie(request,sessionCookie);
    const csrf = readCookie(request,csrfCookie);
    if (request.method === 'POST' && pathname === '/api/auth/logout') {
      if (!csrf || csrf !== request.headers.get('X-CSRF-Token') || request.headers.get('Origin') !== env.MHS_PUBLIC_ORIGIN)
        return response({detail:'Permintaan ditolak'},403);
      if (token) await fetch(config.base+'/auth/v1/logout?scope=local',{method:'POST',redirect:'manual',headers:{...config.headers,Authorization:'Bearer '+token}});
      return response({ok:true},200,clear);
    }
    const user = await owner(config,env,token);
    if (!user) return response({detail:'Masuk dengan akun Owner'},401);
    if (request.method === 'GET' && pathname === '/api/me') return response({id:user.id,role:'admin',name:user.email,csrf},200);
    if (!['GET','HEAD'].includes(request.method) && (!csrf || csrf !== request.headers.get('X-CSRF-Token') || request.headers.get('Origin') !== env.MHS_PUBLIC_ORIGIN))
      return response({detail:'Permintaan ditolak'},403);
    try { return await workspace(request,config,token,user); }
    catch { return response({detail:'Workspace gagal memproses permintaan.'},503); }
  } catch {
    return response({detail:'Layanan autentikasi belum tersedia'},503);
  }
}
