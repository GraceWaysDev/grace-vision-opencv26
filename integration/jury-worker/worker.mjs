import {check,exact,seal,open,sha,random,json,bounded,image,LIMIT,HEADERS} from './security.mjs';
import {protocol,gatewayAddress} from './protocol.mjs';
import {CAT_POLICY} from './cat-contract.mjs';
const enc=new TextEncoder();
export function createWorker({send=(...a)=>fetch(...a),now=()=>Math.floor(Date.now()/1000)}={}){
 const reply=(value,status=200,extra={})=>new Response(JSON.stringify(value),{status,headers:{...HEADERS,'Content-Type':'application/json; charset=utf-8',...extra}});
 const cookie=req=>(req.headers.get('cookie')||'').match(/(?:^|;\s*)__Host-gv_session=([A-Za-z0-9_-]{32})(?:;|$)/)?.[1];
 function ready(env){try{gatewayAddress(env.GATEWAY_ENDPOINT);return typeof env.JOB_TOKEN_SECRET==='string'&&env.JOB_TOKEN_SECRET.length>=32&&typeof env.TURNSTILE_SECRET_KEY==='string'&&env.TURNSTILE_SECRET_KEY.length>=16&&typeof env.GATEWAY_API_KEY==='string'&&env.GATEWAY_API_KEY.length>=20&&typeof env.TURNSTILE_SITE_KEY==='string'&&/^[\w-]{10,100}$/.test(env.TURNSTILE_SITE_KEY);}catch{return false;}}
 async function csrf(req,env,origin){check(req.headers.get('origin')===origin&&req.headers.get('sec-fetch-site')!=='cross-site');const s=cookie(req);check(s);const p=await open(req.headers.get('x-gv-csrf'),env.JOB_TOKEN_SECRET,now());exact(p,['kind','session','origin','exp']);check(p.kind==='csrf'&&p.origin===origin&&p.session===await sha(enc.encode(s)));return p.session;}
 return {async fetch(req,env){try{
  const url=new URL(req.url);check(url.protocol==='https:'||url.hostname==='127.0.0.1');
  if(!url.pathname.startsWith('/api/')){check(req.method==='GET'||req.method==='HEAD');return env.ASSETS.fetch(req);}
  check(!url.search&&!url.hash);
  if(url.pathname==='/api/config'&&req.method==='GET'){
   check(req.headers.get('sec-fetch-site')!=='cross-site');if(!ready(env))return reply({ready:false});const s=random(),session=await sha(enc.encode(s)),token=await seal({kind:'csrf',session,origin:url.origin,exp:now()+900},env.JOB_TOKEN_SECRET);return reply({ready:true,siteKey:env.TURNSTILE_SITE_KEY,csrf:token},200,{'Set-Cookie':`__Host-gv_session=${s}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=900`});
  }
  check(ready(env),'LIVE_UNAVAILABLE');check(req.method==='POST'&&['/api/analyze','/api/decide'].includes(url.pathname));const session=await csrf(req,env,url.origin),api=protocol(env,send);
  if(url.pathname==='/api/decide'){
   check(req.headers.get('content-type')==='application/json');const input=await json(req,8192);exact(input,['token','choice']);const p=await open(input.token,env.JOB_TOKEN_SECRET,now());exact(p,['kind','session','origin','exp','job','decision','hash','cat_policy']);check(p.cat_policy===CAT_POLICY);check(p.kind==='job'&&p.session===session&&p.origin===url.origin&&/^[a-f0-9]{32}$/.test(p.job));const approve=input.choice==='ORIGINAL'&&p.decision==='ACCEPT_ORIGINAL'||input.choice==='PROPOSAL'&&p.decision==='ENHANCE';check(approve||input.choice==='REQUEST_NEW_PHOTO');const r=await api.call({operation:'decide',job_id:p.job,decision:approve?'APPROVE':'REQUEST_NEW_PHOTO'});check(r.published===false&&r.status===(approve?'APPROVED_PRIVATE':'REQUEST_NEW_PHOTO')&&(!approve||r.proposal_sha256===p.hash));return reply({choice:input.choice,published:false,status:approve?'APPROVED_DEMO':'REQUEST_NEW_PHOTO',sha256:approve?p.hash:null});
  }
  check(/^multipart\/form-data; boundary=/.test(req.headers.get('content-type')||''));const bytes=await bounded(req,5*LIMIT+65536),form=await new Request(req.url,{method:'POST',headers:{'Content-Type':req.headers.get('content-type')},body:bytes}).formData();check([...form.keys()].every(k=>['rights','turnstile','photos'].includes(k))&&form.getAll('rights').length===1&&form.getAll('turnstile').length===1&&form.get('rights')==='true');const challenge=form.get('turnstile'),files=form.getAll('photos');check(typeof challenge==='string'&&challenge.length>=10&&challenge.length<=2048&&files.length>=1&&files.length<=5);const photos=[];for(const f of files){check(f instanceof Blob&&f.size<=LIMIT);const b=new Uint8Array(await f.arrayBuffer());image(b,f.type);photos.push({bytes:b,type:f.type,sha256:await sha(b)});}
  const verified=await send('https://challenges.cloudflare.com/turnstile/v0/siteverify',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({secret:env.TURNSTILE_SECRET_KEY,response:challenge}),redirect:'manual',signal:AbortSignal.timeout(10000)});check(verified.status===200);const v=await json(verified,16384);check(v.success===true&&v.hostname===url.hostname&&v.action==='gracevision-job');
  const result=await api.analyze(photos),t=result.trace,token=await seal({kind:'job',cat_policy:CAT_POLICY,session,origin:url.origin,exp:now()+600,job:result.job,decision:t.decision,hash:t.selected===null?null:t.items[t.selected].proposal_sha256},env.JOB_TOKEN_SECRET);return reply({...t,token,proposalBytes:result.proposal});
 }catch{return reply({error:'REQUEST_REJECTED'},400);}}};
}
export default createWorker();
