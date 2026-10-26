export class Rejected extends Error {constructor(code='REQUEST_REJECTED'){super(code);this.code=code;}}
export const check=(v,code)=>{if(!v)throw new Rejected(code);};
export const exact=(o,keys)=>check(o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).sort().join()===keys.slice().sort().join());
const enc=new TextEncoder(),dec=new TextDecoder();
export const hex=b=>Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('');
export const sha=async b=>hex(await crypto.subtle.digest('SHA-256',b));
export function b64(bytes){let s='';for(let i=0;i<bytes.length;i+=32768)s+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(s);}
export function un64(s){check(typeof s==='string'&&/^[A-Za-z0-9+/]*={0,2}$/.test(s));return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
const url64=b=>b64(new Uint8Array(b)).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
const from64=s=>un64(s.replaceAll('-','+').replaceAll('_','/')+'='.repeat((4-s.length%4)%4));
export const random=()=>url64(crypto.getRandomValues(new Uint8Array(24)));
async function keys(secret){check(typeof secret==='string'&&secret.length>=32,'LIVE_UNAVAILABLE');return {mac:await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']),aes:await crypto.subtle.importKey('raw',await crypto.subtle.digest('SHA-256',enc.encode('job-encryption:'+secret)),'AES-GCM',false,['encrypt','decrypt'])};}
export async function seal(payload,secret){const k=await keys(secret),iv=crypto.getRandomValues(new Uint8Array(12)),ct=await crypto.subtle.encrypt({name:'AES-GCM',iv},k.aes,enc.encode(JSON.stringify(payload))),body='v1.'+url64(iv)+'.'+url64(ct);return body+'.'+url64(await crypto.subtle.sign('HMAC',k.mac,enc.encode(body)));}
export async function open(token,secret,now){check(typeof token==='string'&&token.length<=4096&&/^v1\.[\w-]+\.[\w-]+\.[\w-]+$/.test(token));const parts=token.split('.'),k=await keys(secret),body=parts.slice(0,3).join('.');check(await crypto.subtle.verify('HMAC',k.mac,from64(parts[3]),enc.encode(body)));const p=JSON.parse(dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:from64(parts[1])},k.aes,from64(parts[2]))));check(Number.isInteger(p.exp)&&p.exp>now&&p.exp<=now+900);return p;}
export async function bounded(response,max){check(response&&response.body&&Number(response.headers.get('content-length')||0)<=max);const reader=response.body.getReader(),parts=[];let size=0;try{for(;;){const r=await reader.read();if(r.done)break;size+=r.value.length;check(size<=max);parts.push(r.value);}}catch(e){await reader.cancel();throw e;}finally{reader.releaseLock();}const bytes=new Uint8Array(size);let at=0;for(const p of parts){bytes.set(p,at);at+=p.length;}return bytes;}
export async function json(response,max=512*1024){return JSON.parse(dec.decode(await bounded(response,max)));}
export const LIMIT=2*1024*1024,PIXELS=2560000;
export function image(bytes,type){check(bytes instanceof Uint8Array&&bytes.length>=24&&bytes.length<=LIMIT);const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let w,h;
 if(type==='image/png'){check([137,80,78,71,13,10,26,10].every((x,i)=>bytes[i]===x));check(v.getUint32(12)===0x49484452);w=v.getUint32(16);h=v.getUint32(20);}
 else if(type==='image/jpeg'){check(bytes[0]===255&&bytes[1]===216);let i=2;while(i+4<bytes.length){check(bytes[i]===255);const marker=bytes[i+1],n=v.getUint16(i+2);check(n>=2&&i+2+n<=bytes.length);if([0xc0,0xc1,0xc2].includes(marker)){check(n>=7);h=v.getUint16(i+5);w=v.getUint16(i+7);break;}i+=2+n;}check(w&&h);}
 else check(false);
 check(w>0&&h>0&&w<=1600&&h<=1600&&w*h<=PIXELS);return {width:w,height:h};
}
export const HEADERS={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=(), payment=(), usb=()','Content-Security-Policy':"default-src 'self'; script-src 'self' https://challenges.cloudflare.com; style-src 'self'; img-src 'self' blob:; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"};
