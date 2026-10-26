import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {createWorker} from '../worker.mjs';
import {HEADERS} from '../security.mjs';
const require=createRequire(import.meta.url);
const {FakeTransport}=require('./fake-transport.cjs');
export const publicRoot=fileURLToPath(new URL('../public/',import.meta.url));
export const origin='https://jury.invalid';
export const fixture=name=>fs.readFileSync(path.join(publicRoot,'assets',name+'.png'));
const response=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'content-type':'application/json'}});
export class World{
 constructor(){
  this.seconds=1000;this.sequence=0;this.challengeSequence=0;this.usedChallenges=new Set();this.jobs=new Map();this.calls=[];this.quota=40;this.consumed=0;this.enforceRate=false;this.rateTokens=2;this.lastRate=this.seconds;this.redirect=null;this.mode='mock';
  this.key='synthetic-gateway-key-for-offline-tests';
  this.env={GATEWAY_ENDPOINT:'https://synthetic.execute-api.eu-central-1.amazonaws.com/jury/invoke',GATEWAY_API_KEY:this.key,JOB_TOKEN_SECRET:'synthetic-job-secret-for-offline-tests-only',TURNSTILE_SECRET_KEY:'synthetic-turnstile-secret-only',TURNSTILE_SITE_KEY:'synthetic-site-key',ASSETS:{fetch:req=>this.asset(req)}};
  this.worker=createWorker({send:(u,o)=>this.send(u,o),now:()=>this.seconds});
 }
 challenge(){return 'synthetic-challenge-'+(++this.challengeSequence);}
 signed(key){const u=new URL('https://synthetic-storage.s3.eu-central-1.amazonaws.com/'+key);u.searchParams.set('X-Amz-Credential','synthetic/20261024/eu-central-1/s3/aws4_request');u.searchParams.set('X-Amz-Signature','synthetic-only');u.searchParams.set('X-Amz-Expires','120');return u.href;}
 async asset(req){const url=new URL(req.url),rel=url.pathname==='/'?'index.html':url.pathname.slice(1);if(!/^(?:index\.html|demo\.css|src\/(?:adapters|session|ui|i18n)\.mjs|assets\/(?:graceways-base\.css|fixtures\.json|(?:suitable|correctable|correctable-proposal|unusable)\.png))$/.test(rel))return new Response(null,{status:404,headers:HEADERS});const bytes=fs.readFileSync(path.join(publicRoot,rel));const ext=path.extname(rel),mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json','.png':'image/png'}[ext];return new Response(req.method==='HEAD'?null:bytes,{headers:{...HEADERS,'Content-Type':mime}});}
 async send(input,options={}){
  const u=new URL(String(input));assert.equal(options.redirect,'manual','No redirects allowed');assert(options.signal,'Every internal call has a timeout');
  if(u.hostname==='challenges.cloudflare.com'){
   this.calls.push({kind:'turnstile'});if(this.redirect==='turnstile')return new Response(null,{status:307});const p=new URLSearchParams(options.body),token=p.get('response');const ok=p.get('secret')===this.env.TURNSTILE_SECRET_KEY&&/^synthetic-challenge-\d+$/.test(token||'')&&!this.usedChallenges.has(token);if(ok)this.usedChallenges.add(token);return response({success:ok,hostname:'jury.invalid',action:'gracevision-job'});
  }
  if(u.hostname==='synthetic.execute-api.eu-central-1.amazonaws.com'){
   this.calls.push({kind:'gateway'});if(this.redirect==='gateway')return new Response(null,{status:307});if(options.headers['x-api-key']!==this.key)return response({error:'denied'},403);
   if(this.consumed>=this.quota)return response({error:'quota'},429);if(this.enforceRate){this.rateTokens=Math.min(2,this.rateTokens+(this.seconds-this.lastRate)*2);this.lastRate=this.seconds;if(this.rateTokens<1)return response({error:'throttle'},429);this.rateTokens--;}
   this.consumed++;const event=JSON.parse(options.body);const shapes={create:['operation','rights_confirmed','uploads'],analyze:['job_id','operation'],result:['job_id','operation'],decide:['decision','job_id','operation']};if(!shapes[event.operation]||Object.keys(event).sort().join()!==shapes[event.operation].join())return response({statusCode:400,error:'INVALID_REQUEST_OR_IMAGE'});this.calls.at(-1).operation=event.operation;
   let fake;
   if(event.operation==='create'){fake=new FakeTransport();fake.sequence=this.sequence++;const r=await fake.invoke(event);this.jobs.set(r.result.job_id,fake);r.result.uploads.forEach((upload,i)=>upload.url=this.signed('originals/'+r.result.job_id+'/'+i+'.'+(event.uploads[i].content_type==='image/png'?'png':'jpg')));return response(r);}
   fake=this.jobs.get(event.job_id);if(!fake)return response({statusCode:404,error:'NOT_FOUND'});
   if(event.operation==='decide'){if(fake.decided)return response({statusCode:409,error:'ALREADY_EXISTS'});if(!['APPROVE','REQUEST_NEW_PHOTO'].includes(event.decision))return response({statusCode:400,error:'INVALID_REQUEST_OR_IMAGE'});fake.decided=true;}
   const r=await fake.invoke(event);if(event.operation==='result'){r.result.previews.forEach(p=>p.url=this.signed(p.url));if(this.injectReason)r.result.trace.items[0].reasons=[this.injectReason];}return response(r);
  }
  if(u.hostname==='synthetic-storage.s3.eu-central-1.amazonaws.com'){
   const key=decodeURIComponent(u.pathname.slice(1)),parts=key.split('/'),fake=this.jobs.get(parts[1]);assert(fake,'Fake job must exist');const upload=options.method==='PUT';this.calls.push({kind:upload?'upload':'preview'});if(this.redirect===(upload?'upload':'preview'))return new Response(null,{status:307});
   if(upload){if(fake.objects.has(key))return new Response(null,{status:412});await fake.upload('synthetic-upload',options.headers,Buffer.from(options.body),key);return new Response(null,{status:200});}
   const bytes=await fake.preview('synthetic-preview',key);if(this.tamperOriginal&&key.startsWith('originals/'))bytes[0]^=1;return new Response(bytes,{headers:{'content-type':'image/png','content-length':String(bytes.length)}});
  }
  throw Error('Unexpected fake route; no real network fallback exists.');
 }
 async config(){const r=await this.worker.fetch(new Request(origin+'/api/config'),this.env);const value=await r.json();this.csrf=value.csrf;this.cookie=r.headers.get('set-cookie')?.split(';')[0];return value;}
 headers(extra={}){return {Origin:origin,'Sec-Fetch-Site':'same-origin',Cookie:this.cookie,'X-GV-CSRF':this.csrf,...extra};}
 form(names=['correctable','unusable'],options={}){const f=new FormData();f.set('rights',options.rights===false?'false':'true');f.set('turnstile',options.challenge??this.challenge());for(const name of names)f.append('photos',new Blob([fixture(name)],{type:options.type||'image/png'}),'synthetic.png');return f;}
 async analyze(names,options={}){const r=await this.worker.fetch(new Request(origin+'/api/analyze',{method:'POST',headers:this.headers(options.headers),body:options.form||this.form(names,options)}),this.env);return {status:r.status,body:await r.json()};}
 async decide(token,choice,options={}){const r=await this.worker.fetch(new Request(origin+'/api/decide',{method:'POST',headers:this.headers({'Content-Type':'application/json',...options.headers}),body:JSON.stringify({token,choice})}),this.env);return {status:r.status,body:await r.json()};}
}
