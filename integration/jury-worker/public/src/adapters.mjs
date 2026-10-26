export class DemoError extends Error { constructor(code){super(code);this.code=code;} }
export async function sha256(bytes){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
// Private immutable preview state; object URLs are display handles, never fetch targets.
const proposals=new WeakMap();
export const MAX_PROPOSAL_BYTES=80*1024*1024;
export function releaseProposal(item){const stored=proposals.get(item);if(stored){URL.revokeObjectURL(stored.url);proposals.delete(item);item.proposal=null;}}
export function releaseTrace(trace){for(const item of trace?.items||[])releaseProposal(item);}
export async function retainProposal(item,blob){
 if(!(blob instanceof Blob)||blob.type!=='image/png'||blob.size<8||blob.size>MAX_PROPOSAL_BYTES)throw new DemoError('FORMAT');
 const bytes=await blob.arrayBuffer(),magic=new Uint8Array(bytes,0,8);
 if(![137,80,78,71,13,10,26,10].every((v,i)=>magic[i]===v))throw new DemoError('FORMAT');
 if(await sha256(bytes)!==item.proposal_sha256)throw new DemoError('INTEGRITY');
 releaseProposal(item);const immutable=new Blob([bytes],{type:'image/png'}),url=URL.createObjectURL(immutable);
 proposals.set(item,{blob:immutable,url,sha256:item.proposal_sha256});item.proposal=url;
}
export async function verifyProposal(item){const stored=proposals.get(item);if(!stored||stored.url!==item.proposal||stored.sha256!==item.proposal_sha256||await sha256(await stored.blob.arrayBuffer())!==stored.sha256)throw new DemoError('INTEGRITY');return stored.blob;}
async function readProposal(response){
 if(!response.ok||response.headers.get('content-type')?.split(';')[0].trim()!=='image/png'||Number(response.headers.get('content-length'))>MAX_PROPOSAL_BYTES)throw new DemoError('FORMAT');
 const reader=response.body?.getReader();if(!reader)throw new DemoError('FORMAT');const chunks=[];let size=0;
 try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>MAX_PROPOSAL_BYTES)throw new DemoError('FORMAT');chunks.push(value);}}catch(e){await reader.cancel();throw e;}finally{reader.releaseLock();}
 return new Blob(chunks,{type:'image/png'});
}
// Same contract for local fixture replay and a future private server-side broker.
// No endpoint, credentials, AWS identifier or signed URL is accepted by this UI.
export class AwsAdapter {
 constructor(capability){this.mode='aws';this.capability=capability;}
 assertReady(){if(!this.capability||typeof this.capability.csrf!=='string'||typeof this.capability.takeChallenge!=='function')throw new DemoError('AWS_DISABLED');}
 async request(path,body,multipart=false){this.assertReady();try{const r=await fetch(path,{method:'POST',headers:{'X-GV-CSRF':this.capability.csrf,...(multipart?{}:{'Content-Type':'application/json'})},credentials:'same-origin',body:multipart?body:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(90000)});if(!r.ok)throw Error();return await r.json();}catch{throw new DemoError('BRIDGE_REJECTED');}}
 async analyze(photos,{rights=false}={}){this.assertReady();if(!rights)throw new DemoError('RIGHTS');if(!Array.isArray(photos)||photos.length<1||photos.length>5)throw new DemoError('COUNT');for(const p of photos){if(p.bytes.byteLength>2*1024*1024||!['image/png','image/jpeg'].includes(p.type))throw new DemoError('FORMAT');if(await sha256(p.bytes)!==p.sha256)throw new DemoError('INTEGRITY');}
 const challenge=this.capability.takeChallenge();if(typeof challenge!=='string')throw new DemoError('AWS_DISABLED');const form=new FormData();form.set('rights','true');form.set('turnstile',challenge);for(const p of photos)form.append('photos',new Blob([p.bytes],{type:p.type}),'photo');const trace=await this.request('/api/analyze',form,true);
 try{if(trace.proposalBytes){if(trace.decision!=='ENHANCE'||trace.selected===null||trace.proposalBytes.type!=='image/png'||typeof trace.proposalBytes.base64!=='string'||trace.proposalBytes.base64.length>Math.ceil(16*1024*1024/3)*4)throw new DemoError('FORMAT');const b=Uint8Array.from(atob(trace.proposalBytes.base64),c=>c.charCodeAt(0));await retainProposal(trace.items[trace.selected],new Blob([b],{type:'image/png'}));}delete trace.proposalBytes;return trace;}catch(e){releaseTrace(trace);throw e;}}
 async decide(trace,choice){this.assertReady();if(choice==='PROPOSAL')await verifyProposal(trace.items[trace.selected]);return this.request('/api/decide',{token:trace.token,choice});}
}
export class MockAdapter {
 constructor(fixtures){this.fixtures=fixtures;this.mode='mock';}
 async analyze(photos,{failure='none',rights=false}={}){
  if(!rights)throw new DemoError('RIGHTS');
  if(photos.length<1||photos.length>5)throw new DemoError('COUNT');
  if(failure!=='none')throw new DemoError(failure.toUpperCase());
  const items=[];
  for(const [index,photo] of photos.entries()){
   if(!['image/png','image/jpeg'].includes(photo.type)||photo.bytes.byteLength>12*1024*1024)throw new DemoError('FORMAT');
   const hash=await sha256(photo.bytes);if(hash!==photo.sha256)throw new DemoError('INTEGRITY');
   const f=this.fixtures[hash];if(!f)throw new DemoError('FIXTURE');
   items.push({...structuredClone(f),index,original_sha256:hash,eligible:f.action!=='TRY_NEXT_IMAGE',proposal_sha256:f.proposal_sha256||hash});
  }
  const candidates=items.filter(x=>x.eligible).sort((a,b)=>((b.after||b.metrics).sharpness-(a.after||a.metrics).sharpness)||a.index-b.index);
  const selected=candidates[0]?.index??null;
  return {mode:'mock',measurementSource:'precomputed-local-opencv-5.0.0',selected,items,decision:selected===null?'REQUEST_NEW_PHOTO':items[selected].action,published:false,approval:null};
 }
 async decide(trace,choice){
  if(trace.approval)throw new DemoError('ALREADY_DECIDED');
  if(!['ORIGINAL','PROPOSAL','REJECT','REQUEST_NEW_PHOTO'].includes(choice))throw new DemoError('CHOICE');
  if(['ORIGINAL','PROPOSAL'].includes(choice)&&trace.selected===null)throw new DemoError('NO_SELECTION');
  const item=trace.items[trace.selected];
  if(choice==='PROPOSAL'&&item.action!=='ENHANCE')throw new DemoError('NO_PROPOSAL');
  return {choice,published:false,status:['ORIGINAL','PROPOSAL'].includes(choice)?'APPROVED_DEMO':choice,sha256:choice==='ORIGINAL'?item.original_sha256:choice==='PROPOSAL'?item.proposal_sha256:null};
 }
}
